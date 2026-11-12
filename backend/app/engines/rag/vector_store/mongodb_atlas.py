"""
ALPHANEXUS – MongoDB Atlas Vector Search Store
===============================================
Performs semantic vector search using MongoDB Atlas's native $vectorSearch aggregation stage.
Includes dimensional verification (384-d), metadata filtering, score projection,
and graceful handling of missing Atlas search indexes.
"""

from typing import List, Dict, Any, Optional
from pymongo.errors import OperationFailure, PyMongoError

from app.core.config import settings
from app.core.logging import logger
from app.database.mongodb import mongodb_manager, MongoDBUnavailableError
from app.database.collections import COLLECTION_CHUNKS


class MongoDBVectorIndexMissingError(RuntimeError):
    """Raised when the configured Atlas Vector Search index is not present on the cluster."""
    pass


class MongoDBAtlasStore:
    """
    Manages semantic vector retrieval against MongoDB Atlas using $vectorSearch.
    """

    def __init__(self):
        self.index_name: str = getattr(settings, "MONGODB_VECTOR_INDEX_NAME", "vector_index")
        self.expected_dim: int = getattr(settings, "EMBEDDING_DIMENSION", 384)

    @property
    def is_available(self) -> bool:
        """Indicates whether MongoDB Atlas connection is active."""
        return mongodb_manager.is_connected

    def store_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """Stores chunk records with their vector embeddings into MongoDB."""
        return mongodb_manager.store_chunks(chunks)

    def search_similar(
        self,
        query_vector: List[float],
        top_k: int = 8,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes genuine semantic vector similarity search via MongoDB $vectorSearch.

        Args:
            query_vector: 384-dimensional query embedding.
            top_k: Number of similar chunks to return.
            filters: Optional metadata filters (e.g. {"company_id": "...", "financial_year": "FY24"}).

        Returns:
            List of matching chunks with similarity scores.
        """
        # 1. Validate embedding dimensions
        if not query_vector or len(query_vector) != self.expected_dim:
            raise ValueError(
                f"Invalid query vector dimension: got {len(query_vector) if query_vector else 0}, "
                f"expected {self.expected_dim} dimensions."
            )

        # 2. Check cluster availability
        if not mongodb_manager.is_connected or mongodb_manager.database is None:
            if mongodb_manager.allow_fallback:
                logger.warning("[Atlas Vector Search] Atlas disconnected; using metadata fallback in simulation mode.")
                return mongodb_manager.find_chunks(filters or {}, limit=top_k)
            raise MongoDBUnavailableError(
                f"MongoDB Atlas is not connected: {mongodb_manager.connection_error}"
            )

        coll = mongodb_manager.database[COLLECTION_CHUNKS]

        # 3. Build $vectorSearch aggregation pipeline
        vector_search_stage: Dict[str, Any] = {
            "$vectorSearch": {
                "index": self.index_name,
                "path": "embedding",
                "queryVector": query_vector,
                "numCandidates": max(top_k * 15, 100),
                "limit": top_k,
            }
        }

        # Apply metadata filters if provided
        clean_filters = {k: v for k, v in (filters or {}).items() if v is not None}
        if clean_filters:
            vector_search_stage["$vectorSearch"]["filter"] = clean_filters

        pipeline = [
            vector_search_stage,
            {
                "$project": {
                    "_id": 1,
                    "chunk_id": 1,
                    "document_id": 1,
                    "company_id": 1,
                    "symbol": 1,
                    "financial_year": 1,
                    "document_type": 1,
                    "chunk_index": 1,
                    "page_number": 1,
                    "section": 1,
                    "content": 1,
                    "token_count": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
        ]

        try:
            cursor = coll.aggregate(pipeline)
            results = list(cursor)
            return [
                {
                    "chunk_id": doc.get("chunk_id") or str(doc.get("_id")),
                    "document_id": str(doc.get("document_id")),
                    "company_id": str(doc.get("company_id")),
                    "symbol": doc.get("symbol", ""),
                    "financial_year": doc.get("financial_year", ""),
                    "document_type": doc.get("document_type", ""),
                    "chunk_index": doc.get("chunk_index", 0),
                    "page_number": doc.get("page_number", 1),
                    "section": doc.get("section", ""),
                    "content": doc.get("content", ""),
                    "similarity_score": float(doc.get("score", 0.0)),
                    "token_count": doc.get("token_count", 0),
                }
                for doc in results
            ]
        except OperationFailure as e:
            err_text = str(e)
            if "index not found" in err_text.lower() or "vectorsearch" in err_text.lower() or "planexecutor" in err_text.lower():
                logger.error(
                    "Atlas Vector Search index '%s' is missing or unindexed on '%s'. Detail: %s",
                    self.index_name,
                    COLLECTION_CHUNKS,
                    err_text,
                )
                raise MongoDBVectorIndexMissingError(
                    f"Atlas Vector Search index '{self.index_name}' does not exist on collection '{COLLECTION_CHUNKS}'. "
                    "Create the vector index in Atlas Search with fields: embedding (vector, 384-d, cosine)."
                ) from e
            raise
        except PyMongoError as e:
            logger.error("MongoDB Atlas Vector Search aggregation failed: %s", str(e))
            raise

    def check_vector_search_ready(self) -> Dict[str, Any]:
        """
        Validates whether Atlas Vector Search is operational by probing the index.
        Never reports healthy unless an actual query executes without index errors.
        """
        if not mongodb_manager.is_connected:
            return {
                "ready": False,
                "status": "Unavailable",
                "index_name": self.index_name,
                "reason": "MongoDB Atlas cluster is disconnected.",
            }

        dummy_vector = [0.0] * self.expected_dim
        try:
            self.search_similar(query_vector=dummy_vector, top_k=1)
            return {
                "ready": True,
                "status": "Ready",
                "index_name": self.index_name,
                "dimensions": self.expected_dim,
                "reason": "Atlas Vector Search query verified.",
            }
        except MongoDBVectorIndexMissingError as e:
            return {
                "ready": False,
                "status": "Index Missing",
                "index_name": self.index_name,
                "dimensions": self.expected_dim,
                "reason": str(e),
            }
        except Exception as e:
            return {
                "ready": False,
                "status": "Unavailable",
                "index_name": self.index_name,
                "dimensions": self.expected_dim,
                "reason": f"Probe query failed: {type(e).__name__} - {str(e)[:100]}",
            }


mongodb_atlas_store = MongoDBAtlasStore()
