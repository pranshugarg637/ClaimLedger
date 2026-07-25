"""
Decision Agent
----------------
Final synthesis node. Combines every upstream agent's output, runs it
through the AI Governance layer (risk assessment, policy compliance,
human-in-the-loop gate), and asks the LLM only for the *narrative
justification* — the actual approve/reject/needs_review verdict is
determined deterministically so the system stays auditable and cannot be
talked into an unsafe decision by a manipulated prompt.
"""
from agents.llm_utils import ask_llm_json
from guardrails_engine.validators import engine as guardrails_engine
from governance.audit import (
    log_agent_action, blended_confidence, assess_risk,
    requires_human_review, policy_compliance_check, build_explainability_report,
)
from config import AUTO_APPROVE_CONFIDENCE, AUTO_REJECT_FRAUD_SCORE

SYSTEM_PROMPT = """You are the Decision Agent for a medical insurance claims system.
You are given the FINAL, ALREADY-DETERMINED decision (approved/rejected/needs_review)
plus every upstream agent's summary. Your only job is to write one clear,
professional paragraph explaining the decision to the policyholder. Do not
change the decision, and do not invent facts not present in the summaries.

Respond with ONLY a JSON object in exactly this shape:
{"decision": "<same as given>", "reasoning": "one paragraph", "confidence": 0.0-1.0}
"""


def _deterministic_decision(state: dict) -> tuple[str, float, float]:
    """The authoritative decision logic. Pure, deterministic, testable —
    the LLM never gets a vote on the verdict itself, only on the phrasing."""
    doc = state.get("document_verification", {}) or {}
    pol = state.get("policy_verification", {}) or {}
    med = state.get("medical_validation", {}) or {}
    fraud = state.get("fraud_detection", {}) or {}

    confidence = blended_confidence(
        doc.get("confidence"), pol.get("confidence"), med.get("confidence"), fraud.get("confidence"),
    )
    fraud_score = fraud.get("fraud_score", 0.0) or 0.0

    # Hard reject conditions
    if not doc.get("is_valid", False):
        return "rejected", confidence, fraud_score
    if pol.get("policy_active") is False:
        return "rejected", confidence, fraud_score
    if pol.get("procedure_covered") is False:
        return "rejected", confidence, fraud_score
    if pol.get("patient_is_covered") is False:
        return "rejected", confidence, fraud_score
    if doc.get("field_matches") is False:
        return "needs_review", confidence, fraud_score
    if fraud_score >= AUTO_REJECT_FRAUD_SCORE:
        return "rejected", confidence, fraud_score

    # Human review conditions
    if requires_human_review(fraud_score, confidence, state.get("claimed_amount")):
        return "needs_review", confidence, fraud_score
    if pol.get("sufficient_balance") is False:
        return "needs_review", confidence, fraud_score
    if med.get("clinically_plausible") is False or med.get("cost_within_range") is False:
        return "needs_review", confidence, fraud_score

    # Auto-approve
    if confidence >= AUTO_APPROVE_CONFIDENCE:
        return "approved", confidence, fraud_score

    return "needs_review", confidence, fraud_score


async def run(state: dict) -> dict:
    claim_id = state["claim_id"]

    decision, confidence, fraud_score = _deterministic_decision(state)

    user_prompt = f"""Final decision (do not change): {decision}
Document verification: {state.get('document_verification')}
Policy verification: {state.get('policy_verification')}
Medical validation: {state.get('medical_validation')}
Fraud detection: {state.get('fraud_detection')}
Blended confidence: {confidence}
"""
    parsed, raw = await ask_llm_json(SYSTEM_PROMPT, user_prompt)

    if not parsed or parsed.get("decision") != decision:
        parsed = {
            "decision": decision,
            "reasoning": _fallback_reasoning(decision, state),
            "confidence": confidence,
        }

    # Governance gates run regardless of what the LLM said
    working_state = {**state, "decision": decision, "confidence_score": confidence,
                      "requires_human_review": decision == "needs_review"}
    compliance = policy_compliance_check(working_state)
    if not compliance["compliant"]:
        decision = "needs_review"
        parsed["decision"] = decision
        parsed["reasoning"] += " [Escalated to human review due to policy compliance check.]"

    risk = assess_risk(fraud_score, confidence, state.get("claimed_amount"))

    final_state = {**state, "decision": decision, "confidence_score": confidence,
                   "requires_human_review": decision == "needs_review"}
    explainability = build_explainability_report(final_state)

    log_agent_action(claim_id, "decision_agent", "finalize_decision",
                      {"fraud_score": fraud_score, "confidence": confidence},
                      {"decision": decision, "reasoning": parsed.get("reasoning")},
                      confidence, parsed.get("reasoning"))

    return {
        "decision": decision,
        "decision_reasoning": parsed.get("reasoning"),
        "confidence_score": confidence,
        "requires_human_review": decision == "needs_review",
        "governance_report": {
            "risk_assessment": risk,
            "policy_compliance": compliance,
            "explainability": explainability,
        },
        "current_stage": "completed",
        "trace": [{"agent": "decision_agent", "detail": {"decision": decision, "fraud_score": fraud_score},
                   "llm_raw": raw}],
    }


def _fallback_reasoning(decision: str, state: dict) -> str:
    reasons = []
    doc = state.get("document_verification", {}) or {}
    pol = state.get("policy_verification", {}) or {}
    med = state.get("medical_validation", {}) or {}
    fraud = state.get("fraud_detection", {}) or {}

    if doc.get("summary"):
        reasons.append(doc["summary"])
    if pol.get("summary"):
        reasons.append(pol["summary"])
    if med.get("summary"):
        reasons.append(med["summary"])
    if fraud.get("summary"):
        reasons.append(fraud["summary"])

    prefix = {
        "approved": "This claim has been approved.",
        "rejected": "This claim has been rejected.",
        "needs_review": "This claim requires manual review by a claims officer.",
    }.get(decision, "This claim's status has been determined.")

    return prefix + " " + " ".join(reasons)
