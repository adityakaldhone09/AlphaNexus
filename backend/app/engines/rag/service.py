"""
EquiLens AI – Financial RAG Service
=====================================
Central orchestrator for the full RAG pipeline:

  INGESTION:
    File validation → Document classification → Loader dispatch →
    Table extraction → Financial-domain chunking → Metadata enrichment →
    Embedding generation → pgvector storage

  RETRIEVAL & GENERATION:
    Query classification → Query rewriting → Hybrid retrieval (semantic + BM25 + RRF) →
    Optional BGE reranking → Context assembly → Gemini synthesis →
    Structured financial response → Verified source citations

All configuration (chunk sizes, embedding model, retrieval weights, reranking toggle)
is driven by the active RAGConfiguration row or per-request overrides.
"""

from __future__ import annotations

import hashlib
import os
import time
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import logger
from app.engines.providers.gemini import GeminiProvider
from app.engines.providers.groq import GroqProvider
from app.engines.rag.chunking import FinancialDocumentChunker
from app.engines.rag.citations import CitationEngine
from app.engines.rag.classifier import document_classifier
from app.engines.rag.embeddings import embedding_engine
from app.engines.rag.loaders.docx_loader import DOCXDocumentLoader
from app.engines.rag.loaders.pdf_loader import PDFDocumentLoader
from app.engines.rag.loaders.tabular_loader import TabularDocumentLoader
from app.engines.rag.loaders.langchain_loader import LangChainDocumentLoader
from app.engines.rag.preprocessor import DocumentPreprocessor
from app.engines.rag.query_router import query_router, QueryRoute
from app.engines.rag.rerankers import get_reranker
from app.engines.rag.vector_store import vector_store
from app.database.mongodb import mongodb_manager
from app.models.company import Company
from app.models.document import Document, DocumentChunk
from app.models.research import Citation, ResearchMessage, ResearchSession


# ---------------------------------------------------------------------------
# Financial system prompt
# ---------------------------------------------------------------------------

_FINANCIAL_SYSTEM_PROMPT = """You are EquiLens AI, an evidence-grounded equity research analyst.

CORE RESPONSIBILITIES:
- Provide objective, fact-backed financial intelligence using the supplied source excerpts.
- Every quantitative claim must reference a specific source bracket: [Source N].
- Never invent financial figures, dates, or company names.
- Clearly identify the financial year and reporting period for every metric cited.
- Distinguish: (a) Verified Document Facts, (b) Calculated Metrics, (c) Strategic Interpretations.
- State clearly when information is absent from the provided documents.
- Never predict specific stock prices or guarantee future performance.
- Distinguish historical facts from forward-looking estimates.
- Note whether figures are Consolidated or Standalone.
- Preserve units (₹ Crores, %, basis points) exactly as in source documents.

RESPONSE STRUCTURE:
1. **Executive Summary** – 2-3 sentences answering the core question
2. **Key Financial Findings** – bullet list of verified facts with citations
3. **Historical Context / Trend** – YoY or multi-year perspective where available
4. **Risks & Opportunities** – factual risks from filings, not speculation
5. **Financial Interpretation** – calculated ratios or derived analysis
6. **Supporting Evidence** – verbatim excerpts with [Source N, Page P] tags
7. **Information Gaps** – what could not be answered from the available documents
"""


