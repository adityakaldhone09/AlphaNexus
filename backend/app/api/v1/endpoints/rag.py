"""
EquiLens AI – RAG API Endpoints
================================
Full set of RAG pipeline endpoints:

  Document management:   /rag/documents/upload|list|{id}|process|reprocess|delete
  Research:              /rag/query | /rag/chat | /rag/sessions
  Retrieval:             /rag/retrieve | /rag/retrieve/debug
  Administration:        /rag/config | /rag/health | /rag/metrics | /rag/index/rebuild
  Evaluation:            /rag/evaluation/run | /rag/evaluation/results
"""

from __future__ import annotations

import os
import time
import uuid
from typing import List, Optional

from fastapi import (
    APIRouter, BackgroundTasks, Depends,
    File, Form, HTTPException, Query, UploadFile,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db, check_database_health, parse_uuid
from app.database.mongodb import mongodb_manager
from app.engines.rag.embeddings import embedding_engine
from app.engines.rag.reranker import get_reranker
from app.engines.rag.service import rag_service
from app.engines.rag.query_router import query_router
from app.models.company import Company
from app.models.document import Document, DocumentChunk
from app.models.rag_config import RAGConfiguration
from app.models.research import ResearchSession, ResearchMessage
from app.schemas.document import (
    DocumentProcessResponse, DocumentResponse, DocumentUploadResponse,
)
from app.schemas.rag import (
    ChunkResponse,
    EvaluationMetrics,
    RAGChatRequest,
    RAGChatResponse,
    RAGCitationResponse,
    RAGConfigResponse,
    RAGConfigUpdateRequest,
    RAGDocumentStatsResponse,
    RAGEvaluationResponse,
    RAGHealthResponse,
    RAGMetricsResponse,
    RAGQueryRequest,
    RAGRetrieveRequest,
    RAGRetrieveResponse,
)
from app.schemas.research import (
    ResearchMessageResponse, ResearchSessionResponse, CitationResponse,
)

router = APIRouter()


# ===========================================================================
# DOCUMENT MANAGEMENT
# ===========================================================================

@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def rag_upload_document(
    company_id: str = Form(...),
    title: str = Form(...),
    financial_year: str = Form("FY24"),
    document_type: str = Form("Annual Report"),
    file: UploadFile = File(...),
    auto_process: bool = Form(True),
    is_consolidated: bool = Form(True),
    db: Session = Depends(get_db),
):
    """
    Upload a financial document and optionally trigger immediate RAG ingestion.
    Supported: PDF, DOCX, XLSX, CSV.
    """
    company = db.query(Company).filter(Company.id == parse_uuid(company_id)).first()
    if not company:
        raise HTTPException(404, "Company not found")

    # Validate file type
    allowed_exts = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {allowed_exts}")

    # Size limit (50 MB)
    MAX_SIZE = 50 * 1024 * 1024
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(413, "File exceeds 50 MB limit")

    os.makedirs(settings.LOCAL_UPLOAD_DIR, exist_ok=True)
    doc_id = uuid.uuid4()
    safe_name = f"{doc_id}_{file.filename}"
    file_path = os.path.join(settings.LOCAL_UPLOAD_DIR, safe_name)
    with open(file_path, "wb") as fh:
        fh.write(contents)

    doc = Document(
        id=doc_id,
        company_id=parse_uuid(company_id),
        title=title,
        filename=file.filename,
        file_path=file_path,
        file_size_bytes=len(contents),
        mime_type=file.content_type or "application/octet-stream",
        financial_year=financial_year,
        document_type=document_type,
        status="UPLOADED",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    message = "Document uploaded. Ready for processing."
    if auto_process:
        try:
            result = rag_service.ingest_document(
                db=db,
                document_id=str(doc.id),
                file_path_or_bytes=file_path,
                filename=file.filename,
                mime_type=doc.mime_type,
                manual_document_type=document_type,
                financial_year=financial_year,
                is_consolidated=is_consolidated,
            )
            message = (
                f"Processed: {result['chunks_stored']} chunks from "
                f"{result['pages_extracted']} pages "
                f"(type: {result['document_type']}, "
                f"classification_conf: {result['classification_confidence']:.0%})"
            )
        except Exception as exc:
            message = f"Upload succeeded but processing failed: {exc}"

    return DocumentUploadResponse(
        document_id=doc.id,
        title=doc.title,
        filename=doc.filename,
        status=doc.status,
        message=message,
    )


@router.get("/documents", response_model=List[DocumentResponse])
def rag_list_documents(
    company_id: Optional[str] = None,
    document_type: Optional[str] = None,
    status: Optional[str] = None,
    financial_year: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Document)
    if company_id:
        q = q.filter(Document.company_id == parse_uuid(company_id))
    if document_type:
        q = q.filter(Document.document_type == document_type)
    if status:
        q = q.filter(Document.status == status.upper())
    if financial_year:
        q = q.filter(Document.financial_year == financial_year)
    return q.order_by(Document.created_at.desc()).limit(limit).all()


@router.get("/documents/{document_id}", response_model=DocumentResponse)
def rag_get_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == parse_uuid(document_id)).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc


@router.get("/documents/{document_id}/stats", response_model=RAGDocumentStatsResponse)
def rag_document_stats(document_id: str, db: Session = Depends(get_db)):
    stats = rag_service.get_document_stats(db, document_id)
    if not stats:
        raise HTTPException(404, "Document not found")
    return RAGDocumentStatsResponse(**stats)


@router.post("/documents/{document_id}/process", response_model=DocumentProcessResponse)
def rag_process_document(document_id: str, db: Session = Depends(get_db)):
    """Trigger RAG ingestion (first time)."""
    doc = db.query(Document).filter(Document.id == parse_uuid(document_id)).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    if not os.path.exists(doc.file_path):
        raise HTTPException(400, "Stored file not found on disk")
    result = rag_service.ingest_document(
        db=db,
        document_id=str(doc.id),
        file_path_or_bytes=doc.file_path,
        filename=doc.filename,
        mime_type=doc.mime_type,
    )
    return DocumentProcessResponse(**{
        "document_id": result["document_id"],
        "status": result["status"],
        "pages_extracted": result["pages_extracted"],
        "chunks_stored": result["chunks_stored"],
    })


@router.post("/documents/{document_id}/reprocess", response_model=DocumentProcessResponse)
def rag_reprocess_document(document_id: str, db: Session = Depends(get_db)):
    """Force re-ingest even if already processed."""
    doc = db.query(Document).filter(Document.id == parse_uuid(document_id)).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    if not os.path.exists(doc.file_path):
        raise HTTPException(400, "Stored file not found on disk")
    result = rag_service.ingest_document(
        db=db,
        document_id=str(doc.id),
        file_path_or_bytes=doc.file_path,
        filename=doc.filename,
        mime_type=doc.mime_type,
        reprocess=True,
    )
    return DocumentProcessResponse(**{
        "document_id": result["document_id"],
        "status": result["status"],
        "pages_extracted": result["pages_extracted"],
        "chunks_stored": result["chunks_stored"],
    })


@router.delete("/documents/{document_id}")
def rag_delete_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == parse_uuid(document_id)).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    # Delete file
    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except OSError:
            pass
    try:
        mongodb_manager.delete_document_chunks(str(doc.id))
    except Exception:
        pass
    db.delete(doc)
    db.commit()
    return {"message": "Document, chunks, and embeddings deleted", "document_id": document_id}


