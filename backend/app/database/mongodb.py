"""
ALPHANEXUS – MongoDB Atlas & Vector Search Database Manager
===========================================================
Production MongoDB client lifecycle manager for AlphaNexus RAG document intelligence.
Handles connection pooling, index verification, Atlas Vector Search compatibility,
and explicit error reporting without silent data loss.
"""

import os
import certifi
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from app.core.config import settings
from app.core.logging import logger
from app.database.collections import (
    COLLECTION_DOCUMENTS,
    COLLECTION_CHUNKS,
    COLLECTION_CONVERSATIONS,
    COLLECTION_CITATIONS,
    COLLECTION_CONFIGURATIONS,
    COLLECTION_EVALUATIONS,
    ALL_COLLECTIONS,
    ensure_all_collection_indexes,
    get_existing_collection_indexes,
)


class MongoDBUnavailableError(RuntimeError):
    """Raised when an operation is attempted while MongoDB Atlas is disconnected."""
    pass


# Optional in-memory fallback ONLY when explicitly enabled by MONGODB_ALLOW_IN_MEMORY_FALLBACK
_simulated_db: Dict[str, List[Dict[str, Any]]] = {
    COLLECTION_DOCUMENTS: [],
    COLLECTION_CHUNKS: [],
    COLLECTION_CONVERSATIONS: [],
    COLLECTION_CITATIONS: [],
    COLLECTION_CONFIGURATIONS: [],
    COLLECTION_EVALUATIONS: [],
}


