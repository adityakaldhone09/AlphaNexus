import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, JSON, Index
from sqlalchemy import Uuid
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from ..core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    company_id = Column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size_bytes = Column(Integer, nullable=False)
    mime_type = Column(String(100), nullable=False)
    file_hash = Column(String(64), nullable=True, index=True)  # SHA-256
    financial_year = Column(String(20), nullable=True, index=True)  # e.g., FY24, FY25
    document_type = Column(String(50), nullable=False, index=True)  # Annual Report, Earnings Call, Investor Presentation, etc.
    status = Column(String(30), default="UPLOADED", index=True)  # UPLOADED, QUEUED, PROCESSING, PROCESSED, FAILED
    error_message = Column(Text, nullable=True)
    total_pages = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="documents")
    company = relationship("Company", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    citations = relationship("Citation", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    document_id = Column(Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    clean_text = Column(Text, nullable=True)
    section = Column(String(100), nullable=True)
    page_number = Column(Integer, nullable=True)
    token_count = Column(Integer, default=0)
    embedding = Column(Vector(384), nullable=True)  # 384-d BAAI/bge-small-en-v1.5
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="chunks")
    company = relationship("Company", back_populates="document_chunks")
    citations = relationship("Citation", back_populates="chunk", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_chunk_company_page", "company_id", "page_number"),
    )

