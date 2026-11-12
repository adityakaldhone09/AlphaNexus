"""
ALPHANEXUS – MongoDB Collection Name Registry & Schema Index Definitions
========================================================================
Central constants, specifications, and index management for all RAG
and document collections in MongoDB Atlas.
"""

from typing import Dict, Any, List, Tuple
from pymongo.database import Database
from pymongo.collection import Collection
from pymongo import ASCENDING, DESCENDING
from app.core.logging import logger

COLLECTION_DOCUMENTS = "rag_documents"
COLLECTION_CHUNKS = "rag_chunks"
COLLECTION_CONVERSATIONS = "rag_conversations"
COLLECTION_CITATIONS = "rag_citations"
COLLECTION_CONFIGURATIONS = "rag_configurations"
COLLECTION_EVALUATIONS = "rag_evaluations"

ALL_COLLECTIONS = [
    COLLECTION_DOCUMENTS,
    COLLECTION_CHUNKS,
    COLLECTION_CONVERSATIONS,
    COLLECTION_CITATIONS,
    COLLECTION_CONFIGURATIONS,
    COLLECTION_EVALUATIONS,
]

# Standard metadata and unique indexes definitions
COLLECTION_INDEXES: Dict[str, List[Dict[str, Any]]] = {
    COLLECTION_DOCUMENTS: [
        {"keys": [("company_id", ASCENDING), ("financial_year", ASCENDING)], "name": "idx_company_fy"},
        {"keys": [("file_checksum", ASCENDING)], "unique": True, "sparse": True, "name": "idx_file_checksum"},
        {"keys": [("document_type", ASCENDING)], "name": "idx_doc_type"},
        {"keys": [("created_at", DESCENDING)], "name": "idx_created_at"},
    ],
    COLLECTION_CHUNKS: [
        {"keys": [("chunk_id", ASCENDING)], "unique": True, "sparse": True, "name": "idx_chunk_id"},
        {"keys": [("document_id", ASCENDING), ("chunk_index", ASCENDING)], "name": "idx_doc_chunk_idx"},
        {"keys": [("company_id", ASCENDING), ("document_type", ASCENDING)], "name": "idx_company_doc_type"},
        {"keys": [("financial_year", ASCENDING)], "name": "idx_financial_year"},
    ],
    COLLECTION_CONVERSATIONS: [
        {"keys": [("session_id", ASCENDING)], "unique": True, "name": "idx_session_id"},
        {"keys": [("company_id", ASCENDING)], "name": "idx_company_id"},
        {"keys": [("created_at", DESCENDING)], "name": "idx_created_at"},
    ],
    COLLECTION_CITATIONS: [
        {"keys": [("session_id", ASCENDING), ("document_id", ASCENDING)], "name": "idx_session_doc"},
        {"keys": [("chunk_id", ASCENDING)], "name": "idx_chunk_id"},
    ],
    COLLECTION_CONFIGURATIONS: [
        {"keys": [("name", ASCENDING)], "unique": True, "name": "idx_config_name"},
    ],
    COLLECTION_EVALUATIONS: [
        {"keys": [("session_id", ASCENDING)], "name": "idx_eval_session"},
        {"keys": [("created_at", DESCENDING)], "name": "idx_created_at"},
    ],
}


def ensure_all_collection_indexes(db: Database) -> Dict[str, List[str]]:
    """
    Creates standard indexes across all AlphaNexus MongoDB collections.
    Does not drop, overwrite, or reset existing documents.
    """
    created_indexes: Dict[str, List[str]] = {}
    for coll_name, index_specs in COLLECTION_INDEXES.items():
        coll = db[coll_name]
        created_indexes[coll_name] = []
        for spec in index_specs:
            keys = spec["keys"]
            unique = spec.get("unique", False)
            sparse = spec.get("sparse", False)
            name = spec.get("name")
            try:
                idx_name = coll.create_index(keys, unique=unique, sparse=sparse, name=name)
                created_indexes[coll_name].append(idx_name)
            except Exception as e:
                logger.warning(f"Notice creating index {name or keys} on {coll_name}: {e}")
    return created_indexes


def get_existing_collection_indexes(db: Database) -> Dict[str, List[str]]:
    """Inspects and returns current index names across all collections."""
    existing: Dict[str, List[str]] = {}
    for coll_name in ALL_COLLECTIONS:
        try:
            coll = db[coll_name]
            info = coll.index_information()
            existing[coll_name] = list(info.keys())
        except Exception:
            existing[coll_name] = []
    return existing
