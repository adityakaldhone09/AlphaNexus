import os
import uuid
import shutil
import glob
import hashlib
import json
from typing import List, Optional, Dict, Any, Tuple
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.config import settings
from app.core.database import get_db, parse_uuid
from app.models.document import Document
from app.models.company import Company
from app.engines.rag.service import rag_service
from app.engines.rag.document_intelligence import document_intelligence
from app.services.supabase_storage import supabase_storage
from app.services.company_discovery import company_discovery_service
from app.database.mongodb import mongodb_manager
from app.schemas.document import (
    DocumentResponse,
    DocumentUploadResponse,
    DocumentProcessResponse,
    DocumentAnalysisResponse,
    DocumentConfirmRequest,
    DocumentCandidateCompany,
)

router = APIRouter()

STAGING_DIR = os.path.join(os.getcwd(), "uploads", "staging")
os.makedirs(STAGING_DIR, exist_ok=True)


def _get_staged_file(token: str) -> Optional[Tuple[str, str]]:
    """Locates a staged file by its token. Returns (filepath, original_filename)."""
    matches = glob.glob(os.path.join(STAGING_DIR, f"{token}_*"))
    if not matches:
        return None
    filepath = matches[0]
    filename = os.path.basename(filepath)[len(token) + 1 :]
    return filepath, filename


