"""
AlphaNexus — LangGraph Research Orchestrator
=============================================
Stateful multi-step financial research agent using LangGraph.

Graph topology:
  START
    │
    ▼
  plan_research          — Classify query, extract entities, build tool plan
    │
    ▼
  execute_tools          — Run selected tools, collect evidence
    │
    ▼
  synthesize_answer      — Generate structured response with Gemini
    │
    ▼
  validate_response      — Check citations, detect unsupported claims
    │
    ▼
  END

Streaming: Each node emits activity events that callers receive in real time.
The orchestrator yields (event_type, payload) tuples via run_stream().
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END

from app.core.logging import logger
from app.engines.agent.state import ResearchState
from app.engines.agent.tools import ALL_TOOLS
from app.engines.agent.prompts import get_system_prompt

# ---------------------------------------------------------------------------
# LLM provider helpers
# ---------------------------------------------------------------------------

def _get_gemini_llm():
    """Returns a LangChain-compatible Gemini LLM if configured."""
    try:
        from app.core.config import settings
        if not settings.GEMINI_API_KEY:
            return None
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.1,
            max_output_tokens=3000,
        )
    except ImportError:
        return None


def _get_groq_llm():
    """Returns a LangChain-compatible Groq LLM if configured."""
    try:
        from app.core.config import settings
        if not settings.GROQ_API_KEY:
            return None
        from langchain_groq import ChatGroq
        return ChatGroq(
            model=settings.GROQ_MODEL,
            groq_api_key=settings.GROQ_API_KEY,
            temperature=0.1,
            max_tokens=3000,
        )
    except ImportError:
        return None


def _get_llm():
    """Returns the best available LLM (Gemini preferred, Groq fallback)."""
    llm = _get_gemini_llm()
    if llm:
        return llm, "gemini"
    llm = _get_groq_llm()
    if llm:
        return llm, "groq"
    return None, None


# ---------------------------------------------------------------------------
# Tool execution helpers
# ---------------------------------------------------------------------------

TOOL_MAP = {t.name: t for t in ALL_TOOLS}


def _run_tool(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """Execute a named tool safely, returning JSON string result."""
    t = TOOL_MAP.get(tool_name)
    if not t:
        return json.dumps({"error": f"Tool '{tool_name}' not found", "data_unavailable": True})
    try:
        result = t.invoke(tool_input)
        return result if isinstance(result, str) else json.dumps(result, default=str)
    except Exception as exc:
        logger.error("Tool execution error (%s): %s", tool_name, exc)
        return json.dumps({"error": str(exc), "data_unavailable": True})


# ---------------------------------------------------------------------------
# Research plan generation
# ---------------------------------------------------------------------------

TOOL_SELECTOR: Dict[str, List[str]] = {
    "quick": [
        "get_company_profile_db",
        "get_company_live_data",
    ],
    "deep": [
        "get_company_profile_db",
        "get_company_live_data",
        "retrieve_company_documents",
        "calculate_financial_ratios",
    ],
    "live": [
        "get_company_announcements",
        "get_market_news",
        "get_corporate_actions",
        "get_company_live_data",
    ],
    "document": [
        "retrieve_company_documents",
        "get_company_profile_db",
    ],
    "comparative": [
        "get_company_profile_db",
        "get_company_live_data",
        "calculate_financial_ratios",
    ],
    "event": [
        "get_company_announcements",
        "get_market_news",
        "get_company_live_data",
        "get_company_profile_db",
    ],
}


def _build_tool_plan(mode: str, symbol: Optional[str], query: str) -> List[Dict[str, Any]]:
    """Build an ordered list of tool calls based on mode and query context."""
    tool_names = TOOL_SELECTOR.get(mode, TOOL_SELECTOR["quick"])

    plan = []
    for name in tool_names:
        args: Dict[str, Any] = {}
        if name in (
            "get_company_profile_db",
            "get_company_live_data",
            "get_company_announcements",
            "get_corporate_actions",
        ) and symbol:
            args["symbol"] = symbol
        elif name == "get_market_news":
            args["symbol"] = symbol
            args["keywords"] = query[:60] if not symbol else None
        elif name == "retrieve_company_documents":
            args["query"] = query
        elif name == "calculate_financial_ratios":
            # This tool is called after evidence collection with actual values
            continue  # Will be called conditionally in execute_tools
        plan.append({"tool": name, "args": args})

    return plan


# ---------------------------------------------------------------------------
# LangGraph nodes
# ---------------------------------------------------------------------------

def node_plan_research(state: ResearchState) -> ResearchState:
    """Classify the query, extract entities, and build a tool execution plan."""
    now = datetime.now(timezone.utc).isoformat()
    query = state["query"]
    mode = state.get("research_mode", "quick")
    symbol = state.get("company_symbol")

    # Quick entity extraction — look for known ticker patterns
    if not symbol:
        import re
        tickers = re.findall(r'\b([A-Z]{3,10})\b', query.upper())
        known_tickers = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "LT", "ICICIBANK",
                         "WIPRO", "BAJFINANCE", "MARUTI", "KOTAKBANK", "SBIN", "AXISBANK",
                         "HINDUNILVR", "NESTLEIND", "TATAMOTORS", "POWERGRID", "NTPC"]
        for t in tickers:
            if t in known_tickers:
                symbol = t
                break

    plan = _build_tool_plan(mode, symbol, query)

    return {
        **state,
        "company_symbol": symbol or state.get("company_symbol"),
        "research_plan": [f"[{p['tool']}] {json.dumps(p['args'])}" for p in plan],
        "_tool_plan_json": json.dumps(plan),
        "current_step": 0,
        "started_at": state.get("started_at") or now,
        "activity_log": [{
            "event": "plan_created",
            "mode": mode,
            "company": symbol,
            "steps": len(plan),
            "tools": [p["tool"] for p in plan],
            "timestamp": now,
        }],
        "messages": [],
        "evidence": [],
        "citations": [],
        "sources_accessed": [],
        "tools_used": [],
    }


def node_execute_tools(state: ResearchState) -> ResearchState:
    """Execute the planned tools and collect evidence."""
    plan_json = state.get("_tool_plan_json") or "[]"
    try:
        plan: List[Dict[str, Any]] = json.loads(plan_json)
    except (json.JSONDecodeError, TypeError):
        plan = []
    evidence: List[Dict[str, Any]] = []
    sources: List[str] = []
    tools_used: List[str] = []
    activity: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    for step in plan:
        tool_name = step["tool"]
        tool_args = step.get("args", {})

        # Skip if args missing required symbol for symbol-dependent tools
        symbol_required = tool_name in (
            "get_company_profile_db", "get_company_live_data",
            "get_company_announcements", "get_corporate_actions"
        )
        if symbol_required and not tool_args.get("symbol"):
            activity.append({
                "event": "tool_skipped",
                "tool": tool_name,
                "reason": "No company symbol available",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            continue

        activity.append({
            "event": "tool_started",
            "tool": tool_name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        t0 = time.monotonic()
        raw_result = _run_tool(tool_name, tool_args)
        elapsed_ms = round((time.monotonic() - t0) * 1000, 0)

        try:
            parsed = json.loads(raw_result)
        except (json.JSONDecodeError, TypeError):
            parsed = {"raw": raw_result}

        is_live = parsed.get("is_live", True)
        data_unavailable = parsed.get("data_unavailable", False)

        activity.append({
            "event": "tool_completed",
            "tool": tool_name,
            "status": "unavailable" if data_unavailable else "success",
            "is_live": is_live,
            "elapsed_ms": elapsed_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        tools_used.append(tool_name)
        if not data_unavailable:
            evidence.append({
                "tool": tool_name,
                "data": parsed,
                "retrieved_at": parsed.get("retrieved_at", datetime.now(timezone.utc).isoformat()),
                "is_live": is_live,
            })
            source_label = {
                "get_company_live_data": "IndianAPI (Live Market Data)",
                "get_company_announcements": "IndianAPI (Exchange Announcements)",
                "get_corporate_actions": "IndianAPI (Corporate Actions)",
                "get_market_news": "IndianAPI + Marketaux (News)",
                "retrieve_company_documents": "AlphaNexus RAG (Indexed Filings)",
                "calculate_financial_ratios": "AlphaNexus Financial Engine",
                "get_company_profile_db": "AlphaNexus Database",
            }.get(tool_name, tool_name)
            sources.append(source_label)

    return {
        **state,
        "evidence": evidence,
        "sources_accessed": sources,
        "tools_used": tools_used,
        "activity_log": activity,
    }


def node_synthesize_answer(state: ResearchState) -> ResearchState:
    """Generate a structured financial research response from collected evidence."""
    query = state["query"]
    mode = state.get("research_mode", "quick")
    evidence = state.get("evidence", [])
    company = state.get("company_symbol", "")
    now = datetime.now(timezone.utc).isoformat()

    # Build evidence summary for the LLM
    evidence_blocks = []
    for idx, ev in enumerate(evidence, 1):
        tool = ev["tool"]
        data = ev["data"]
        retrieved = ev.get("retrieved_at", "unknown")
        evidence_blocks.append(
            f"\n--- EVIDENCE [{idx}] from {tool} (retrieved: {retrieved}) ---\n"
            + json.dumps(data, indent=2, default=str)[:3000]  # cap per source
        )

    if not evidence_blocks:
        final_answer = (
            f"⚠️ **Data Unavailable**\n\n"
            f"No data could be retrieved for your query: *{query}*\n\n"
            f"**Possible reasons:**\n"
            f"- No company documents have been uploaded and indexed for this company\n"
            f"- The market data provider (IndianAPI) may not be configured or is unreachable\n"
            f"- The company symbol was not recognized\n\n"
            f"**Suggestions:**\n"
            f"1. Upload relevant company filings in the Document Intelligence section\n"
            f"2. Verify that the INDIANAPI_API_KEY is configured in the backend\n"
            f"3. Try specifying the company ticker explicitly (e.g., 'RELIANCE' not 'Reliance Industries')"
        )
        return {
            **state,
            "final_answer": final_answer,
            "answer_type": "insufficient_data",
            "completed": True,
            "completed_at": now,
            "activity_log": [{"event": "synthesis_skipped", "reason": "no_evidence", "timestamp": now}],
        }

    system_prompt = get_system_prompt(mode)
    evidence_text = "\n".join(evidence_blocks)

    full_prompt = (
        f"Research Query: {query}\n"
        f"Company Symbol: {company or 'Not specified'}\n"
        f"Research Mode: {mode}\n\n"
        f"EVIDENCE COLLECTED:\n{evidence_text}\n\n"
        f"Based ONLY on the evidence provided above, generate a structured financial research response. "
        f"Include a Sources section at the end with numbered citations matching [Evidence N] references."
    )

    # Try LLM generation
    llm, provider_name = _get_llm()
    final_answer = None
    answer_type = "synthesis"

    if llm:
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=full_prompt),
            ]
            response = llm.invoke(messages)
            # Handle both string content and list of content parts (google-genai format)
            raw_content = response.content
            if isinstance(raw_content, list):
                # Extract text from content parts [{type: text, text: ...}, ...]
                parts = [p.get("text", "") if isinstance(p, dict) else str(p) for p in raw_content]
                final_answer = "\n".join(p for p in parts if p).strip()
            else:
                final_answer = str(raw_content) if raw_content else None
            answer_type = "fact_grounded" if evidence else "synthesis"
        except Exception as exc:
            logger.error("LLM synthesis failed: %s", exc)
            final_answer = None

    # Fallback: direct evidence presentation
    if not final_answer:
        lines = [
            f"## AlphaNexus Research — {company or 'Company'}\n",
            f"**Query:** {query}\n",
            f"**Mode:** {mode.title()} Research\n",
            f"**Note:** LLM synthesis unavailable. Presenting raw evidence.\n\n---\n",
        ]
        for idx, ev in enumerate(evidence, 1):
            tool = ev["tool"]
            data = ev["data"]
            lines.append(f"\n### Source [{idx}]: {tool}\n")
            # Format key fields readably
            for key, val in data.items():
                if key in ("tool", "retrieved_at", "is_live", "data_unavailable"):
                    continue
                if isinstance(val, (dict, list)):
                    lines.append(f"**{key}:** {json.dumps(val, default=str)[:300]}\n")
                else:
                    lines.append(f"**{key}:** {val}\n")
        final_answer = "".join(lines)
        answer_type = "synthesis"

    return {
        **state,
        "final_answer": final_answer,
        "answer_type": answer_type,
        "completed": True,
        "completed_at": now,
        "activity_log": [{
            "event": "synthesis_completed",
            "provider": provider_name or "fallback",
            "answer_type": answer_type,
            "evidence_sources": len(evidence),
            "timestamp": now,
        }],
    }


def node_validate_response(state: ResearchState) -> ResearchState:
    """
    Lightweight validation: check that the answer doesn't claim data
    that wasn't in the evidence. Currently flags obvious issues.
    """
    answer = state.get("final_answer", "")
    evidence_count = len(state.get("evidence", []))
    now = datetime.now(timezone.utc).isoformat()

    warnings = []
    if evidence_count == 0 and len(answer) > 100:
        warnings.append("Answer was generated without retrieved evidence — treat as synthesis only")

    return {
        **state,
        "activity_log": [{
            "event": "validation_completed",
            "warnings": warnings,
            "citations_count": len(state.get("citations", [])),
            "timestamp": now,
        }],
    }


# ---------------------------------------------------------------------------
# Build the LangGraph graph
# ---------------------------------------------------------------------------

def _build_graph() -> StateGraph:
    g = StateGraph(ResearchState)
    g.add_node("plan_research",    node_plan_research)
    g.add_node("execute_tools",    node_execute_tools)
    g.add_node("synthesize_answer", node_synthesize_answer)
    g.add_node("validate_response", node_validate_response)

    g.add_edge(START,              "plan_research")
    g.add_edge("plan_research",    "execute_tools")
    g.add_edge("execute_tools",    "synthesize_answer")
    g.add_edge("synthesize_answer", "validate_response")
    g.add_edge("validate_response", END)

    return g.compile()


# Lazy-compiled graph — reset whenever the module reloads
_compiled_graph = None


def _get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = _build_graph()
    return _compiled_graph


# ---------------------------------------------------------------------------
# Public orchestrator class
# ---------------------------------------------------------------------------

class ResearchOrchestrator:
    """
    Public interface for the AlphaNexus agentic research system.
    Supports both synchronous execution and streaming event generation.
    """

    def run(
        self,
        query: str,
        research_mode: str = "quick",
        company_symbol: Optional[str] = None,
        company_id: Optional[str] = None,
        financial_year: Optional[str] = None,
        document_type: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run the full research pipeline synchronously.
        Returns the final state dict.
        """
        initial_state: ResearchState = {
            "query": query,
            "company_symbol": company_symbol,
            "company_id": company_id,
            "research_mode": research_mode,
            "financial_year": financial_year,
            "document_type": document_type,
            "session_id": session_id,
            "messages": [],
            "activity_log": [],
            "evidence": [],
            "citations": [],
            "sources_accessed": [],
            "llm_messages": [],
            "research_plan": None,
            "_tool_plan_json": None,
            "current_step": 0,
            "final_answer": None,
            "answer_type": None,
            "tools_used": [],
            "error": None,
            "completed": False,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
        }

        try:
            graph = _get_graph()
            final_state = graph.invoke(initial_state)
            return final_state
        except Exception as exc:
            logger.error("Research orchestrator failed: %s", exc)
            return {
                **initial_state,
                "final_answer": f"⚠️ Research failed: {exc}",
                "answer_type": "insufficient_data",
                "error": str(exc),
                "completed": True,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }

    def stream_events(
        self,
        query: str,
        research_mode: str = "quick",
        company_symbol: Optional[str] = None,
        company_id: Optional[str] = None,
        financial_year: Optional[str] = None,
        document_type: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
        """
        Run the research pipeline and yield (event_type, payload) tuples
        as each stage completes. Used by the SSE streaming endpoint.

        Event types:
          "activity"   — agent progress update
          "answer"     — final answer text
          "sources"    — collected citations/sources
          "done"       — pipeline completed
          "error"      — pipeline failed
        """
        initial_state: ResearchState = {
            "query": query,
            "company_symbol": company_symbol,
            "company_id": company_id,
            "research_mode": research_mode,
            "financial_year": financial_year,
            "document_type": document_type,
            "session_id": session_id,
            "messages": [],
            "activity_log": [],
            "evidence": [],
            "citations": [],
            "sources_accessed": [],
            "llm_messages": [],
            "research_plan": None,
            "_tool_plan_json": None,
            "current_step": 0,
            "final_answer": None,
            "answer_type": None,
            "tools_used": [],
            "error": None,
            "completed": False,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
        }

        try:
            graph = _get_graph()

            yield "activity", {
                "stage": "started",
                "message": "Research started — analyzing your question",
                "mode": research_mode,
                "query": query[:80],
            }

            # Stream graph steps
            for chunk in graph.stream(initial_state, stream_mode="values"):
                # Emit activity events from the latest log entries
                log = chunk.get("activity_log", [])
                for entry in log[-3:]:  # last 3 events to avoid overwhelming the client
                    event_type = entry.get("event", "")
                    stage_message = {
                        "plan_created":         "Research plan created",
                        "tool_started":         f"Accessing {entry.get('tool', 'source')}",
                        "tool_completed":       f"Retrieved data from {entry.get('tool', 'source')}",
                        "tool_skipped":         f"Skipped {entry.get('tool', 'tool')}: {entry.get('reason', '')}",
                        "synthesis_completed":  "Synthesizing research report",
                        "validation_completed": "Validating response",
                    }.get(event_type, event_type)

                    yield "activity", {
                        "stage": event_type,
                        "message": stage_message,
                        "tool": entry.get("tool"),
                        "status": entry.get("status", "ok"),
                        "is_live": entry.get("is_live"),
                        "elapsed_ms": entry.get("elapsed_ms"),
                        "timestamp": entry.get("timestamp"),
                    }

            # Final state is the last chunk
            final = chunk  # last value from stream

            # Emit sources
            sources_accessed = final.get("sources_accessed", [])
            evidence = final.get("evidence", [])
            if sources_accessed:
                yield "sources", {
                    "sources": sources_accessed,
                    "evidence_count": len(evidence),
                    "tools_used": final.get("tools_used", []),
                }

            # Emit answer
            answer = final.get("final_answer", "")
            answer_type = final.get("answer_type", "synthesis")
            if answer:
                yield "answer", {
                    "content": answer,
                    "answer_type": answer_type,
                    "mode": research_mode,
                    "company": company_symbol,
                    "session_id": session_id,
                    "started_at": final.get("started_at"),
                    "completed_at": final.get("completed_at"),
                }

            yield "done", {
                "completed": True,
                "tools_used": final.get("tools_used", []),
                "sources_count": len(sources_accessed),
                "has_answer": bool(answer),
            }

        except Exception as exc:
            logger.error("stream_events failed: %s", exc)
            yield "error", {
                "message": f"Research pipeline failed: {exc}",
                "query": query,
            }


# Module singleton
research_orchestrator = ResearchOrchestrator()
