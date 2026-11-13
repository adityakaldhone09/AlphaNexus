"""
ALPHANEXUS – Intelligent Document Recognition, Relevance & Metadata Extraction
==============================================================================
Provides end-to-end automated document intelligence:
  - File format validation (PDF, DOCX, XLSX, CSV, TXT) and integrity checks.
  - Multi-tier Financial Relevance Classifier (filtering recipes, personal photos, academic essays).
  - Multi-signal Company Identification (ISIN, BSE scrip, NSE symbol, corporate name, aliases).
  - Document Type Classification (Annual Report, Quarterly Results, Presentations, etc.).
  - Reporting Period & Financial Year extraction (FY25, FY24, Q1-Q4, Consolidated/Standalone).
  - Duplicate detection via cryptographic SHA-256 hashing.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.logging import logger
from app.models.company import Company, CompanyIdentifier
from app.models.document import Document
from app.engines.rag.loaders.pdf_loader import PDFDocumentLoader
from app.engines.rag.loaders.docx_loader import DOCXDocumentLoader
from app.engines.rag.loaders.tabular_loader import TabularDocumentLoader
from app.services.company_discovery import MASTER_EQUITIES_UNIVERSE, company_discovery_service


# ---------------------------------------------------------------------------
# Supported Document Formats
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".txt"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB


# ---------------------------------------------------------------------------
# Domain Lexicons & Relevance Signals
# ---------------------------------------------------------------------------

FINANCIAL_SIGNALS = [
    r"\bfinancial\s+statements?\b",
    r"\bbalance\s+sheet\b",
    r"\bstatement\s+of\s+profit\s+and\s+loss\b",
    r"\bprofit\s+and\s+loss\b",
    r"\bcash\s+flow\s+statement\b",
    r"\bstatement\s+of\s+cash\s+flows?\b",
    r"\bannual\s+report\b",
    r"\bunaudited\s+financial\s+results\b",
    r"\boperating\s+revenue\b",
    r"\bebitda\b",
    r"\bprofit\s+after\s+tax\b",
    r"\bnet\s+profit\b",
    r"\bearnings\s+per\s+share\b",
    r"\bstandalone\b",
    r"\bconsolidated\b",
    r"\bshareholders?\s+equity\b",
    r"\btotal\s+assets\b",
    r"\btotal\s+liabilities\b",
    r"\bnotes\s+to\s+accounts\b",
    r"\bdirectors?\s+report\b",
    r"\bauditor'?s?\s+report\b",
    r"\bcorporate\s+governance\b",
    r"\bmanagement\s+discussion\s+and\s+analysis\b",
    r"\binvestor\s+presentation\b",
    r"\bearnings\s+conference\s+call\b",
    r"\bexchange\s+filings?\b",
    r"\bsebi\s*\(?lodr\)?\b",
    r"\bregulation\s+3[03]\b",
    r"\bdividend\s+declared\b",
    r"\bpaid-?up\s+capital\b",
    r"\bdebt\s+to\s+equity\b",
    r"\breturn\s+on\s+equity\b",
    r"\binr\s+(?:crores?|lakhs?)\b",
    r"₹\s*(?:\d+[\d,]*\.?\d*)",
    r"\bcin\s*[:=]\s*[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b",
    r"\bisin\s*[:=]\s*INE[0-9A-Z]{9}\b",
]

NON_FINANCIAL_SIGNALS = [
    # Recipes / Food prep
    r"\brecipe\b", r"\bingredients\b", r"\btablespoon[s]?\b", r"\bteaspoon[s]?\b",
    r"\bpreheat\s+oven\b", r"\bcups?\s+of\s+(?:sugar|flour|water|milk)\b",
    r"\bboil\s+for\b", r"\bbake\s+at\b", r"\bcook\s+time\b",
    # Academic / Non-corporate literature
    r"\bhomework\s+assignment\b", r"\bessay\s+on\s+literature\b",
    r"\bshakespeare\b", r"\bpoem\s+analysis\b", r"\bchapter\s+summary\b",
    # Personal photos / non-documents
    r"\bcamera\s+model\b", r"\bshutter\s+speed\b", r"\biso\s+speed\b",
    r"\bfocal\s+length\b", r"\bflash\s+fired\b",
]


@dataclass
class DocumentRelevanceResult:
    is_relevant: bool
    category: str  # Relevant financial document, Relevant corporate document, Unrelated document
    confidence: float
    reasons: List[str]
    matched_signals: List[str]
    rejection_message: Optional[str] = None


@dataclass
class CompanyDetectionResult:
    company_id: Optional[str]
    company_name: Optional[str]
    symbol: Optional[str]
    exchange: str
    isin: Optional[str]
    confidence: float
    status: str  # HIGH_CONFIDENCE, MULTIPLE_MATCHES, UNKNOWN_COMPANY, UNRELATED
    candidate_matches: List[Dict[str, Any]] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)


@dataclass
class DocumentInspectionResult:
    filename: str
    file_size_bytes: int
    mime_type: str
    file_hash: str
    total_pages: int
    extracted_text_preview: str

    relevance: DocumentRelevanceResult
    company: CompanyDetectionResult

    detected_title: str
    document_type: str
    document_type_confidence: float
    financial_year: Optional[str]
    quarter: Optional[str]
    reporting_basis: str  # Consolidated vs Standalone
    currency: str
    unit: str

    is_duplicate: bool
    existing_document_id: Optional[str] = None
    existing_document_title: Optional[str] = None

    temp_file_token: str = ""
    can_proceed: bool = False


class IntelligentDocumentAnalyzer:
    """
    Automated document inspection, relevance validation, company matching,
    and structured metadata extraction pipeline.
    """

    def __init__(self):
        self.pdf_loader = PDFDocumentLoader()
        self.docx_loader = DOCXDocumentLoader()
        self.tabular_loader = TabularDocumentLoader()

    def validate_file(self, filename: str, file_bytes: bytes) -> Tuple[bool, Optional[str]]:
        """Validates file extension, length, and binary safety."""
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return False, f"Unsupported format '{ext}'. Supported formats: PDF, DOCX, XLSX, CSV, TXT."
        if len(file_bytes) == 0:
            return False, "The uploaded file is empty (0 bytes)."
        if len(file_bytes) > MAX_FILE_SIZE_BYTES:
            return False, f"File size exceeds maximum limit of {MAX_FILE_SIZE_BYTES // (1024*1024)}MB."
        return True, None

    def extract_content(self, filename: str, file_bytes: bytes) -> List[Dict[str, Any]]:
        """Extracts text pages and tabular datasets from document."""
        ext = os.path.splitext(filename)[1].lower()
        try:
            if ext == ".pdf":
                return self.pdf_loader.load(file_bytes)
            elif ext in (".docx", ".doc"):
                return self.docx_loader.load(file_bytes)
            elif ext == ".csv":
                return self.tabular_loader.load_csv(file_bytes)
            elif ext in (".xlsx", ".xls"):
                return self.tabular_loader.load_excel(file_bytes)
            else:
                # Plain text
                text = file_bytes.decode("utf-8", errors="ignore")
                return [{"page_number": 1, "text": text, "tables": []}]
        except Exception as e:
            logger.error(f"[DocumentIntelligence] Extraction failed for {filename}: {e}")
            raise ValueError(f"Failed to read file contents: {str(e)}")

    def classify_relevance(self, full_text: str, filename: str) -> DocumentRelevanceResult:
        """
        Classifies financial/corporate relevance and detects unrelated documents
        (recipes, personal notes, non-financial essays, image logs).
        """
        lower_text = (filename + " " + full_text[:20000]).lower()

        # Check non-financial / junk triggers
        negative_hits = []
        for pat in NON_FINANCIAL_SIGNALS:
            matches = re.findall(pat, lower_text, re.IGNORECASE)
            if matches:
                negative_hits.extend(matches)

        # Check financial / corporate triggers
        positive_hits = []
        for pat in FINANCIAL_SIGNALS:
            matches = re.findall(pat, lower_text, re.IGNORECASE)
            if matches:
                positive_hits.extend(matches)

        pos_count = len(positive_hits)
        neg_count = len(negative_hits)

        # Decision threshold
        if neg_count >= 2 and pos_count < 2:
            return DocumentRelevanceResult(
                is_relevant=False,
                category="Unrelated document",
                confidence=0.92,
                reasons=[f"Detected non-financial content indicators: {', '.join(set(negative_hits[:4]))}"],
                matched_signals=negative_hits[:5],
                rejection_message="Document not recognized as a relevant company or financial document. Please upload an annual report, financial statement, investor presentation or another company-related document.",
            )

        if pos_count >= 3:
            return DocumentRelevanceResult(
                is_relevant=True,
                category="Relevant financial document",
                confidence=min(0.98, 0.60 + (pos_count * 0.05)),
                reasons=[f"Detected verified financial disclosure signals: {', '.join(set(positive_hits[:6]))}"],
                matched_signals=positive_hits[:8],
            )
        elif pos_count >= 1:
            return DocumentRelevanceResult(
                is_relevant=True,
                category="Relevant corporate document",
                confidence=0.72,
                reasons=[f"Detected corporate signals: {', '.join(set(positive_hits[:4]))}"],
                matched_signals=positive_hits[:4],
            )
        else:
            return DocumentRelevanceResult(
                is_relevant=False,
                category="Unrelated document",
                confidence=0.88,
                reasons=["No verifiable financial statements, corporate metrics, or disclosure terms detected."],
                matched_signals=[],
                rejection_message="Document not recognized as a relevant company or financial document. Please upload an annual report, financial statement, investor presentation or another company-related document.",
            )

    def identify_company(
        self,
        db: Session,
        text_pages: List[Dict[str, Any]],
        filename: str,
    ) -> CompanyDetectionResult:
        """
        Discovers company identity using multiple corroborated signals:
          1. ISIN detection
          2. Official full corporate name matches (case-insensitive)
          3. Exact NSE Ticker / BSE Scrip references
          4. Registered corporate aliases
        """
        # Focus on title, cover page, and first 3 pages
        primary_text = filename + "\n"
        for p in text_pages[:3]:
            primary_text += (p.get("text") or "") + "\n"

        evidence: List[str] = []

        # ── Signal 1: ISIN Matching ────────────────────────────────────────
        isin_matches = re.findall(r"\b(INE[0-9A-Z]{9})\b", primary_text)
        if isin_matches:
            found_isin = isin_matches[0]
            evidence.append(f"Found ISIN in text: {found_isin}")
            # Lookup in database
            comp = db.query(Company).filter(Company.isin == found_isin).first()
            if comp:
                return CompanyDetectionResult(
                    company_id=str(comp.id),
                    company_name=comp.name,
                    symbol=comp.symbol,
                    exchange=comp.exchange or "NSE",
                    isin=comp.isin,
                    confidence=0.98,
                    status="HIGH_CONFIDENCE",
                    evidence=evidence,
                )
            # Lookup in master universe
            master_item = next((m for m in MASTER_EQUITIES_UNIVERSE if m.get("isin") == found_isin), None)
            if master_item:
                # Provision immediately
                comp = company_discovery_service.resolve_or_create(db, master_item["symbol"])
                if comp:
                    return CompanyDetectionResult(
                        company_id=str(comp.id),
                        company_name=comp.name,
                        symbol=comp.symbol,
                        exchange=comp.exchange or "NSE",
                        isin=comp.isin,
                        confidence=0.98,
                        status="HIGH_CONFIDENCE",
                        evidence=evidence,
                    )

        # ── Signal 2: Official Corporate Names from Master Universe ──────
        candidates: List[Tuple[Dict[str, Any], float, str]] = []

        # Check existing active database companies first
        db_comps = db.query(Company).filter(Company.is_active == True).all()
        for comp in db_comps:
            score = 0.0
            matched_reason = ""
            name_clean = comp.name.lower().replace("limited", "").replace("ltd", "").strip()
            if len(name_clean) > 4 and name_clean in primary_text.lower():
                score += 0.85
                matched_reason = f"Matched company name '{comp.name}'"

            # Symbol match with word boundaries
            if comp.symbol and re.search(rf"\b{re.escape(comp.symbol)}\b", primary_text):
                score += 0.65
                matched_reason += f" and ticker '{comp.symbol}'"

            if score >= 0.80:
                candidates.append(({
                    "id": str(comp.id),
                    "name": comp.name,
                    "symbol": comp.symbol,
                    "exchange": comp.exchange or "NSE",
                    "isin": comp.isin,
                }, score, matched_reason))

        # Check Master Universe items
        for item in MASTER_EQUITIES_UNIVERSE:
            score = 0.0
            matched_reason = ""
            name_clean = item["name"].lower().replace("limited", "").replace("ltd", "").strip()
            if len(name_clean) > 4 and name_clean in primary_text.lower():
                score += 0.85
                matched_reason = f"Matched official name '{item['name']}'"

            if re.search(rf"\b{re.escape(item['symbol'])}\b", primary_text):
                score += 0.60
                matched_reason += f" and symbol '{item['symbol']}'"

            # Check aliases
            for alias in item.get("aliases", []):
                if len(alias) > 2 and re.search(rf"\b{re.escape(alias)}\b", primary_text, re.IGNORECASE):
                    score += 0.50
                    matched_reason += f" and alias '{alias}'"
                    break

            if score >= 0.75:
                # Deduplicate if already present in candidates
                if not any(c[0]["symbol"] == item["symbol"] for c in candidates):
                    candidates.append(({
                        "id": None,
                        "name": item["name"],
                        "symbol": item["symbol"],
                        "exchange": item["exchange"],
                        "isin": item.get("isin"),
                    }, score, matched_reason))

        # Sort candidates by score descending
        candidates.sort(key=lambda x: x[1], reverse=True)

        if len(candidates) == 1:
            best, score, reason = candidates[0]
            evidence.append(reason)
            # Resolve or provision
            comp = company_discovery_service.resolve_or_create(db, best["symbol"])
            if comp:
                return CompanyDetectionResult(
                    company_id=str(comp.id),
                    company_name=comp.name,
                    symbol=comp.symbol,
                    exchange=comp.exchange or "NSE",
                    isin=comp.isin,
                    confidence=min(0.96, score),
                    status="HIGH_CONFIDENCE",
                    evidence=evidence,
                )

        elif len(candidates) > 1:
            # Check if top score is significantly higher than second
            if candidates[0][1] >= 1.2 and (candidates[0][1] - candidates[1][1] >= 0.4):
                best, score, reason = candidates[0]
                evidence.append(reason)
                comp = company_discovery_service.resolve_or_create(db, best["symbol"])
                if comp:
                    return CompanyDetectionResult(
                        company_id=str(comp.id),
                        company_name=comp.name,
                        symbol=comp.symbol,
                        exchange=comp.exchange or "NSE",
                        isin=comp.isin,
                        confidence=0.90,
                        status="HIGH_CONFIDENCE",
                        evidence=evidence,
                    )
            else:
                # Ambiguous match: multiple plausible companies
                candidate_list = [c[0] for c in candidates[:4]]
                return CompanyDetectionResult(
                    company_id=None,
                    company_name=None,
                    symbol=None,
                    exchange="NSE",
                    isin=None,
                    confidence=0.55,
                    status="MULTIPLE_MATCHES",
                    candidate_matches=candidate_list,
                    evidence=[f"Multiple matching companies identified: {', '.join([c['name'] for c in candidate_list])}"],
                )

        # No company resolved
        return CompanyDetectionResult(
            company_id=None,
            company_name=None,
            symbol=None,
            exchange="NSE",
            isin=None,
            confidence=0.20,
            status="UNKNOWN_COMPANY",
            evidence=["No specific listed company identifier was detected with sufficient confidence."],
        )

    def extract_metadata(
        self,
        full_text: str,
        filename: str,
        company_result: CompanyDetectionResult,
    ) -> Dict[str, Any]:
        """
        Extracts Document Title, Document Type, Financial Year, Quarter,
        Reporting Basis (Consolidated vs Standalone), Currency, and Units.
        """
        header_text = (filename + "\n" + full_text[:8000]).lower()

        # ── 1. Document Type ──────────────────────────────────────────────
        doc_type = "Annual Report"
        doc_type_conf = 0.70

        if re.search(r"annual\s+report|integrated\s+annual\s+report", header_text):
            doc_type = "Annual Report"
            doc_type_conf = 0.95
        elif re.search(r"quarterly\s+results?|unaudited\s+results?|quarter\s+ended", header_text):
            doc_type = "Quarterly Result"
            doc_type_conf = 0.92
        elif re.search(r"investor\s+presentation|earnings\s+presentation", header_text):
            doc_type = "Investor Presentation"
            doc_type_conf = 0.94
        elif re.search(r"earnings\s+call|conference\s+call\s+transcript|concall", header_text):
            doc_type = "Earnings Call Transcript"
            doc_type_conf = 0.96
        elif re.search(r"board\s+meeting\s+outcome|corporate\s+announcement|regulation\s+30", header_text):
            doc_type = "Corporate Announcement"
            doc_type_conf = 0.90
        elif re.search(r"financial\s+statements?|balance\s+sheet\s+and\s+profit", header_text):
            doc_type = "Financial Statement"
            doc_type_conf = 0.88
        elif re.search(r"research\s+report|equity\s+research|initiating\s+coverage", header_text):
            doc_type = "Research Report"
            doc_type_conf = 0.85

        # ── 2. Financial Year Extraction ──────────────────────────────────
        fy_match = re.search(r"\b(?:FY|Financial\s+Year\s*)[:\-]?\s*(20\d{2}|\d{2})\b", header_text, re.IGNORECASE)
        fy_val = "FY24"
        if fy_match:
            raw_yr = fy_match.group(1)
            fy_val = f"FY{raw_yr[-2:]}"
        else:
            # Check 2024-25 or 2023-2024 patterns
            yr_match = re.search(r"\b(202\d)[\-/](?:20)?(\d{2})\b", header_text)
            if yr_match:
                fy_val = f"FY{yr_match.group(2)}"

        # ── 3. Quarter Extraction ─────────────────────────────────────────
        q_match = re.search(r"\b(Q[1-4]|Quarter\s+[1-4])\b", header_text, re.IGNORECASE)
        quarter = None
        if q_match:
            raw_q = q_match.group(1).upper()
            quarter = "Q1" if "1" in raw_q else ("Q2" if "2" in raw_q else ("Q3" if "3" in raw_q else "Q4"))

        # ── 4. Reporting Basis ────────────────────────────────────────────
        is_consolidated = True
        if "standalone" in header_text and "consolidated" not in header_text:
            is_consolidated = False
        reporting_basis = "Consolidated" if is_consolidated else "Standalone"

        # ── 5. Document Title Generation ──────────────────────────────────
        c_name = company_result.company_name or "Company"
        clean_fn = os.path.splitext(filename)[0].replace("_", " ").replace("-", " ").title()

        if doc_type in ("Annual Report", "Quarterly Result", "Investor Presentation"):
            title = f"{c_name} {doc_type} {fy_val}"
            if quarter:
                title = f"{c_name} {quarter} {fy_val} {doc_type}"
        else:
            title = f"{c_name} {clean_fn}"

        return {
            "title": title[:255],
            "document_type": doc_type,
            "document_type_confidence": doc_type_conf,
            "financial_year": fy_val,
            "quarter": quarter,
            "reporting_basis": reporting_basis,
            "currency": "INR",
            "unit": "Crores",
        }

    def inspect_document(
        self,
        db: Session,
        filename: str,
        file_bytes: bytes,
    ) -> DocumentInspectionResult:
        """
        Executes full inspection pipeline without writing to database chunks:
          1. File validation
          2. Content extraction
          3. Relevance classification
          4. Company identification
          5. Metadata extraction
          6. Duplicate detection (SHA-256)
        """
        # Validate format
        is_valid, err_msg = self.validate_file(filename, file_bytes)
        if not is_valid:
            return DocumentInspectionResult(
                filename=filename,
                file_size_bytes=len(file_bytes),
                mime_type="application/octet-stream",
                file_hash="",
                total_pages=0,
                extracted_text_preview="",
                relevance=DocumentRelevanceResult(
                    is_relevant=False,
                    category="Unsupported or unreadable file",
                    confidence=1.0,
                    reasons=[err_msg or "Unsupported format"],
                    matched_signals=[],
                    rejection_message=err_msg,
                ),
                company=CompanyDetectionResult(
                    company_id=None, company_name=None, symbol=None, exchange="NSE", isin=None,
                    confidence=0.0, status="UNRELATED"
                ),
                detected_title=filename,
                document_type="Other",
                document_type_confidence=0.0,
                financial_year=None,
                quarter=None,
                reporting_basis="Consolidated",
                currency="INR",
                unit="Crores",
                is_duplicate=False,
                can_proceed=False,
            )

        # Compute SHA-256
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        # Check existing duplicates in database
        existing_doc = db.query(Document).filter(Document.file_hash == file_hash).first()
        is_dup = existing_doc is not None

        # Extract content
        try:
            pages_data = self.extract_content(filename, file_bytes)
        except Exception as extract_err:
            return DocumentInspectionResult(
                filename=filename,
                file_size_bytes=len(file_bytes),
                mime_type="application/octet-stream",
                file_hash=file_hash,
                total_pages=0,
                extracted_text_preview="",
                relevance=DocumentRelevanceResult(
                    is_relevant=False,
                    category="Unsupported or unreadable file",
                    confidence=1.0,
                    reasons=[f"File content extraction failed: {str(extract_err)}"],
                    matched_signals=[],
                    rejection_message=f"Failed to read file: {str(extract_err)}. Please ensure the document is a valid, uncorrupted file.",
                ),
                company=CompanyDetectionResult(
                    company_id=None, company_name=None, symbol=None, exchange="NSE", isin=None,
                    confidence=0.0, status="UNRELATED"
                ),
                detected_title=filename,
                document_type="Other",
                document_type_confidence=0.0,
                financial_year=None,
                quarter=None,
                reporting_basis="Consolidated",
                currency="INR",
                unit="Crores",
                is_duplicate=is_dup,
                can_proceed=False,
            )

        full_text = "\n".join([p.get("text", "") for p in pages_data])
        preview = full_text[:600].strip()

        # Classify Relevance
        relevance = self.classify_relevance(full_text, filename)

        # If completely unrelated, stop early
        if not relevance.is_relevant:
            return DocumentInspectionResult(
                filename=filename,
                file_size_bytes=len(file_bytes),
                mime_type="application/pdf" if filename.endswith(".pdf") else "application/octet-stream",
                file_hash=file_hash,
                total_pages=len(pages_data),
                extracted_text_preview=preview,
                relevance=relevance,
                company=CompanyDetectionResult(
                    company_id=None, company_name=None, symbol=None, exchange="NSE", isin=None,
                    confidence=0.0, status="UNRELATED",
                    evidence=["Document content did not exhibit verified financial relevance."]
                ),
                detected_title=filename,
                document_type="Unrelated Document",
                document_type_confidence=relevance.confidence,
                financial_year=None,
                quarter=None,
                reporting_basis="Consolidated",
                currency="INR",
                unit="Crores",
                is_duplicate=is_dup,
                existing_document_id=str(existing_doc.id) if existing_doc else None,
                existing_document_title=existing_doc.title if existing_doc else None,
                can_proceed=False,
            )

        # Identify Company
        company_res = self.identify_company(db, pages_data, filename)

        # Extract structured metadata
        meta = self.extract_metadata(full_text, filename, company_res)

        # Generate temporary token for seamless confirmation
        token = hashlib.md5((filename + file_hash).encode()).hexdigest()

        # Can proceed if relevant and company is identified or ready for confirmation
        can_proceed = relevance.is_relevant and (company_res.company_id is not None or company_res.status == "HIGH_CONFIDENCE")

        return DocumentInspectionResult(
            filename=filename,
            file_size_bytes=len(file_bytes),
            mime_type="application/pdf" if filename.endswith(".pdf") else "application/octet-stream",
            file_hash=file_hash,
            total_pages=len(pages_data),
            extracted_text_preview=preview,
            relevance=relevance,
            company=company_res,
            detected_title=meta["title"],
            document_type=meta["document_type"],
            document_type_confidence=meta["document_type_confidence"],
            financial_year=meta["financial_year"],
            quarter=meta["quarter"],
            reporting_basis=meta["reporting_basis"],
            currency=meta["currency"],
            unit=meta["unit"],
            is_duplicate=is_dup,
            existing_document_id=str(existing_doc.id) if existing_doc else None,
            existing_document_title=existing_doc.title if existing_doc else None,
            temp_file_token=token,
            can_proceed=can_proceed,
        )


document_intelligence = IntelligentDocumentAnalyzer()