@router.post("/analyze", response_model=DocumentAnalysisResponse)
async def analyze_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    Frictionless Document Inspection & Recognition:
      1. Validates format (PDF, DOCX, XLSX, CSV, TXT) and safety.
      2. Multi-tier Financial Relevance Classifier (filters recipes, personal photos, essays).
      3. Automatic Company Identification (ISIN, BSE scrip, NSE ticker, official trade names, aliases).
      4. Metadata Extraction (Title, Document Type, FY, Quarter, Reporting basis).
      5. Duplicate detection (SHA-256).
    Does NOT require the user to pre-fill company, title, or financial year.
    """
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty (0 bytes).")

    # Run complete inspection pipeline
    inspection = document_intelligence.inspect_document(
        db=db,
        filename=file.filename,
        file_bytes=contents,
    )

    # If document is relevant or under review, stage file for confirmation
    if inspection.relevance.is_relevant or inspection.can_proceed:
        staged_path = os.path.join(STAGING_DIR, f"{inspection.temp_file_token}_{file.filename}")
        with open(staged_path, "wb") as f:
            f.write(contents)
        meta_path = os.path.join(STAGING_DIR, f"{inspection.temp_file_token}.meta.json")
        with open(meta_path, "w") as f:
            json.dump({
                "company_id": inspection.company.company_id,
                "company_symbol": inspection.company.symbol,
                "detected_title": inspection.detected_title,
                "document_type": inspection.document_type,
                "financial_year": inspection.financial_year,
                "quarter": inspection.quarter,
            }, f)

    candidates = [
        DocumentCandidateCompany(
            id=c.get("id"),
            name=c["name"],
            symbol=c["symbol"],
            exchange=c.get("exchange", "NSE"),
            isin=c.get("isin"),
        )
        for c in inspection.company.candidate_matches
    ]

    return DocumentAnalysisResponse(
        filename=inspection.filename,
        file_size_bytes=inspection.file_size_bytes,
        file_hash=inspection.file_hash,
        mime_type=inspection.mime_type,
        total_pages=inspection.total_pages,
        extracted_text_preview=inspection.extracted_text_preview,
        is_relevant=inspection.relevance.is_relevant,
        relevance_category=inspection.relevance.category,
        relevance_confidence=inspection.relevance.confidence,
        relevance_reasons=inspection.relevance.reasons,
        rejection_message=inspection.relevance.rejection_message,
        company_id=inspection.company.company_id,
        company_name=inspection.company.company_name,
        company_symbol=inspection.company.symbol,
        exchange=inspection.company.exchange,
        isin=inspection.company.isin,
        company_confidence=inspection.company.confidence,
        company_identification_status=inspection.company.status,
        candidate_matches=candidates,
        company_evidence=inspection.company.evidence,
        detected_title=inspection.detected_title,
        document_type=inspection.document_type,
        document_type_confidence=inspection.document_type_confidence,
        financial_year=inspection.financial_year,
        quarter=inspection.quarter,
        reporting_basis=inspection.reporting_basis,
        currency=inspection.currency,
        unit=inspection.unit,
        is_duplicate=inspection.is_duplicate,
        existing_document_id=inspection.existing_document_id,
        existing_document_title=inspection.existing_document_title,
        temp_file_token=inspection.temp_file_token,
        can_proceed=inspection.can_proceed,
    )


@router.post("/confirm", response_model=DocumentUploadResponse)
def confirm_document(
    payload: DocumentConfirmRequest,
    db: Session = Depends(get_db),
):
    """
    Confirms an inspected document, persists it to Supabase Storage & PostgreSQL,
    and runs the RAG ingestion pipeline (chunking + pgvector embeddings).
    """
    staged = _get_staged_file(payload.temp_file_token)
    if not staged:
        raise HTTPException(
            status_code=404,
            detail="Staged file session expired or not found. Please upload the file again.",
        )
    staged_path, filename = staged

    meta_path = os.path.join(STAGING_DIR, f"{payload.temp_file_token}.meta.json")
    staged_meta = {}
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as f:
                staged_meta = json.load(f)
        except Exception:
            pass

    # Resolve company
    company = None
    target_cid = payload.company_id or staged_meta.get("company_id")
    if target_cid:
        company = db.query(Company).filter(Company.id == parse_uuid(target_cid)).first()
    target_sym = payload.company_symbol or staged_meta.get("company_symbol")
    if not company and target_sym:
        company = company_discovery_service.resolve_or_create(db, target_sym)

    if not company:
        raise HTTPException(
            status_code=400,
            detail="Valid company selection or symbol is required to index the document.",
        )

    with open(staged_path, "rb") as f:
        contents = f.read()

    doc_id = uuid.uuid4()
    doc_type = payload.document_type or staged_meta.get("document_type") or "Annual Report"
    fy = payload.financial_year or staged_meta.get("financial_year") or "FY24"
    doc_title = payload.title or staged_meta.get("detected_title") or f"{company.name} {doc_type} {fy}"

    storage_path = supabase_storage.generate_storage_path(
        company_id=company.id,
        document_type=doc_type,
        filename=filename,
    )

    upload_meta = supabase_storage.upload_file(
        file_bytes=contents,
        destination_path=storage_path,
        content_type="application/pdf" if filename.endswith(".pdf") else "application/octet-stream",
    )

    file_hash = hashlib.sha256(contents).hexdigest()

    doc = Document(
        id=doc_id,
        company_id=company.id,
        title=doc_title,
        filename=filename,
        file_path=upload_meta["local_path"],
        file_size_bytes=len(contents),
        mime_type="application/pdf" if filename.endswith(".pdf") else "application/octet-stream",
        file_hash=file_hash,
        financial_year=fy,
        document_type=doc_type,
        status="UPLOADED",
        metadata_json={
            "storage_path": upload_meta["storage_path"],
            "bucket": upload_meta["bucket"],
            "remote_uploaded": upload_meta["remote_uploaded"],
            "quarter": payload.quarter,
        },
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    chunks_stored = 0
    if payload.auto_process:
        try:
            res = rag_service.ingest_document(
                db=db,
                document_id=str(doc.id),
                file_path_or_bytes=doc.file_path,
                filename=filename,
                mime_type=doc.mime_type,
                financial_year=fy,
                quarter=payload.quarter,
            )
            chunks_stored = res.get("chunks_stored", 0)
            message = f"Document confirmed and indexed successfully ({chunks_stored} chunks in pgvector)."
        except Exception as e:
            message = f"Document confirmed, but chunk indexing failed: {str(e)}"
    else:
        message = "Document confirmed and uploaded to Supabase Storage. Ready for indexing."

    # Clean up staging file
    try:
        os.remove(staged_path)
    except OSError:
        pass
    if os.path.exists(meta_path):
        try:
            os.remove(meta_path)
        except OSError:
            pass

    return DocumentUploadResponse(
        document_id=doc.id,
        title=doc.title,
        filename=doc.filename,
        status=doc.status,
        message=message,
        company_id=company.id,
        company_symbol=company.symbol,
        chunks_stored=chunks_stored,
    )


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    company_id: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    financial_year: Optional[str] = Form(None),
    document_type: Optional[str] = Form(None),
    auto_process: bool = Form(True),
    db: Session = Depends(get_db),
):
    """
    Intelligent Document Upload:
      - If company_id / title / FY are omitted, runs automated inspection.
      - If content is detected as unrelated, returns 400 rejection immediately.
      - If relevant, persists to Supabase Storage and pgvector.
    """
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="The uploaded file is empty (0 bytes).")

    # If company or metadata is missing, run automated intelligence
    detected_company = None
    final_title = title
    final_doc_type = document_type or "Annual Report"
    final_fy = financial_year or "FY24"

    if company_id:
        detected_company = db.query(Company).filter(Company.id == (parse_uuid(company_id) or company_id)).first()

    if not detected_company or not final_title:
        # Run inspection
        inspection = document_intelligence.inspect_document(
            db=db,
            filename=file.filename,
            file_bytes=contents,
        )

        if not inspection.relevance.is_relevant:
            raise HTTPException(
                status_code=400,
                detail=inspection.relevance.rejection_message
                or "Document not recognized as a relevant company or financial document.",
            )

        if not detected_company and inspection.company.company_id:
            detected_company = db.query(Company).filter(Company.id == parse_uuid(inspection.company.company_id)).first()

        if not detected_company and inspection.company.symbol:
            detected_company = company_discovery_service.resolve_or_create(db, inspection.company.symbol)

        if not final_title:
            final_title = inspection.detected_title
        if not document_type:
            final_doc_type = inspection.document_type
        if not financial_year:
            final_fy = inspection.financial_year or "FY24"

    if not detected_company:
        raise HTTPException(
            status_code=422,
            detail="Company could not be automatically identified with high confidence. Please inspect via /documents/analyze and select the correct company.",
        )

    doc_id = uuid.uuid4()
    storage_path = supabase_storage.generate_storage_path(
        company_id=detected_company.id,
        document_type=final_doc_type,
        filename=file.filename,
    )

    upload_meta = supabase_storage.upload_file(
        file_bytes=contents,
        destination_path=storage_path,
        content_type=file.content_type or "application/octet-stream",
    )

    file_hash = hashlib.sha256(contents).hexdigest()

    doc = Document(
        id=doc_id,
        company_id=detected_company.id,
        title=final_title or f"{detected_company.name} {final_doc_type}",
        filename=file.filename,
        file_path=upload_meta["local_path"],
        file_size_bytes=len(contents),
        mime_type=file.content_type or "application/octet-stream",
        file_hash=file_hash,
        financial_year=final_fy,
        document_type=final_doc_type,
        status="UPLOADED",
        metadata_json={
            "storage_path": upload_meta["storage_path"],
            "bucket": upload_meta["bucket"],
            "remote_uploaded": upload_meta["remote_uploaded"],
        },
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    chunks_stored = 0
    if auto_process:
        try:
            res = rag_service.ingest_document(
                db=db,
                document_id=str(doc.id),
                file_path_or_bytes=doc.file_path,
                filename=file.filename,
                mime_type=doc.mime_type,
                financial_year=final_fy,
            )
            chunks_stored = res.get("chunks_stored", 0)
            message = f"Document uploaded and processed successfully into pgvector ({chunks_stored} chunks)."
        except Exception as e:
            message = f"Document uploaded, but processing failed: {str(e)}"
    else:
        message = "Document uploaded successfully to Supabase Storage. Ready for processing."

    return DocumentUploadResponse(
        document_id=doc.id,
        title=doc.title,
        filename=doc.filename,
        status=doc.status,
        message=message,
        company_id=detected_company.id,
        company_symbol=detected_company.symbol,
        chunks_stored=chunks_stored,
    )


@router.get("", response_model=List[DocumentResponse])
def list_documents(
    company_id: Optional[str] = None,
    document_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Document)
    if company_id:
        parsed = parse_uuid(company_id)
        if parsed:
            query = query.filter(Document.company_id == parsed)
        else:
            comp = db.query(Company).filter(Company.symbol == company_id.upper()).first()
            if comp:
                query = query.filter(Document.company_id == comp.id)

    if document_type:
        query = query.filter(Document.document_type == document_type)
    if status:
        query = query.filter(Document.status == status.upper())
    if search:
        patt = f"%{search}%"
        query = query.filter(or_(Document.title.ilike(patt), Document.filename.ilike(patt)))

    docs = query.order_by(Document.created_at.desc()).all()

    # Enrich with company symbols
    results = []
    for d in docs:
        c = d.company
        results.append(DocumentResponse(
            id=d.id,
            company_id=d.company_id,
            company_name=c.name if c else None,
            company_symbol=c.symbol if c else None,
            user_id=d.user_id,
            title=d.title,
            filename=d.filename,
            file_size_bytes=d.file_size_bytes,
            mime_type=d.mime_type,
            status=d.status,
            error_message=d.error_message,
            total_pages=d.total_pages or 0,
            total_chunks=d.total_chunks or 0,
            financial_year=d.financial_year,
            document_type=d.document_type,
            created_at=d.created_at,
            updated_at=d.updated_at,
        ))
    return results


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, db: Session = Depends(get_db)):
    parsed_id = parse_uuid(document_id) or document_id
    doc = db.query(Document).filter(Document.id == parsed_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    c = doc.company
    return DocumentResponse(
        id=doc.id,
        company_id=doc.company_id,
        company_name=c.name if c else None,
        company_symbol=c.symbol if c else None,
        user_id=doc.user_id,
        title=doc.title,
        filename=doc.filename,
        file_size_bytes=doc.file_size_bytes,
        mime_type=doc.mime_type,
        status=doc.status,
        error_message=doc.error_message,
        total_pages=doc.total_pages or 0,
        total_chunks=doc.total_chunks or 0,
        financial_year=doc.financial_year,
        document_type=doc.document_type,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.get("/{document_id}/stats", response_model=Dict[str, Any])
def get_document_stats(document_id: str, db: Session = Depends(get_db)):
    parsed_id = parse_uuid(document_id) or document_id
    doc = db.query(Document).filter(Document.id == parsed_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "document_id": str(doc.id),
        "title": doc.title,
        "company_symbol": doc.company.symbol if doc.company else None,
        "total_pages": doc.total_pages or 0,
        "total_chunks": doc.total_chunks or 0,
        "file_size_bytes": doc.file_size_bytes,
        "status": doc.status,
        "financial_year": doc.financial_year,
        "document_type": doc.document_type,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.post("/{document_id}/process", response_model=DocumentProcessResponse)
@router.post("/{document_id}/reprocess", response_model=DocumentProcessResponse)
def process_document(document_id: str, db: Session = Depends(get_db)):
    """Triggers RAG extraction, chunking, and pgvector embeddings on an existing document."""
    parsed_id = parse_uuid(document_id) or document_id
    doc = db.query(Document).filter(Document.id == parsed_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not os.path.exists(doc.file_path):
        raise HTTPException(status_code=400, detail="Stored file path does not exist on disk.")

    result = rag_service.ingest_document(
        db=db,
        document_id=str(doc.id),
        file_path_or_bytes=doc.file_path,
        filename=doc.filename,
        mime_type=doc.mime_type,
        reprocess=True,
    )

    return DocumentProcessResponse(
        document_id=result["document_id"],
        status=result["status"],
        pages_extracted=result["pages_extracted"],
        chunks_stored=result["chunks_stored"],
        message=f"Document processed successfully into {result['chunks_stored']} pgvector chunks.",
    )


@router.get("/{document_id}/download")
def download_document(document_id: str, db: Session = Depends(get_db)):
    """Generates signed URL or streams file for document download."""
    parsed_id = parse_uuid(document_id) or document_id
    doc = db.query(Document).filter(Document.id == parsed_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    storage_path = (doc.metadata_json or {}).get("storage_path")
    if storage_path:
        signed_url = supabase_storage.create_signed_url(storage_path)
        if signed_url:
            return {"download_url": signed_url, "storage": "supabase"}

    if doc.file_path and os.path.exists(doc.file_path):
        return FileResponse(
            path=doc.file_path,
            filename=doc.filename,
            media_type=doc.mime_type,
        )

    raise HTTPException(status_code=404, detail="Document file not found in storage")


@router.delete("/{document_id}")
def delete_document(document_id: str, db: Session = Depends(get_db)):
    parsed_id = parse_uuid(document_id) or document_id
    doc = db.query(Document).filter(Document.id == parsed_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    storage_path = (doc.metadata_json or {}).get("storage_path")
    if storage_path or doc.file_path:
        supabase_storage.delete_file(
            storage_path=storage_path or "",
            local_path=doc.file_path,
        )

    # Clean up associated document chunks in MongoDB Atlas
    try:
        if mongodb_manager.is_connected:
            mongodb_manager.delete_document_chunks(str(doc.id))
    except Exception:
        pass

    db.delete(doc)
    db.commit()
    return {"message": "Document and associated embeddings deleted successfully"}