# ===========================================================================
# RESEARCH – QUERY (single-turn, no session persistence)
# ===========================================================================

@router.post("/query", response_model=RAGRetrieveResponse)
def rag_query(payload: RAGQueryRequest, db: Session = Depends(get_db)):
    """
    One-shot retrieval query (no session).
    Returns retrieved chunks without LLM generation.
    """
    result = rag_service.retrieve(
        db=db,
        query=payload.query,
        company_id=payload.company_id,
        financial_year=payload.financial_year,
        document_type=payload.document_type,
        top_k=payload.top_k,
        min_similarity=payload.min_similarity,
        hybrid=payload.hybrid,
        reranking=payload.reranking,
        vector_weight=payload.vector_weight,
        keyword_weight=payload.keyword_weight,
    )
    chunks = [ChunkResponse(**{
        "chunk_id": c["chunk_id"],
        "document_id": c["document_id"],
        "document_title": c.get("document_title", ""),
        "document_type": c.get("document_type"),
        "financial_year": c.get("financial_year"),
        "filename": c.get("filename"),
        "section": c.get("section"),
        "page_number": c.get("page_number"),
        "content": c["content"],
        "clean_text": c.get("clean_text"),
        "similarity_score": c.get("similarity_score", 0.0),
        "keyword_score": c.get("keyword_score", 0.0),
        "rerank_score": c.get("rerank_score"),
        "rrf_score": c.get("rrf_score"),
        "retrieval_method": c.get("retrieval_method"),
        "metadata": c.get("metadata"),
    }) for c in result["chunks"]]
    return RAGRetrieveResponse(
        query=result["query"],
        rewritten_query=result["rewritten_query"],
        route=result["route"],
        financial_year_hint=result["financial_year_hint"],
        retrieved_count=result["retrieved_count"],
        chunks=chunks,
        routing=result["routing"],
    )


