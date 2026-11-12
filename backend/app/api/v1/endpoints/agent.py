"""
AlphaNexus — Agentic Research API Endpoints
=============================================

POST /api/v1/agent/research        — Synchronous research (returns full result)
POST /api/v1/agent/research/stream — SSE streaming research

GET  /api/v1/agent/sessions        — List research sessions
POST /api/v1/agent/sessions        — Create session
GET  /api/v1/agent/sessions/{id}   — Get session with messages
DELETE /api/v1/agent/sessions/{id} — Delete session

GET  /api/v1/agent/status          — Agent health / tool availability
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db, parse_uuid
from app.core.logging import logger
from app.engines.agent.orchestrator import research_orchestrator
from app.models.company import Company
from app.models.research import ResearchSession, ResearchMessage, Citation
from app.schemas.research import (
    ResearchMessageResponse,
    ResearchSessionResponse,
    CitationResponse,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class AgentResearchRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Research question")
    research_mode: str = Field(
        default="quick",
        description="quick | deep | live | document | comparative | event",
    )
    company_symbol: Optional[str] = Field(None, description="NSE ticker e.g. RELIANCE")
    company_id: Optional[str] = Field(None, description="AlphaNexus company UUID")
    financial_year: Optional[str] = Field(None, description="e.g. FY24, FY25")
    document_type: Optional[str] = Field(None, description="e.g. Annual Report")
    session_id: Optional[str] = None


class AgentResearchResponse(BaseModel):
    session_id: str
    message_id: str
    query: str
    answer: str
    answer_type: str
    research_mode: str
    company: Optional[str]
    tools_used: List[str]
    sources: List[str]
    started_at: Optional[str]
    completed_at: Optional[str]
    citations: List[CitationResponse] = []


class AgentStatusResponse(BaseModel):
    status: str
    tools_available: List[str]
    llm_configured: bool
    llm_provider: Optional[str]
    indianapi_configured: bool
    marketaux_configured: bool
    rag_available: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_company(payload: AgentResearchRequest, db: Session):
    """Resolve company_symbol and company_id from the request."""
    symbol = payload.company_symbol
    comp_id = payload.company_id

    if comp_id and not symbol:
        c = db.query(Company).filter(Company.id == parse_uuid(comp_id)).first()
        if c:
            symbol = c.symbol

    if symbol and not comp_id:
        c = db.query(Company).filter(Company.symbol == symbol.upper()).first()
        if c:
            comp_id = str(c.id)

    return symbol, comp_id


def _get_or_create_session(
    session_id: Optional[str],
    query: str,
    comp_uuid,
    db: Session,
) -> ResearchSession:
    if session_id:
        sess = db.query(ResearchSession).filter(
            ResearchSession.id == parse_uuid(session_id)
        ).first()
        if sess:
            return sess

    title = query[:60] + ("…" if len(query) > 60 else "")
    sess = ResearchSession(title=title, company_id=comp_uuid)
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


def _persist_messages(
    db: Session,
    sess: ResearchSession,
    query: str,
    result: dict,
) -> ResearchMessage:
    """Save user query + assistant answer to research_messages."""
    # User message
    user_msg = ResearchMessage(
        session_id=sess.id,
        role="user",
        content=query,
        message_type="user_query",
        token_count=0,
    )
    db.add(user_msg)

    # Assistant message
    asst_msg = ResearchMessage(
        session_id=sess.id,
        role="assistant",
        content=result.get("final_answer", ""),
        message_type=result.get("answer_type", "synthesis"),
        token_count=0,
    )
    db.add(asst_msg)
    db.commit()
    db.refresh(asst_msg)
    db.refresh(sess)

    # Update session updated_at
    sess.updated_at = datetime.utcnow()
    db.commit()
    return asst_msg


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/research", response_model=AgentResearchResponse)
def run_research(payload: AgentResearchRequest, db: Session = Depends(get_db)):
    """
    Synchronous agentic research endpoint.
    Runs the full LangGraph pipeline and returns the complete result.
    Use /research/stream for progressive SSE delivery.
    """
    symbol, comp_id = _resolve_company(payload, db)
    comp_uuid = parse_uuid(comp_id) if comp_id else None
    sess = _get_or_create_session(payload.session_id, payload.query, comp_uuid, db)

    result = research_orchestrator.run(
        query=payload.query,
        research_mode=payload.research_mode,
        company_symbol=symbol,
        company_id=comp_id,
        financial_year=payload.financial_year,
        document_type=payload.document_type,
        session_id=str(sess.id),
    )

    asst_msg = _persist_messages(db, sess, payload.query, result)

    return AgentResearchResponse(
        session_id=str(sess.id),
        message_id=str(asst_msg.id),
        query=payload.query,
        answer=result.get("final_answer", ""),
        answer_type=result.get("answer_type", "synthesis"),
        research_mode=payload.research_mode,
        company=symbol,
        tools_used=result.get("tools_used", []),
        sources=result.get("sources_accessed", []),
        started_at=result.get("started_at"),
        completed_at=result.get("completed_at"),
    )


@router.post("/research/stream")
async def stream_research(payload: AgentResearchRequest, db: Session = Depends(get_db)):
    """
    SSE streaming research endpoint.
    Yields Server-Sent Events as the agent progresses through each stage.

    Event format:
        event: activity|answer|sources|done|error
        data: <JSON payload>

    Frontend should use EventSource or fetch with ReadableStream.
    """
    symbol, comp_id = _resolve_company(payload, db)
    comp_uuid = parse_uuid(comp_id) if comp_id else None
    sess = _get_or_create_session(payload.session_id, payload.query, comp_uuid, db)
    session_id = str(sess.id)

    def _sse_event(event_type: str, data: dict) -> str:
        return f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"

    def generate():
        final_result = {}
        try:
            for event_type, payload_data in research_orchestrator.stream_events(
                query=payload.query,
                research_mode=payload.research_mode,
                company_symbol=symbol,
                company_id=comp_id,
                financial_year=payload.financial_year,
                document_type=payload.document_type,
                session_id=session_id,
            ):
                payload_data["session_id"] = session_id
                yield _sse_event(event_type, payload_data)

                if event_type == "answer":
                    final_result = payload_data

        except Exception as exc:
            logger.error("SSE stream error: %s", exc)
            yield _sse_event("error", {"message": str(exc), "session_id": session_id})

        # Persist to DB after streaming completes
        if final_result.get("content"):
            try:
                db2 = db
                asst_msg = _persist_messages(db2, sess, payload.query, {
                    "final_answer": final_result.get("content", ""),
                    "answer_type": final_result.get("answer_type", "synthesis"),
                })
                yield _sse_event("persisted", {
                    "message_id": str(asst_msg.id),
                    "session_id": session_id,
                })
            except Exception as exc:
                logger.warning("Failed to persist streamed answer: %s", exc)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/sessions", response_model=List[ResearchSessionResponse])
def list_agent_sessions(
    limit: int = 20,
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


@router.post("/sessions")
def create_agent_session(
    company_id: Optional[str] = None,
    title: str = "New Research",
    db: Session = Depends(get_db),
):
    comp_uuid = parse_uuid(company_id) if company_id else None
    sess = ResearchSession(title=title, company_id=comp_uuid)
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return {"session_id": str(sess.id), "title": sess.title}


@router.get("/sessions/{session_id}", response_model=ResearchSessionResponse)
def get_agent_session(session_id: str, db: Session = Depends(get_db)):
    sess = db.query(ResearchSession).filter(
        ResearchSession.id == parse_uuid(session_id)
    ).first()
    if not sess:
        raise HTTPException(404, "Session not found")

    msgs = []
    for msg in sess.messages:
        cits = [
            CitationResponse(
                id=str(c.id),
                document_id=str(c.document_id),
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
            tokens_used=msg.token_count or 0,
            citations=cits,
            created_at=msg.created_at,
        ))

    return ResearchSessionResponse(
        id=str(sess.id),
        title=sess.title,
        company_id=str(sess.company_id) if sess.company_id else None,
        created_at=sess.created_at,
        updated_at=sess.updated_at,
        messages=msgs,
    )


@router.delete("/sessions/{session_id}")
def delete_agent_session(session_id: str, db: Session = Depends(get_db)):
    sess = db.query(ResearchSession).filter(
        ResearchSession.id == parse_uuid(session_id)
    ).first()
    if not sess:
        raise HTTPException(404, "Session not found")
    db.delete(sess)
    db.commit()
    return {"deleted": True, "session_id": session_id}


@router.get("/status", response_model=AgentStatusResponse)
def agent_status():
    """Returns current agent capability and provider health."""
    from app.core.config import settings
    from app.integrations.market_data.indianapi import IndianAPIProvider
    from app.integrations.news_providers.marketaux import MarketauxProvider

    indian = IndianAPIProvider()
    mktaux = MarketauxProvider()

    # Check LLM
    llm_configured = False
    llm_provider = None
    if settings.GEMINI_API_KEY:
        llm_configured = True
        llm_provider = "gemini"
    elif settings.GROQ_API_KEY:
        llm_configured = True
        llm_provider = "groq"

    # Check RAG
    try:
        from app.engines.rag.embeddings import embedding_engine
        rag_ok = embedding_engine.get_model_info().get("loaded", False)
    except Exception:
        rag_ok = False

    return AgentStatusResponse(
        status="ready" if llm_configured else "degraded",
        tools_available=[
            "get_company_live_data", "get_company_announcements",
            "get_corporate_actions", "get_market_news",
            "retrieve_company_documents", "calculate_financial_ratios",
            "get_company_profile_db",
        ],
        llm_configured=llm_configured,
        llm_provider=llm_provider,
        indianapi_configured=indian.is_configured,
        marketaux_configured=mktaux.is_configured,
        rag_available=rag_ok,
    )
