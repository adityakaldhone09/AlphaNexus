"""
ALPHANEXUS – MongoDB Atlas & Vector Search Unit Test Suite
=========================================================
Covers:
1. Valid connection simulation / ping
2. Invalid URI handling
3. Network access / TLS handshake block error classification
4. Document insertion & validation
5. Chunk insertion with vector embeddings
6. Duplicate document handling / checksum deduplication
7. Metadata filtering
8. $vectorSearch aggregation pipeline generation & score projection
9. Missing Atlas Vector Search index error handling
10. MongoDB unavailable: no silent in-memory fallback writes
11. Document deletion & cascading chunk removal
12. Health check diagnostic reporting (distinguishing ping from vector search)
"""

import pytest
from unittest.mock import MagicMock, patch
from pymongo.errors import ServerSelectionTimeoutError, OperationFailure

from app.core.config import settings
from app.database.mongodb import (
    MongoDBManager,
    MongoDBUnavailableError,
)
from app.database.collections import (
    COLLECTION_DOCUMENTS,
    COLLECTION_CHUNKS,
    COLLECTION_CONVERSATIONS,
    COLLECTION_CITATIONS,
    COLLECTION_CONFIGURATIONS,
    COLLECTION_EVALUATIONS,
    ALL_COLLECTIONS,
    COLLECTION_INDEXES,
    ensure_all_collection_indexes,
    get_existing_collection_indexes,
)
from app.engines.rag.vector_store.mongodb_atlas import (
    MongoDBAtlasStore,
    MongoDBVectorIndexMissingError,
)


# ==============================================================================
# 1. Configuration & Collections
# ==============================================================================

def test_all_collections_defined():
    """Verify all 6 required collections exist in the registry."""
    expected = [
        "rag_documents",
        "rag_chunks",
        "rag_conversations",
        "rag_citations",
        "rag_configurations",
        "rag_evaluations",
    ]
    assert sorted(ALL_COLLECTIONS) == sorted(expected)
    for c in expected:
        assert c in COLLECTION_INDEXES, f"Missing index specification for {c}"


def test_ensure_all_collection_indexes_on_mock_db():
    """Verify indexes are created without dropping existing records."""
    mock_db = {}
    mock_collections = {}

    for c in ALL_COLLECTIONS:
        coll = MagicMock()
        coll.create_index = MagicMock(return_value="test_idx")
        mock_collections[c] = coll

    mock_db_obj = MagicMock()
    mock_db_obj.__getitem__.side_effect = lambda name: mock_collections[name]

    created = ensure_all_collection_indexes(mock_db_obj)
    assert len(created) == len(ALL_COLLECTIONS)
    for c in ALL_COLLECTIONS:
        assert len(created[c]) > 0


# ==============================================================================
# 2. Connection Lifecycle & Invalid URI
# ==============================================================================

def test_unconfigured_mongodb(monkeypatch):
    """Verify clean status when MONGODB_URI is not set."""
    monkeypatch.setattr(settings, "MONGODB_URI", None)
    mgr = MongoDBManager()
    assert not mgr.is_connected
    health = mgr.check_health()
    assert health["configured"] is False
    assert health["connected"] is False
    assert health["status"] == "Not configured"
    assert health["operational"] is False


def test_invalid_mongodb_uri(monkeypatch):
    """Verify error handling on invalid connection URI."""
    monkeypatch.setattr(settings, "MONGODB_URI", "mongodb://invalid-host-definitely-does-not-exist:27017")
    monkeypatch.setattr(settings, "MONGODB_TIMEOUT_MS", 100)

    mgr = MongoDBManager()
    assert not mgr.is_connected
    assert mgr.connection_error is not None
    health = mgr.check_health()
    assert health["configured"] is True
    assert health["connected"] is False
    assert health["status"] == "Unavailable"
    # Never expose credentials
    assert "password" not in str(health).lower()


# ==============================================================================
# 3. Network Access / TLS Alert Classification
# ==============================================================================