# ===========================================================================
# RESEARCH – CHAT (full RAG with generation + session)
# ===========================================================================

@router.post("/chat", response_model=RAGChatResponse)
def rag_chat(payload: RAGChatRequest, db: Session = Depends(get_db)):
    """
    Full RAG chat pipeline: retrieval → LLM generation → citations → session.
    """
    comp_uuid = None
    if payload.company_id:
        comp_uuid = parse_uuid(payload.company_id)
        if not comp_uuid:
            c = db.query(Company).filter(
                Company.symbol == payload.company_id.upper()
            ).first()
            if c:
                comp_uuid = c.id

    # Create or fetch session
    sess_obj = None
    if payload.session_id:
        sess_obj = db.query(ResearchSession).filter(
            ResearchSession.id == parse_uuid(payload.session_id)
        ).first()
    if not sess_obj:
        title = payload.query[:60] + ("…" if len(payload.query) > 60 else "")
        sess_obj = ResearchSession(title=title, company_id=comp_uuid)
        db.add(sess_obj)
        db.commit()
        db.refresh(sess_obj)

    result = rag_service.research_chat(
        db=db,
        session_id=str(sess_obj.id),
        user_query=payload.query,
        company_id=str(comp_uuid) if comp_uuid else None,
        financial_year=payload.financial_year,
        document_type=payload.document_type,
        top_k=payload.top_k,
        hybrid=payload.hybrid,
        reranking=payload.reranking,
    )

    citations = [
        RAGCitationResponse(
            document_id=c.get("document_id"),
            document_chunk_id=c.get("document_chunk_id"),
            document_title=c.get("document_title"),
            page_number=c.get("page_number"),
            section=c.get("section"),
            excerpt=c.get("excerpt", ""),
            source_url=c.get("source_url"),
            confidence_score=float(c.get("confidence_score", 0.95)),
        )
        for c in result["citations"]
    ]

    return RAGChatResponse(
        message_id=result["message_id"],
        session_id=result["session_id"],
        role=result["role"],
        content=result["content"],
        message_type=result["message_type"],
        tokens_used=result["tokens_used"],
        retrieved_count=result["retrieved_count"],
        route=result["route"],
        citations=citations,
    )