class MongoDBManager:
    """
    Manages MongoDB Atlas connection, collections, and index lifecycle.
    Never exposes raw connection strings, usernames, or passwords.
    """

    def __init__(self):
        self.uri: Optional[str] = getattr(settings, "MONGODB_URI", None) or os.getenv("MONGODB_URI", "")
        self.db_name: str = getattr(settings, "effective_mongodb_db", None) or os.getenv("MONGODB_DB", "alphanexus_rag")
        self.timeout_ms: int = getattr(settings, "MONGODB_TIMEOUT_MS", 5000)
        self.allow_fallback: bool = getattr(settings, "MONGODB_ALLOW_IN_MEMORY_FALLBACK", False)

        self._client: Optional[MongoClient] = None
        self._db: Optional[Database] = None
        self._is_connected: bool = False
        self._connection_error: Optional[str] = None
        self._last_successful_check: Optional[str] = None
        self._server_version: Optional[str] = None

        self._connect()

    def _connect(self) -> None:
        """Establishes connection to MongoDB Atlas with TLS verification."""
        if not self.uri:
            self._connection_error = "MONGODB_URI is not configured in environment."
            self._is_connected = False
            return

        try:
            self._client = MongoClient(
                self.uri,
                tls=True,
                tlsCAFile=certifi.where(),
                serverSelectionTimeoutMS=self.timeout_ms,
                connectTimeoutMS=self.timeout_ms,
                socketTimeoutMS=self.timeout_ms,
                appname="AlphaNexus-Backend",
            )
            # Ping to confirm live cluster connectivity
            self._client.admin.command("ping")
            self._db = self._client[self.db_name]
            build_info = self._client.admin.command("buildInfo")
            self._server_version = build_info.get("version", "Unknown")

            self._is_connected = True
            self._connection_error = None
            self._last_successful_check = datetime.now(timezone.utc).isoformat()
            logger.info("Connected successfully to MongoDB Atlas database: %s", self.db_name)

            # Ensure all standard collection indexes
            ensure_all_collection_indexes(self._db)

        except Exception as e:
            self._is_connected = False
            self._db = None
            err_msg = str(e)
            if "tlsv1 alert internal error" in err_msg.lower() or "ssl handshake failed" in err_msg.lower():
                self._connection_error = (
                    "MongoDB Atlas Network Access Block: The application IP address is not allowlisted in "
                    "MongoDB Atlas Console -> Security -> Network Access. Add your IP or 0.0.0.0/0 to enable connectivity."
                )
            elif "authentication failed" in err_msg.lower():
                self._connection_error = "MongoDB Atlas Authentication Failed: Invalid username or password in MONGODB_URI."
            else:
                self._connection_error = f"MongoDB connection failed: {type(e).__name__}"
            logger.warning("MongoDB connection status: %s", self._connection_error)

    def reconnect(self) -> bool:
        """Manually re-attempts connection to MongoDB Atlas."""
        self._connect()
        return self._is_connected

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @is_connected.setter
    def is_connected(self, value: bool) -> None:
        self._is_connected = value

    @property
    def connection_error(self) -> Optional[str]:
        return self._connection_error

    @connection_error.setter
    def connection_error(self, value: Optional[str]) -> None:
        self._connection_error = value

    @property
    def database(self) -> Optional[Database]:
        return self._db

    @database.setter
    def database(self, value: Optional[Database]) -> None:
        self._db = value

    def get_collection(self, name: str) -> Optional[Collection]:
        if self._is_connected and self._db is not None:
            return self._db[name]
        return None

    def check_health(self) -> Dict[str, Any]:
        """
        Returns comprehensive diagnostic health check of MongoDB.
        Never marks MongoDB or vector search as healthy when disconnected.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        if self._is_connected and self._client is not None and self._db is not None:
            try:
                self._client.admin.command("ping")
                existing_colls = self._db.list_collection_names()
                indexes = get_existing_collection_indexes(self._db)
                self._last_successful_check = now_iso
                return {
                    "configured": True,
                    "connected": True,
                    "verified": True,
                    "status": "Connected",
                    "operational": True,
                    "database": self.db_name,
                    "server_version": self._server_version,
                    "deployment_type": "MongoDB Atlas ReplicaSet",
                    "collections": existing_colls,
                    "indexes": indexes,
                    "last_successful_check": self._last_successful_check,
                    "error": None,
                }
            except Exception as e:
                self._is_connected = False
                self._connection_error = f"MongoDB ping failed: {type(e).__name__}"

        return {
            "configured": bool(self.uri),
            "connected": False,
            "verified": False,
            "status": "Unavailable" if self.uri else "Not configured",
            "operational": False,
            "database": self.db_name,
            "server_version": None,
            "deployment_type": "Disconnected",
            "collections": [],
            "indexes": {},
            "last_successful_check": self._last_successful_check,
            "error": self._connection_error or "MongoDB Atlas is unreachable.",
            "remediation": (
                "Ensure MONGODB_URI is populated and the host IP is added to "
                "MongoDB Atlas Console -> Security -> Network Access."
                if self.uri
                else "Configure MONGODB_URI in the environment."
            ),
        }

    # -------------------------------------------------------------------------
    # Unified Document & Chunk Storage Interface
    # -------------------------------------------------------------------------

    def store_document(self, doc_data: Dict[str, Any]) -> str:
        """
        Stores document metadata in rag_documents.
        In production, raises MongoDBUnavailableError if Atlas is unreachable,
        preventing silent data loss.
        """
        if self._is_connected and self._db is not None:
            res = self._db[COLLECTION_DOCUMENTS].insert_one(doc_data)
            return str(res.inserted_id)

        if self.allow_fallback:
            logger.warning("[MongoDB] Using explicitly allowed in-memory fallback for store_document.")
            _simulated_db[COLLECTION_DOCUMENTS].append(doc_data)
            return str(doc_data.get("_id") or len(_simulated_db[COLLECTION_DOCUMENTS]))

        raise MongoDBUnavailableError(
            f"Cannot store document: MongoDB Atlas is disconnected. ({self._connection_error})"
        )

    def store_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """
        Stores document chunks with embeddings in rag_chunks.
        In production, raises MongoDBUnavailableError if Atlas is unreachable.
        """
        if not chunks:
            return 0

        if self._is_connected and self._db is not None:
            res = self._db[COLLECTION_CHUNKS].insert_many(chunks)
            return len(res.inserted_ids)

        if self.allow_fallback:
            logger.warning("[MongoDB] Using explicitly allowed in-memory fallback for store_chunks.")
            _simulated_db[COLLECTION_CHUNKS].extend(chunks)
            return len(chunks)

        raise MongoDBUnavailableError(
            f"Cannot store chunks: MongoDB Atlas is disconnected. ({self._connection_error})"
        )

    def find_chunks(self, query_filter: Dict[str, Any], limit: int = 20) -> List[Dict[str, Any]]:
        """Queries chunks with metadata filters."""
        if self._is_connected and self._db is not None:
            cursor = self._db[COLLECTION_CHUNKS].find(query_filter).limit(limit)
            return list(cursor)

        if self.allow_fallback:
            res = []
            for c in _simulated_db[COLLECTION_CHUNKS]:
                match = True
                for k, v in query_filter.items():
                    if c.get(k) != v:
                        match = False
                        break
                if match:
                    res.append(c)
                if len(res) >= limit:
                    break
            return res

        raise MongoDBUnavailableError(
            f"Cannot query chunks: MongoDB Atlas is disconnected. ({self._connection_error})"
        )

    def delete_document_chunks(self, document_id: str) -> int:
        """Removes all chunks and metadata for a document."""
        if self._is_connected and self._db is not None:
            res = self._db[COLLECTION_CHUNKS].delete_many({"document_id": document_id})
            self._db[COLLECTION_DOCUMENTS].delete_one({"_id": document_id})
            return res.deleted_count

        if self.allow_fallback:
            prev = len(_simulated_db[COLLECTION_CHUNKS])
            _simulated_db[COLLECTION_CHUNKS] = [
                c for c in _simulated_db[COLLECTION_CHUNKS] if str(c.get("document_id")) != str(document_id)
            ]
            _simulated_db[COLLECTION_DOCUMENTS] = [
                d for d in _simulated_db[COLLECTION_DOCUMENTS] if str(d.get("_id")) != str(document_id)
            ]
            return prev - len(_simulated_db[COLLECTION_CHUNKS])

        raise MongoDBUnavailableError(
            f"Cannot delete document chunks: MongoDB Atlas is disconnected. ({self._connection_error})"
        )


# Global singleton instance
mongodb_manager = MongoDBManager()