class RAGService:
    """
    Production RAG orchestrator for EquiLens AI financial document intelligence.
    Singleton – use `rag_service` module-level instance.
    """

    def __init__(self) -> None:
        self.pdf_loader = PDFDocumentLoader()
        self.docx_loader = DOCXDocumentLoader()
        self.tabular_loader = TabularDocumentLoader()
        self.langchain_loader = LangChainDocumentLoader()
        self.preprocessor = DocumentPreprocessor()
        self.chunker = FinancialDocumentChunker()
        self.gemini = GeminiProvider()
        self.groq = GroqProvider()
        # Expose module-level singletons as instance attributes for testability
        self.embedding_engine = embedding_engine
        self.vector_store = vector_store

    # ==================================================================
    # INGESTION PIPELINE
    # ==================================================================

    def ingest_document(
        self,
        db: Session,
        document_id: str,
        file_path_or_bytes: Any,
        filename: str,
        mime_type: str,
        *,
        manual_document_type: Optional[str] = None,
        financial_year: Optional[str] = None,
        quarter: Optional[str] = None,
        currency: str = "INR",
        unit: str = "Crores",
        is_consolidated: bool = True,
        reprocess: bool = False,
    ) -> Dict[str, Any]:
        """
        Full document ingestion pipeline.
        Idempotent: deletes existing chunks before re-inserting.
        """
        t0 = time.monotonic()
        doc_uuid = _to_uuid(document_id)
        doc = db.query(Document).filter(Document.id == doc_uuid).first()
        if not doc:
            raise ValueError(f"Document {document_id} not found")

        # Skip if already processed and not forced
        if doc.status == "PROCESSED" and not reprocess:
            return {
                "document_id": str(doc.id),
                "status": "PROCESSED",
                "pages_extracted": doc.total_pages,
                "chunks_stored": doc.total_chunks,
                "skipped": True,
                "reason": "Already processed – use reprocess=True to force",
            }

        # Compute file hash for dedup detection
        file_hash = self._compute_hash(file_path_or_bytes)
        doc.file_hash = file_hash
        doc.status = "PROCESSING"
        db.commit()

        try:
            # ── 1. Load pages ──────────────────────────────────────────
            pages_data = self._load_file(file_path_or_bytes, filename, mime_type)
            logger.info(
                f"[RAG] Loaded {len(pages_data)} pages from '{filename}'"
            )

            # ── 2. Classify document type ─────────────────────────────
            first_page_text = pages_data[0].get("text", "") if pages_data else ""
            classification = document_classifier.classify(
                filename=filename,
                first_page_text=first_page_text,
                manual_hint=manual_document_type or doc.document_type,
            )
            doc_type = classification.document_type
            if doc.document_type and doc.document_type != "Other":
                doc_type = doc.document_type  # user-supplied wins
            logger.info(
                f"[RAG] Classified as '{doc_type}' "
                f"(conf={classification.confidence:.2f}, "
                f"review_needed={classification.needs_review})"
            )

            # ── 3. Get company info ────────────────────────────────────
            company = db.query(Company).filter(Company.id == doc.company_id).first()
            symbol = company.symbol if company else "STOCK"
            exchange = company.exchange if company else ""
            fy = financial_year or doc.financial_year or "FY24"

            # ── 4. Chunking ────────────────────────────────────────────
            chunks = self.chunker.chunk_document(
                pages_data=pages_data,
                company_id=str(doc.company_id),
                document_id=str(doc.id),
                company_symbol=symbol,
                financial_year=fy,
                document_type=doc_type,
                quarter=quarter,
                ticker=symbol,
                exchange=exchange,
                currency=currency,
                unit=unit,
                is_consolidated=is_consolidated,
            )
            logger.info(f"[RAG] Created {len(chunks)} chunks")

            # ── 5. Embed ───────────────────────────────────────────────
            contents = [c["content"] for c in chunks]
            embeddings = embedding_engine.generate_document_embeddings(contents)
            for chunk, emb in zip(chunks, embeddings):
                chunk["embedding"] = emb

            # ── 6. Persist ─────────────────────────────────────────────
            vector_store.delete_document_chunks(db, str(doc.id))
            stored = vector_store.store_chunks(db, chunks)

            # Persist to MongoDB Atlas if connected
            if mongodb_manager.is_connected:
                try:
                    mongodb_manager.delete_document_chunks(str(doc.id))
                    mongodb_manager.store_document({
                        "_id": str(doc.id),
                        "company_id": str(doc.company_id),
                        "filename": filename,
                        "document_type": doc_type,
                        "financial_year": fy,
                        "quarter": quarter,
                        "total_pages": len(pages_data),
                        "total_chunks": len(chunks),
                        "file_checksum": file_hash,
                    })
                    mongodb_manager.store_chunks([
                        {
                            "chunk_id": str(c.get("chunk_id") or uuid.uuid4()),
                            "document_id": str(doc.id),
                            "company_id": str(doc.company_id),
                            "symbol": symbol,
                            "financial_year": fy,
                            "document_type": doc_type,
                            "chunk_index": c.get("chunk_index", 0),
                            "page_number": c.get("page_number", 1),
                            "section": c.get("section", ""),
                            "content": c.get("content", ""),
                            "embedding": c.get("embedding", []),
                            "token_count": c.get("token_count", 0),
                        }
                        for c in chunks
                    ])
                    logger.info(f"[RAG] Synced {len(chunks)} chunks to MongoDB Atlas.")
                except Exception as mongo_err:
                    logger.warning(f"[RAG] MongoDB sync notice: {mongo_err}")
            else:
                logger.info(
                    "[RAG] MongoDB Atlas is disconnected; document chunks persisted in authoritative PostgreSQL vector store."
                )

            # ── 7. Update document record ──────────────────────────────
            doc.status = "PROCESSED"
            doc.document_type = doc_type
            doc.total_pages = len(pages_data)
            doc.total_chunks = stored
            doc.error_message = None
            db.commit()

            elapsed = round(time.monotonic() - t0, 2)
            logger.info(
                f"[RAG] Ingestion complete: doc={document_id[:8]}… "
                f"pages={len(pages_data)} chunks={stored} "
                f"elapsed={elapsed}s"
            )
            return {
                "document_id": str(doc.id),
                "status": "PROCESSED",
                "document_type": doc_type,
                "pages_extracted": len(pages_data),
                "chunks_stored": stored,
                "classification_confidence": classification.confidence,
                "needs_review": classification.needs_review,
                "elapsed_s": elapsed,
            }

        except Exception as exc:
            logger.error(f"[RAG] Ingestion failed for {document_id}: {exc}")
            doc.status = "FAILED"
            doc.error_message = str(exc)[:500]
            db.commit()
            raise

    # ==================================================================
    # RETRIEVAL PIPELINE (used by research_chat and /rag/retrieve)
    # ==================================================================

    def retrieve(
        self,
        db: Session,
        query: str,
        company_id: Optional[str] = None,
        financial_year: Optional[str] = None,
        document_type: Optional[str] = None,
        top_k: int = 8,
        min_similarity: float = 0.0,
        hybrid: bool = True,
        reranking: bool = False,
        vector_weight: float = 0.6,
        keyword_weight: float = 0.4,
    ) -> Dict[str, Any]:
        """
        Standalone retrieval endpoint (no generation).
        Used by /rag/retrieve and /rag/retrieve/debug.
        """
        # Route query
        routing = query_router.route(query, company_hint=company_id)
        primary_query = routing.rewritten_queries[0]
        fy_hint = financial_year or routing.financial_year_hint

        # Embed primary query
        q_vec = embedding_engine.generate_query_embedding(primary_query)

        if hybrid:
            candidates = vector_store.hybrid_search(
                db=db,
                query=primary_query,
                query_embedding=q_vec,
                company_id=company_id,
                financial_year=fy_hint,
                document_type=document_type,
                top_k=top_k * (3 if reranking else 1),
                min_similarity=min_similarity,
                vector_weight=vector_weight,
                keyword_weight=keyword_weight,
            )
        else:
            candidates = vector_store.search_similar(
                db=db,
                query_embedding=q_vec,
                company_id=company_id,
                financial_year=fy_hint,
                document_type=document_type,
                top_k=top_k * (3 if reranking else 1),
                min_similarity=min_similarity,
            )

        # Multi-query fusion: run additional rewrites and merge
        extra_chunks: List[Dict[str, Any]] = []
        for alt_q in routing.rewritten_queries[1:]:
            alt_vec = embedding_engine.generate_query_embedding(alt_q)
            alt_results = vector_store.search_similar(
                db=db,
                query_embedding=alt_vec,
                company_id=company_id,
                financial_year=fy_hint,
                document_type=document_type,
                top_k=top_k,
                min_similarity=min_similarity,
            )
            extra_chunks.extend(alt_results)

        # Merge and deduplicate by chunk_id
        seen_ids: set = {c["chunk_id"] for c in candidates}
        for ec in extra_chunks:
            if ec["chunk_id"] not in seen_ids:
                candidates.append(ec)
                seen_ids.add(ec["chunk_id"])

        # Optional reranking
        if reranking:
            reranker = get_reranker()
            if reranker.is_available:
                candidates = reranker.rerank(primary_query, candidates, top_k=top_k)

        final = candidates[:top_k]

        return {
            "query": query,
            "rewritten_query": primary_query,
            "route": routing.route.value,
            "financial_year_hint": fy_hint,
            "retrieved_count": len(final),
            "chunks": final,
            "routing": {
                "route": routing.route.value,
                "confidence": routing.confidence,
                "reasoning": routing.reasoning,
                "rewrites": routing.rewritten_queries,
                "metric_hints": routing.metric_hints,
            },
        }

    def search_documents(
        self,
        query: str,
        top_k: int = 3,
        db: Optional[Session] = None,
    ) -> List[Dict[str, Any]]:
        """
        Legacy/convenience helper for document retrieval.
        """
        close_db = False
        if db is None:
            from app.core.database import SessionLocal
            db = SessionLocal()
            close_db = True
        try:
            res = self.retrieve(db=db, query=query, top_k=top_k)
            return res.get("chunks", [])
        finally:
            if close_db:
                db.close()

    # ==================================================================
    # RESEARCH CHAT (retrieval + generation)
    # ==================================================================

    def research_chat(
        self,
        db: Session,
        session_id: str,
        user_query: str,
        company_id: Optional[str] = None,
        financial_year: Optional[str] = None,
        document_type: Optional[str] = None,
        top_k: int = 8,
        hybrid: bool = True,
        reranking: bool = False,
    ) -> Dict[str, Any]:
        """
        Full RAG chat pipeline:
        query → retrieval → generation → citations → persisted messages
        """
        sess_uuid = _to_uuid(session_id)
        comp_uuid = _to_uuid(company_id) if company_id else None

        # Save user message
        user_msg = ResearchMessage(
            session_id=sess_uuid,
            role="user",
            content=user_query,
            message_type="user_query",
        )
        db.add(user_msg)
        db.commit()

        # ── Retrieval ────────────────────────────────────────────────
        retrieval = self.retrieve(
            db=db,
            query=user_query,
            company_id=str(comp_uuid) if comp_uuid else None,
            financial_year=financial_year,
            document_type=document_type,
            top_k=top_k,
            hybrid=hybrid,
            reranking=reranking,
        )
        retrieved_chunks = retrieval["chunks"]

        # ── Context assembly ─────────────────────────────────────────
        context_text = CitationEngine.format_context_for_prompt(retrieved_chunks)

        # ── Generation ───────────────────────────────────────────────
        prompt = (
            f"Context Documents:\n{context_text}\n\n"
            f"Research Question: {user_query}\n\n"
            "Provide a structured equity research answer following the response template. "
            "Use [Source N] inline citations tied to the context above."
        )

        final_content, msg_type, tokens = self._generate(prompt)

        # ── Persist assistant message ─────────────────────────────────
        asst_msg = ResearchMessage(
            session_id=sess_uuid,
            role="assistant",
            content=final_content,
            message_type=msg_type,
            token_count=tokens,
        )
        db.add(asst_msg)
        db.commit()

        # ── Citations ────────────────────────────────────────────────
        citations_data = CitationEngine.build_citations_from_retrieval(
            retrieved_chunks, asst_msg.id
        )
        saved_citations = []
        for cit in citations_data:
            doc_id_val = _to_uuid(cit["document_id"])
            chunk_id_val = _to_uuid(cit.get("document_chunk_id"))
            citation_obj = Citation(
                message_id=asst_msg.id,
                document_id=doc_id_val,
                document_chunk_id=chunk_id_val,
                chunk_index=cit.get("chunk_index"),
                page_number=cit.get("page_number"),
                section=cit.get("section"),
                excerpt=cit["excerpt"],
                source_url=cit.get("source_url"),
                confidence_score=cit.get("confidence_score", 0.95),
            )
            db.add(citation_obj)
            cit["id"] = None  # filled after commit
            saved_citations.append(cit)
        db.commit()

        # Reload citations to get IDs
        db.refresh(asst_msg)

        return {
            "message_id": str(asst_msg.id),
            "session_id": str(sess_uuid),
            "role": "assistant",
            "content": final_content,
            "message_type": msg_type,
            "tokens_used": tokens,
            "retrieved_count": len(retrieved_chunks),
            "route": retrieval["route"],
            "citations": citations_data,
        }

    # ==================================================================
    # GENERATION
    # ==================================================================

    def _generate(self, prompt: str) -> tuple[str, str, int]:
        """Try Gemini → Groq → evidence fallback.  Returns (content, msg_type, tokens)."""
        # Gemini
        if getattr(self.gemini, "api_key", None):
            resp = self.gemini.generate(
                prompt=prompt,
                system_prompt=_FINANCIAL_SYSTEM_PROMPT,
            )
            if resp and not resp.error and resp.content:
                return resp.content, "fact_grounded", resp.tokens_used

        # Groq fallback
        if getattr(self.groq, "api_key", None):
            resp = self.groq.generate(
                prompt=prompt,
                system_prompt=_FINANCIAL_SYSTEM_PROMPT,
            )
            if resp and not resp.error and resp.content:
                return resp.content, "fact_grounded", resp.tokens_used

        # Deterministic evidence synthesis (no LLM key)
        lines = [
            "### Evidence-Grounded Research Synthesis\n",
            "> *No LLM key configured – showing raw document evidence.*\n",
        ]
        # Extract context chunks from prompt
        import re
        sources = re.findall(r"--- SOURCE \[(\d+)\] ---\n(.*?)(?=--- SOURCE|\Z)", prompt, re.DOTALL)
        for idx, (num, block) in enumerate(sources[:5]):
            lines.append(f"\n**[Source {num}]**\n{block.strip()[:400]}\n")
        content = "\n".join(lines)
        return content, "synthesis", len(content.split())

    # ==================================================================
    # DOCUMENT LIFECYCLE HELPERS
    # ==================================================================

    def get_document_stats(self, db: Session, document_id: str) -> Dict[str, Any]:
        doc_uuid = _to_uuid(document_id)
        doc = db.query(Document).filter(Document.id == doc_uuid).first()
        if not doc:
            return {}
        chunk_count = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == doc_uuid)
            .count()
        )
        return {
            "document_id": str(doc.id),
            "status": doc.status,
            "total_pages": doc.total_pages,
            "total_chunks": doc.total_chunks,
            "actual_chunk_count": chunk_count,
            "document_type": doc.document_type,
            "financial_year": doc.financial_year,
            "file_hash": doc.file_hash,
            "embedding_model": embedding_engine.model_name,
            "embedding_dimension": embedding_engine.dimension,
        }

    # ==================================================================
    # INTERNAL UTILITIES
    # ==================================================================

    def _load_file(
        self, file_path_or_bytes: Any, filename: str, mime_type: str
    ) -> List[Dict[str, Any]]:
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".pdf" or "pdf" in (mime_type or ""):
            return self.pdf_loader.load(file_path_or_bytes)
        if ext in (".docx", ".doc"):
            return self.docx_loader.load(file_path_or_bytes)
        if ext == ".csv":
            return self.tabular_loader.load_csv(file_path_or_bytes)
        if ext in (".xlsx", ".xls"):
            return self.tabular_loader.load_excel(file_path_or_bytes)
        # Plain text fallback
        if isinstance(file_path_or_bytes, bytes):
            text = file_path_or_bytes.decode("utf-8", errors="ignore")
        else:
            with open(file_path_or_bytes, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        return [{"page_number": 1, "text": text, "tables": []}]

    def _compute_hash(self, file_path_or_bytes: Any) -> str:
        if isinstance(file_path_or_bytes, bytes):
            return hashlib.sha256(file_path_or_bytes).hexdigest()
        try:
            with open(file_path_or_bytes, "rb") as f:
                return hashlib.sha256(f.read(1024 * 1024)).hexdigest()  # first 1 MB
        except Exception:
            return ""


def _to_uuid(val: Any) -> Optional[uuid.UUID]:
    if val is None:
        return None
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Module singleton
# ---------------------------------------------------------------------------
rag_service = RAGService()
