"""
AlphaNexus Agent — LangGraph State Definitions
================================================
Typed state shared across all graph nodes.

Design notes:
  - activity_log uses operator.add (append) so each node's events accumulate
  - evidence, citations, messages also accumulate across nodes
  - tools_used, sources_accessed are PLAIN LISTS (not accumulated) —
    they are SET by execute_tools and read by later nodes without re-adding
"""

from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional
from typing_extensions import TypedDict
import operator


class AgentMessage(TypedDict):
    role: str          # "user" | "assistant" | "tool"
    content: str
    tool_name: Optional[str]
    tool_result: Optional[Any]


class ResearchState(TypedDict):
    # ── Input ──────────────────────────────────────────────────────────
    query: str
    company_symbol: Optional[str]
    company_id: Optional[str]
    research_mode: str            # quick | deep | live | document | comparative | event
    financial_year: Optional[str]
    document_type: Optional[str]
    session_id: Optional[str]

    # ── Accumulating lists (each node appends its own entries) ─────────
    messages:     Annotated[List[AgentMessage],      operator.add]
    activity_log: Annotated[List[Dict[str, Any]],    operator.add]
    evidence:     Annotated[List[Dict[str, Any]],    operator.add]
    citations:    Annotated[List[Dict[str, Any]],    operator.add]
    llm_messages: Annotated[List[Dict[str, str]],    operator.add]

    # ── Plain lists (SET once by execute_tools, never re-accumulated) ──
    sources_accessed: List[str]
    tools_used:       List[str]

    # ── Plan ───────────────────────────────────────────────────────────
    research_plan:   Optional[List[str]]
    current_step:    int
    _tool_plan_json: Optional[str]  # serialized tool plan (JSON string)

    # ── Output ─────────────────────────────────────────────────────────
    final_answer: Optional[str]
    answer_type:  Optional[str]   # fact_grounded | synthesis | insufficient_data
    error:        Optional[str]
    completed:    bool

    # ── Timing ─────────────────────────────────────────────────────────
    started_at:   Optional[str]
    completed_at: Optional[str]