@router.get("/sessions", response_model=List[ResearchSessionResponse])
def rag_list_sessions(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    sessions = (
        db.query(ResearchSession)
        .order_by(ResearchSession.updated_at.desc())
        .limit(limit)
        .all()
    )
    return [
        ResearchSessionResponse(
            id=str(s.id),
            title=s.title,
            company_id=str(s.company_id) if s.company_id else None,
            created_at=s.created_at,
            updated_at=s.updated_at,
            messages=[],
        )
        for s in sessions
    ]


@router.get("/sessions/{session_id}", response_model=ResearchSessionResponse)
def rag_get_session(session_id: str, db: Session = Depends(get_db)):
    session = db.query(ResearchSession).filter(
        ResearchSession.id == parse_uuid(session_id)
    ).first()
    if not session:
        raise HTTPException(404, "Session not found")
    msgs = []
    for msg in session.messages:
        citations = [
            CitationResponse(
                id=str(c.id),
                document_id=str(c.document_id),
                document_chunk_id=str(c.document_chunk_id) if c.document_chunk_id else None,
                document_title=c.document.title if c.document else "Filing",
                page_number=c.page_number,
                section=c.section,
                excerpt=c.excerpt,
                source_url=c.source_url,
                confidence_score=float(c.confidence_score or 0.95),
            )
            for c in msg.citations
        ]
        msgs.append(ResearchMessageResponse(
            id=str(msg.id),
            session_id=str(msg.session_id),
            role=msg.role,
            content=msg.content,
            message_type=msg.message_type,
            tokens_used=msg.token_count,
            citations=citations,
            created_at=msg.created_at,
        ))
    return ResearchSessionResponse(
        id=str(session.id),
        title=session.title,
        company_id=str(session.company_id) if session.company_id else None,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=msgs,
    )


# ===========================================================================
# RETRIEVAL – DEBUG INSPECTOR
# ===========================================================================

@router.post("/retrieve", response_model=RAGRetrieveResponse)
def rag_retrieve(payload: RAGRetrieveRequest, db: Session = Depends(get_db)):
    """Standalone retrieval without generation."""
    result = rag_service.retrieve(
        db=db,
        query=payload.query,
        company_id=payload.company_id,
        financial_year=payload.financial_year,
        document_type=payload.document_type,
        top_k=payload.top_k,
        min_similarity=payload.min_similarity,
        hybrid=payload.hybrid,
        reranking=payload.reranking,
        vector_weight=payload.vector_weight,
        keyword_weight=payload.keyword_weight,
    )
    chunks = [ChunkResponse(**{
        "chunk_id": c["chunk_id"],
        "document_id": c["document_id"],
        "document_title": c.get("document_title", ""),
        "document_type": c.get("document_type"),
        "financial_year": c.get("financial_year"),
        "filename": c.get("filename"),
        "section": c.get("section"),
        "page_number": c.get("page_number"),
        "content": c["content"],
        "clean_text": c.get("clean_text"),
        "similarity_score": c.get("similarity_score", 0.0),
        "keyword_score": c.get("keyword_score", 0.0),
        "rerank_score": c.get("rerank_score"),
        "rrf_score": c.get("rrf_score"),
        "retrieval_method": c.get("retrieval_method"),
        "metadata": c.get("metadata"),
    }) for c in result["chunks"]]
    return RAGRetrieveResponse(
        query=result["query"],
        rewritten_query=result["rewritten_query"],
        route=result["route"],
        financial_year_hint=result["financial_year_hint"],
        retrieved_count=result["retrieved_count"],
        chunks=chunks,
        routing=result["routing"],
    )


@router.post("/retrieve/debug")
def rag_retrieve_debug(payload: RAGRetrieveRequest, db: Session = Depends(get_db)):
    """
    Debug retrieval inspector: returns full pipeline trace including
    query routing, rewrite variants, individual semantic/keyword scores,
    and reranking details. Restricted to admin users in production.
    """
    t0 = time.monotonic()

    # Query routing
    routing = query_router.route(payload.query, company_hint=payload.company_id)

    # Embed
    t_emb = time.monotonic()
    q_vec = embedding_engine.generate_query_embedding(routing.rewritten_queries[0])
    emb_latency = round((time.monotonic() - t_emb) * 1000, 1)

    # Semantic-only
    t_ret = time.monotonic()
    from app.engines.rag.vector_store import vector_store
    semantic = vector_store.search_similar(
        db=db,
        query_embedding=q_vec,
        company_id=payload.company_id,
        financial_year=payload.financial_year,
        document_type=payload.document_type,
        top_k=payload.top_k * 2,
    )
    keyword = vector_store.keyword_search(
        db=db,
        query=routing.rewritten_queries[0],
        company_id=payload.company_id,
        financial_year=payload.financial_year,
        document_type=payload.document_type,
        top_k=payload.top_k * 2,
    )
    ret_latency = round((time.monotonic() - t_ret) * 1000, 1)

    # Hybrid
    hybrid_results = vector_store.hybrid_search(
        db=db,
        query=routing.rewritten_queries[0],
        query_embedding=q_vec,
        company_id=payload.company_id,
        financial_year=payload.financial_year,
        document_type=payload.document_type,
        top_k=payload.top_k,
        vector_weight=payload.vector_weight,
        keyword_weight=payload.keyword_weight,
    )

    total_latency = round((time.monotonic() - t0) * 1000, 1)

    return {
        "query": payload.query,
        "routing": {
            "route": routing.route.value,
            "confidence": routing.confidence,
            "rewrites": routing.rewritten_queries,
            "fy_hint": routing.financial_year_hint,
            "company_hint": routing.company_hint,
            "metric_hints": routing.metric_hints,
            "reasoning": routing.reasoning,
        },
        "latency_ms": {
            "embedding": emb_latency,
            "retrieval": ret_latency,
            "total": total_latency,
        },
        "semantic_results": [
            {
                "rank": i + 1,
                "chunk_id": c["chunk_id"],
                "document_title": c.get("document_title"),
                "section": c.get("section"),
                "page": c.get("page_number"),
                "similarity_score": c["similarity_score"],
                "content_preview": (c.get("clean_text") or c.get("content", ""))[:200],
            }
            for i, c in enumerate(semantic[:payload.top_k])
        ],
        "keyword_results": [
            {
                "rank": i + 1,
                "chunk_id": c["chunk_id"],
                "document_title": c.get("document_title"),
                "section": c.get("section"),
                "page": c.get("page_number"),
                "keyword_score": c["keyword_score"],
                "content_preview": (c.get("clean_text") or c.get("content", ""))[:200],
            }
            for i, c in enumerate(keyword[:payload.top_k])
        ],
        "hybrid_results": [
            {
                "rank": i + 1,
                "chunk_id": c["chunk_id"],
                "document_title": c.get("document_title"),
                "section": c.get("section"),
                "page": c.get("page_number"),
                "rrf_score": c.get("rrf_score", 0),
                "similarity_score": c.get("similarity_score", 0),
                "keyword_score": c.get("keyword_score", 0),
                "content_preview": (c.get("clean_text") or c.get("content", ""))[:200],
            }
            for i, c in enumerate(hybrid_results)
        ],
    }


# ===========================================================================
# ADMINISTRATION
# ===========================================================================

@router.get("/health", response_model=RAGHealthResponse)
def rag_health(db: Session = Depends(get_db)):
    db_health = check_database_health()
    model_info = embedding_engine.get_model_info()

    total_chunks = db.query(DocumentChunk).count()
    total_docs = db.query(Document).filter(Document.status == "PROCESSED").count()

    # Check hybrid search availability
    try:
        from rank_bm25 import BM25Okapi
        hybrid_ok = True
    except ImportError:
        hybrid_ok = False

    reranker = get_reranker()

    active_cfg = (
        db.query(RAGConfiguration)
        .filter(RAGConfiguration.is_active == True)
        .order_by(RAGConfiguration.created_at.desc())
        .first()
    )

    status = "healthy" if model_info.get("loaded") else "degraded"

    return RAGHealthResponse(
        status=status,
        embedding_engine=model_info,
        pgvector_available=db_health.get("pgvector_available", False),
        hybrid_search_available=hybrid_ok,
        reranker_available=reranker.is_available,
        total_chunks_indexed=total_chunks,
        total_documents_processed=total_docs,
        active_config_version=active_cfg.config_version if active_cfg else "default",
        mongodb=mongodb_manager.check_health(),
    )


@router.get("/metrics", response_model=RAGMetricsResponse)
def rag_metrics(db: Session = Depends(get_db)):
    total = db.query(Document).count()
    processed = db.query(Document).filter(Document.status == "PROCESSED").count()
    failed = db.query(Document).filter(Document.status == "FAILED").count()
    total_chunks = db.query(DocumentChunk).count()
    avg_chunks = round(total_chunks / processed, 1) if processed > 0 else 0.0
    last_doc = (
        db.query(Document)
        .filter(Document.status == "PROCESSED")
        .order_by(Document.updated_at.desc())
        .first()
    )
    return RAGMetricsResponse(
        total_documents=total,
        processed_documents=processed,
        failed_documents=failed,
        total_chunks=total_chunks,
        avg_chunks_per_document=avg_chunks,
        embedding_model=embedding_engine.model_name,
        embedding_dimension=embedding_engine.dimension,
        last_ingestion=last_doc.updated_at.isoformat() if last_doc else None,
    )


@router.get("/config", response_model=RAGConfigResponse)
def rag_get_config(db: Session = Depends(get_db)):
    cfg = (
        db.query(RAGConfiguration)
        .filter(RAGConfiguration.is_active == True)
        .order_by(RAGConfiguration.created_at.desc())
        .first()
    )
    if not cfg:
        # Create default
        cfg = RAGConfiguration()
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return RAGConfigResponse(
        id=str(cfg.id),
        config_version=cfg.config_version,
        is_active=cfg.is_active,
        embedding_model=cfg.embedding_model,
        embedding_dimension=cfg.embedding_dimension,
        embedding_batch_size=cfg.embedding_batch_size,
        embedding_device=cfg.embedding_device,
        chunk_strategy=cfg.chunk_strategy,
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
        max_chunk_size=cfg.max_chunk_size,
        min_chunk_size=cfg.min_chunk_size,
        table_aware_chunking=cfg.table_aware_chunking,
        semantic_chunking=cfg.semantic_chunking,
        parent_child_chunking=cfg.parent_child_chunking,
        retrieval_top_k=cfg.retrieval_top_k,
        min_similarity_score=float(cfg.min_similarity_score),
        hybrid_search_enabled=cfg.hybrid_search_enabled,
        vector_weight=float(cfg.vector_weight),
        keyword_weight=float(cfg.keyword_weight),
        rrf_k=cfg.rrf_k,
        reranking_enabled=cfg.reranking_enabled,
        reranking_model=cfg.reranking_model,
        reranking_top_k=cfg.reranking_top_k,
        llm_provider=cfg.llm_provider,
        llm_model=cfg.llm_model,
        llm_temperature=float(cfg.llm_temperature),
        llm_max_tokens=cfg.llm_max_tokens,
        require_citations=cfg.require_citations,
        description=cfg.description,
        created_at=cfg.created_at,
        updated_at=cfg.updated_at,
    )


@router.put("/config", response_model=RAGConfigResponse)
def rag_update_config(payload: RAGConfigUpdateRequest, db: Session = Depends(get_db)):
    """
    Save a new versioned RAG configuration.
    Deactivates the previous active configuration.
    NOTE: Changing embedding_model/dimension requires re-embedding all documents.
    """
    current = (
        db.query(RAGConfiguration)
        .filter(RAGConfiguration.is_active == True)
        .order_by(RAGConfiguration.created_at.desc())
        .first()
    )

    # Warn if embedding model/dimension changes
    if (
        current
        and payload.embedding_model
        and payload.embedding_model != current.embedding_model
    ):
        # We create a new config version but don't auto-reprocess
        pass

    if current:
        current.is_active = False
        db.commit()

    # Compute new version
    from datetime import datetime
    version = f"v{datetime.utcnow().strftime('%Y%m%d%H%M')}"

    new_cfg = RAGConfiguration(
        config_version=version,
        is_active=True,
        embedding_model=payload.embedding_model or (current.embedding_model if current else "BAAI/bge-base-en-v1.5"),
        embedding_dimension=payload.embedding_dimension or (current.embedding_dimension if current else 768),
        chunk_size=payload.chunk_size or (current.chunk_size if current else 600),
        chunk_overlap=payload.chunk_overlap or (current.chunk_overlap if current else 100),
        retrieval_top_k=payload.retrieval_top_k or (current.retrieval_top_k if current else 8),
        min_similarity_score=payload.min_similarity_score if payload.min_similarity_score is not None else (float(current.min_similarity_score) if current else 0.0),
        hybrid_search_enabled=payload.hybrid_search_enabled if payload.hybrid_search_enabled is not None else (current.hybrid_search_enabled if current else True),
        vector_weight=payload.vector_weight if payload.vector_weight is not None else (float(current.vector_weight) if current else 0.6),
        keyword_weight=payload.keyword_weight if payload.keyword_weight is not None else (float(current.keyword_weight) if current else 0.4),
        reranking_enabled=payload.reranking_enabled if payload.reranking_enabled is not None else (current.reranking_enabled if current else False),
        reranking_model=payload.reranking_model or (current.reranking_model if current else "BAAI/bge-reranker-base"),
        reranking_top_k=payload.reranking_top_k or (current.reranking_top_k if current else 5),
        llm_provider=payload.llm_provider or (current.llm_provider if current else "gemini"),
        llm_model=payload.llm_model or (current.llm_model if current else "gemini-1.5-flash"),
        llm_temperature=payload.llm_temperature if payload.llm_temperature is not None else (float(current.llm_temperature) if current else 0.1),
        llm_max_tokens=payload.llm_max_tokens or (current.llm_max_tokens if current else 2048),
        description=(
            payload.description
            if payload.description is not None
            else current.description if current else None
        ),
        created_by="admin",
    )
    db.add(new_cfg)
    db.commit()
    db.refresh(new_cfg)

    return rag_get_config(db)


@router.post("/index/rebuild")
def rag_rebuild_index(
    company_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Re-embed and re-index all PROCESSED documents.
    Expensive operation – run only when changing embedding models.
    """
    q = db.query(Document).filter(Document.status == "PROCESSED")
    if company_id:
        q = q.filter(Document.company_id == parse_uuid(company_id))
    docs = q.all()

    reprocessed = 0
    failed = 0
    for doc in docs:
        if not doc.file_path or not os.path.exists(doc.file_path):
            failed += 1
            continue
        try:
            rag_service.ingest_document(
                db=db,
                document_id=str(doc.id),
                file_path_or_bytes=doc.file_path,
                filename=doc.filename,
                mime_type=doc.mime_type,
                reprocess=True,
            )
            reprocessed += 1
        except Exception as exc:
            failed += 1

    return {
        "message": f"Index rebuild complete",
        "documents_reprocessed": reprocessed,
        "documents_failed": failed,
    }


@router.post("/embeddings/rebuild")
def rag_rebuild_embeddings(
    document_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Re-embed a specific document or all documents."""
    if document_id:
        doc = db.query(Document).filter(Document.id == parse_uuid(document_id)).first()
        if not doc:
            raise HTTPException(404, "Document not found")
        if not os.path.exists(doc.file_path):
            raise HTTPException(400, "File not on disk")
        rag_service.ingest_document(
            db=db, document_id=str(doc.id),
            file_path_or_bytes=doc.file_path,
            filename=doc.filename, mime_type=doc.mime_type,
            reprocess=True,
        )
        return {"message": "Document re-embedded", "document_id": document_id}
    return rag_rebuild_index(db=db)


# ===========================================================================
# EVALUATION
# ===========================================================================

@router.post("/evaluation/run", response_model=RAGEvaluationResponse)
def rag_run_evaluation(db: Session = Depends(get_db)):
    """
    Run built-in retrieval evaluation on a fixed test set.
    Tests: FY retrieval, company retrieval, table retrieval, cross-year, missing info.
    """
    from app.engines.rag.evaluation import run_retrieval_evaluation
    result = run_retrieval_evaluation(db)
    return RAGEvaluationResponse(
        status=result["status"],
        queries_evaluated=result["queries_evaluated"],
        metrics=EvaluationMetrics(**result["metrics"]),
        details=result.get("details"),
    )


@router.get("/evaluation/results", response_model=RAGEvaluationResponse)
def rag_get_evaluation_results(db: Session = Depends(get_db)):
    """Return the most recent evaluation results (run /evaluation/run first)."""
    from app.engines.rag.evaluation import get_last_evaluation_results
    result = get_last_evaluation_results()
    return RAGEvaluationResponse(
        status=result["status"],
        queries_evaluated=result["queries_evaluated"],
        metrics=EvaluationMetrics(**result["metrics"]),
        details=result.get("details"),
    )
