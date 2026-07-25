"""
LangGraph Workflow
--------------------
Wires the five agents into a single stateful graph:

                         ┌─────────────────────────┐
                         │  document_verification   │
                         └────────────┬─────────────┘
                                       │
                     doc invalid? ──── ┴ ──── doc valid?
                            │                     │
                            │        ┌────────────┼────────────┐
                            │        │            │            │
                            │  policy_verif  medical_valid  fraud_detect   (parallel fan-out)
                            │        │            │            │
                            │        └────────────┼────────────┘
                            │                     │
                            └───────────► decision_agent ◄───┘
                                                   │
                                                  END

* State: graph/state.py ClaimState (TypedDict merged across nodes)
* Conditional edges: `route_after_document_check` short-circuits straight to
  the decision agent if the document itself is invalid — no point running
  policy/medical/fraud checks on a claim with no valid supporting document.
* Parallel execution: policy_verification, medical_validation and
  fraud_detection all read the same upstream state and have no dependency
  on each other, so LangGraph runs them in the same superstep (true
  concurrency, not just sequential calls).
* Retries: every node is wrapped in `with_retries`, which retries transient
  failures (e.g. Ollama timeout, MCP subprocess hiccup) up to 2 times before
  recording a structured error and degrading gracefully instead of crashing
  the whole claim.
* Memory: `MemorySaver` checkpointer persists state after every superstep,
  keyed by claim_id as the thread_id — so a claim's workflow can be
  inspected, resumed, or replayed for audit purposes.
"""
import asyncio
import logging
from functools import wraps

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from graph.state import ClaimState
from agents import document_agent, policy_agent, medical_agent, fraud_agent, decision_agent

logger = logging.getLogger("graph.workflow")

MAX_RETRIES = 2


def with_retries(agent_name: str, coro_fn):
    """Wrap an agent's `run` coroutine with bounded retries + structured
    error capture, so one flaky tool call doesn't crash the entire claim."""

    @wraps(coro_fn)
    async def wrapped(state: ClaimState) -> dict:
        last_error = None
        for attempt in range(1, MAX_RETRIES + 2):
            try:
                return await coro_fn(state)
            except Exception as e:
                last_error = e
                logger.warning(f"[{agent_name}] attempt {attempt} failed: {e}")
                await asyncio.sleep(0.5 * attempt)  # simple backoff
        # All retries exhausted — degrade gracefully rather than crash the graph.
        error_msg = f"{agent_name} failed after {MAX_RETRIES + 1} attempts: {last_error}"
        logger.error(error_msg)
        if agent_name == "decision":
            return {
                "decision": "needs_review",
                "decision_reasoning": "The automated decision step failed, so this claim requires human review.",
                "confidence_score": 0.0,
                "requires_human_review": True,
                "errors": [error_msg],
                "current_stage": "decision_error",
                "trace": [{"agent": "decision_agent", "detail": {"error": error_msg}}],
            }
        return {
            agent_name: {
                "confidence": 0.0,
                "summary": f"Agent error — defaulted to manual review. ({last_error})",
                **_degraded_defaults(agent_name),
            },
            "errors": [error_msg],
            "current_stage": f"{agent_name}_error",
        }

    return wrapped


def _degraded_defaults(agent_name: str) -> dict:
    """Safe, review-forcing default payloads per agent when a hard failure occurs."""
    defaults = {
        "document_verification": {"is_valid": False, "document_type": "unknown", "issues": ["agent_failure"]},
        "policy_verification": {"policy_active": False, "procedure_covered": False, "sufficient_balance": False},
        "medical_validation": {"clinically_plausible": False, "cost_within_range": False},
        "fraud_detection": {"fraud_score": 1.0, "risk_reasons": ["agent_failure_treated_as_high_risk"]},
    }
    return defaults.get(agent_name, {})


def route_after_document_check(state: ClaimState) -> list[str]:
    """Conditional edge: skip straight to the decision agent if the document
    itself is invalid; otherwise fan out to all three parallel agents."""
    doc_result = state.get("document_verification", {}) or {}
    if not doc_result.get("is_valid", False):
        return ["decision_agent"]
    return ["policy_verification", "medical_validation", "fraud_detection"]


def build_graph():
    graph = StateGraph(ClaimState)

    # Node names must not duplicate keys in ClaimState.  The agent outputs
    # intentionally use names such as "document_verification", so give the
    # execution nodes a distinct "_agent" suffix.
    graph.add_node("document_verification_agent", with_retries("document_verification", document_agent.run))
    graph.add_node("policy_verification_agent", with_retries("policy_verification", policy_agent.run))
    graph.add_node("medical_validation_agent", with_retries("medical_validation", medical_agent.run))
    graph.add_node("fraud_detection_agent", with_retries("fraud_detection", fraud_agent.run))
    graph.add_node("decision_agent", with_retries("decision", decision_agent.run))

    graph.set_entry_point("document_verification_agent")

    graph.add_conditional_edges(
        "document_verification_agent",
        route_after_document_check,
        {
            "decision_agent": "decision_agent",
            "policy_verification": "policy_verification_agent",
            "medical_validation": "medical_validation_agent",
            "fraud_detection": "fraud_detection_agent",
        },
    )

    # Parallel branches converge on decision_agent
    graph.add_edge("policy_verification_agent", "decision_agent")
    graph.add_edge("medical_validation_agent", "decision_agent")
    graph.add_edge("fraud_detection_agent", "decision_agent")

    graph.add_edge("decision_agent", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


async def run_claim_workflow(initial_state: dict):
    """Execute the full graph for one claim, streaming stage updates back
    to the caller (used by the API to push live progress to the frontend)."""
    graph = get_graph()
    config = {"configurable": {"thread_id": initial_state["claim_id"]}}

    async for event in graph.astream(initial_state, config=config, stream_mode="values"):
        yield event