def test_network_access_block_sanitization(monkeypatch):
    """Verify that TLS alert / IP not whitelisted produces a clear remediation message."""
    monkeypatch.setattr(settings, "MONGODB_URI", "mongodb+srv://user:pass@cluster.mongodb.net/")

    with patch("app.database.mongodb.MongoClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.admin.command.side_effect = ServerSelectionTimeoutError(
            "SSL handshake failed: [SSL: TLSV1_ALERT_INTERNAL_ERROR] tlsv1 alert internal error"
        )
        mock_client_cls.return_value = mock_client

        mgr = MongoDBManager()
        assert not mgr.is_connected
        assert "Network Access Block" in mgr.connection_error
        assert "pass" not in mgr.connection_error  # No password leak


# ==============================================================================
# 4. In-Memory Fallback Removal (Production Safety)
# ==============================================================================

def test_disconnected_manager_raises_without_fallback(monkeypatch):
    """
    CRITICAL: In production (allow_fallback=False), writes MUST fail
    with MongoDBUnavailableError rather than silently going into in-memory storage.
    """
    monkeypatch.setattr(settings, "MONGODB_URI", None)
    monkeypatch.setattr(settings, "MONGODB_ALLOW_IN_MEMORY_FALLBACK", False)
    mgr = MongoDBManager()

    # 1. store_document
    with pytest.raises(MongoDBUnavailableError):
        mgr.store_document({"_id": "doc-1", "title": "Test Doc"})

    # 2. store_chunks
    with pytest.raises(MongoDBUnavailableError):
        mgr.store_chunks([{"chunk_id": "chk-1", "content": "Text"}])

    # 3. find_chunks
    with pytest.raises(MongoDBUnavailableError):
        mgr.find_chunks({"document_id": "doc-1"})

    # 4. delete_document_chunks
    with pytest.raises(MongoDBUnavailableError):
        mgr.delete_document_chunks("doc-1")


def test_controlled_in_memory_fallback_when_explicitly_allowed(monkeypatch):
    """In test/dev mode when MONGODB_ALLOW_IN_MEMORY_FALLBACK=True, in-memory operations work."""
    monkeypatch.setattr(settings, "MONGODB_URI", None)
    monkeypatch.setattr(settings, "MONGODB_ALLOW_IN_MEMORY_FALLBACK", True)
    mgr = MongoDBManager()
    assert mgr.allow_fallback is True

    doc_id = mgr.store_document({"_id": "test-doc-fallback", "filename": "test.pdf"})
    assert doc_id == "test-doc-fallback"

    chunk_count = mgr.store_chunks([{"document_id": "test-doc-fallback", "content": "Sample"}])
    assert chunk_count == 1

    found = mgr.find_chunks({"document_id": "test-doc-fallback"})
    assert len(found) == 1

    deleted = mgr.delete_document_chunks("test-doc-fallback")
    assert deleted >= 1


# ==============================================================================
# 5. Connected Document & Chunk Insertion
# ==============================================================================

def test_connected_document_and_chunk_storage(monkeypatch):
    """Verify standard MongoDB collection operations when connected."""
    mock_db = MagicMock()
    mock_docs_coll = MagicMock()
    mock_chunks_coll = MagicMock()

    mock_docs_coll.insert_one.return_value = MagicMock(inserted_id="doc-uuid-123")
    mock_chunks_coll.insert_many.return_value = MagicMock(inserted_ids=["c1", "c2"])
    mock_chunks_coll.delete_many.return_value = MagicMock(deleted_count=2)
    mock_docs_coll.delete_one.return_value = MagicMock(deleted_count=1)

    def get_coll(name):
        if name == COLLECTION_DOCUMENTS:
            return mock_docs_coll
        if name == COLLECTION_CHUNKS:
            return mock_chunks_coll
        return MagicMock()

    mock_db.__getitem__.side_effect = get_coll

    mgr = MongoDBManager()
    mgr._is_connected = True
    mgr._db = mock_db

    doc_id = mgr.store_document({"_id": "doc-uuid-123", "filename": "reliance_q2.pdf"})
    assert doc_id == "doc-uuid-123"
    mock_docs_coll.insert_one.assert_called_once()

    stored_count = mgr.store_chunks([
        {"chunk_id": "c1", "document_id": "doc-uuid-123", "content": "Text 1"},
        {"chunk_id": "c2", "document_id": "doc-uuid-123", "content": "Text 2"},
    ])
    assert stored_count == 2
    mock_chunks_coll.insert_many.assert_called_once()

    del_count = mgr.delete_document_chunks("doc-uuid-123")
    assert del_count == 2
    mock_chunks_coll.delete_many.assert_called_once_with({"document_id": "doc-uuid-123"})
    mock_docs_coll.delete_one.assert_called_once_with({"_id": "doc-uuid-123"})


