"""
ALPHANEXUS – Company Application Service
=========================================
Encapsulates company discovery, profile retrieval, and master security tracking.
"""

from typing import Any, List, Optional, Dict
from uuid import UUID
from sqlalchemy.orm import Session
from app.database.repositories.company_repository import company_repository
from app.services.company_discovery import company_discovery_service


class CompanyService:

    @staticmethod
    def get_company(db: Session, company_id: Any) -> Optional[Any]:
        if isinstance(company_id, UUID):
            comp = company_repository.get_by_id(db, company_id)
            if comp:
                return comp
        return company_discovery_service.resolve_or_create(db, str(company_id))

    @staticmethod
    def list_companies(
        db: Session,
        query: Optional[str] = None,
        sector: Optional[str] = None,
        limit: int = 100,
    ) -> List[Any]:
        return company_repository.list_all(db, query=query, sector=sector, limit=limit)

    @staticmethod
    def search_companies(
        db: Session,
        query: str,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        return company_discovery_service.search(db, query=query, limit=limit)

    @staticmethod
    def resolve_or_create(
        db: Session,
        identifier: str,
    ) -> Optional[Any]:
        return company_discovery_service.resolve_or_create(db, identifier)


company_service = CompanyService()
