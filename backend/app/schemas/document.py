from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, UUID4, ConfigDict


class DocumentBase(BaseModel):
    title: str
    financial_year: Optional[str] = None
    document_type: str = "Annual Report"


class DocumentResponse(DocumentBase):
    id: UUID4
    company_id: UUID4
    company_name: Optional[str] = None
    company_symbol: Optional[str] = None
    user_id: Optional[UUID4] = None
    filename: str
    file_size_bytes: int
    mime_type: str
    status: str
    error_message: Optional[str] = None
    total_pages: int
    total_chunks: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentUploadResponse(BaseModel):
    document_id: UUID4
    title: str
    filename: str
    status: str
    message: str
    company_id: Optional[UUID4] = None
    company_symbol: Optional[str] = None
    chunks_stored: Optional[int] = 0


class DocumentProcessResponse(BaseModel):
    document_id: str
    status: str
    pages_extracted: int
    chunks_stored: int
    message: Optional[str] = None


class DocumentCandidateCompany(BaseModel):
    id: Optional[str] = None
    name: str
    symbol: str
    exchange: str = "NSE"
    isin: Optional[str] = None


class DocumentAnalysisResponse(BaseModel):
    filename: str
    file_size_bytes: int
    file_hash: str
    mime_type: str
    total_pages: int
    extracted_text_preview: str

    # Relevance & classification
    is_relevant: bool
    relevance_category: str
    relevance_confidence: float
    relevance_reasons: List[str]
    rejection_message: Optional[str] = None

    # Company identification
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    company_symbol: Optional[str] = None
    exchange: str = "NSE"
    isin: Optional[str] = None
    company_confidence: float = 0.0
    company_identification_status: str = "UNKNOWN_COMPANY"
    candidate_matches: List[DocumentCandidateCompany] = []
    company_evidence: List[str] = []

    # Metadata
    detected_title: str
    document_type: str
    document_type_confidence: float
    financial_year: Optional[str] = "FY24"
    quarter: Optional[str] = None
    reporting_basis: str = "Consolidated"
    currency: str = "INR"
    unit: str = "Crores"

    # Duplication
    is_duplicate: bool = False
    existing_document_id: Optional[str] = None
    existing_document_title: Optional[str] = None

    # Workflow token & status
    temp_file_token: str
    can_proceed: bool


class DocumentConfirmRequest(BaseModel):
    temp_file_token: str
    company_id: Optional[str] = None
    company_symbol: Optional[str] = None
    title: Optional[str] = None
    financial_year: Optional[str] = None
    document_type: Optional[str] = None
    quarter: Optional[str] = None
    auto_process: bool = True