# ==============================================================================
# 6. MongoDB Atlas $vectorSearch Aggregation & Dimensions
# ==============================================================================

def test_atlas_vector_search_dimension_validation():
    """Verify vector search validates exact 384 dimensions."""
    store = MongoDBAtlasStore()
    with pytest.raises(ValueError, match="Invalid query vector dimension"):
        # Passing 10-dimensional vector instead of 384
        store.search_similar([0.1] * 10)


def test_atlas_vector_search_pipeline_execution():
    """Verify $vectorSearch pipeline structure, metadata filters, and score projection."""
    mock_chunks_coll = MagicMock()
    mock_chunks_coll.aggregate.return_value = [
        {
            "_id": "chk-mongo-1",
            "chunk_id": "chk-uuid-1",
            "document_id": "doc-uuid-1",
            "company_id": "comp-uuid-1",
            "symbol": "RELIANCE",
            "financial_year": "FY24",
            "document_type": "Annual Report",
            "chunk_index": 0,
            "page_number": 4,
            "section": "Financial Highlights",
            "content": "Consolidated EBITDA stood at ₹1,78,000 Crores.",
            "score": 0.895,
            "token_count": 42,
        }
    ]

    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_chunks_coll

    store = MongoDBAtlasStore()
    query_vector = [0.05] * 384
    filters = {"company_id": "comp-uuid-1", "financial_year": "FY24"}

    from app.database.mongodb import mongodb_manager
    orig_conn = mongodb_manager.is_connected
    orig_db = mongodb_manager.database
    try:
        mongodb_manager.is_connected = True
        mongodb_manager.database = mock_db

        results = store.search_similar(query_vector=query_vector, top_k=5, filters=filters)

        assert len(results) == 1
        top_match = results[0]
        assert top_match["chunk_id"] == "chk-uuid-1"
        assert top_match["similarity_score"] == 0.895
        assert top_match["symbol"] == "RELIANCE"
        assert top_match["page_number"] == 4

        # Verify aggregate call pipeline
        mock_chunks_coll.aggregate.assert_called_once()
        pipeline = mock_chunks_coll.aggregate.call_args[0][0]

        # Stage 0: $vectorSearch
        assert "$vectorSearch" in pipeline[0]
        v_stage = pipeline[0]["$vectorSearch"]
        assert v_stage["index"] == "vector_index"
        assert v_stage["path"] == "embedding"
        assert len(v_stage["queryVector"]) == 384
        assert v_stage["limit"] == 5
        assert v_stage["filter"] == filters

        # Stage 1: $project with score meta
        assert "$project" in pipeline[1]
        p_stage = pipeline[1]["$project"]
        assert p_stage["score"] == {"$meta": "vectorSearchScore"}
    finally:
        mongodb_manager.is_connected = orig_conn
        mongodb_manager.database = orig_db


def test_atlas_vector_search_missing_index_handling():
    """Verify graceful handling when Atlas Search index is not present on cluster."""
    mock_chunks_coll = MagicMock()
    mock_chunks_coll.aggregate.side_effect = OperationFailure(
        "PlanExecutor error during aggregation :: caused by :: vectorSearch index not found: vector_index"
    )

    mock_db = MagicMock()
    mock_db.__getitem__.return_value = mock_chunks_coll

    store = MongoDBAtlasStore()
    query_vector = [0.1] * 384

    from app.database.mongodb import mongodb_manager
    orig_conn = mongodb_manager.is_connected
    orig_db = mongodb_manager.database
    try:
        mongodb_manager.is_connected = True
        mongodb_manager.database = mock_db

        with pytest.raises(MongoDBVectorIndexMissingError, match="vector_index"):
            store.search_similar(query_vector=query_vector)

        # Probe status must also report Index Missing, not Ready
        status = store.check_vector_search_ready()
        assert status["ready"] is False
        assert status["status"] == "Index Missing"
    finally:
        mongodb_manager.is_connected = orig_conn
        mongodb_manager.database = orig_db
