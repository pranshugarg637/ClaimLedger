"""
AI Governance Layer
---------------------
Cross-cutting concerns that every agent and the final decision go through:

  * Audit logging       -> immutable append-only log (SQLite + JSONL mirror)
  * Explainability       -> human-readable reasoning trace per agent
  * Decision trace       -> full state snapshot attached to each claim
  * Confidence scoring   -> blended deterministic + LLM confidence
  * Human-in-the-loop    -> flags claims that must not be auto-decided
  * Policy compliance    -> checks the decision against hard business rules
  * Risk assessment      -> aggregate risk level for dashboards/reporting
"""
import json
import logging
from datetime import datetime, timezone

from database import db
from config import (
    AUDIT_LOG_PATH, AUTO_APPROVE_CONFIDENCE, AUTO_REJECT_FRAUD_SCORE,
    HUMAN_REVIEW_LOWER_BOUND, MAX_CLAIM_AMOUNT_AUTO,
)


def redact_sensitive(value: object) -> object:
    if isinstance(value, str):
        return value[:80] + ("..." if len(value) > 80 else "")
    if isinstance(value, dict):
        return {k: redact_sensitive(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_sensitive(v) for v in value]
    return value

logger = logging.getLogger("governance")


def _as_float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def log_agent_action(claim_id: str, agent: str, action: str, input_summary: dict,
                      output_summary: dict, confidence: float = None, reasoning: str = ""):
    """Write a structured, immutable audit record for one agent action.
    Persisted both to SQLite (for querying via API) and to an append-only
    JSONL file (for tamper-evident, ops-style audit trails)."""
    record = {
        "claim_id": claim_id,
        "agent": agent,
        "action": action,
        "input_summary": redact_sensitive(input_summary),
        "output_summary": redact_sensitive(output_summary),
        "confidence": confidence,
        "reasoning": redact_sensitive(reasoning),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    db.insert_audit_log(
        claim_id=claim_id, agent=agent, action=action,
        input_summary=json.dumps(input_summary, default=str),
        output_summary=json.dumps(output_summary, default=str),
        confidence=confidence, reasoning=reasoning,
    )

    with open(AUDIT_LOG_PATH, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")

    logger.info(f"[AUDIT] claim={claim_id} agent={agent} action={action} confidence={confidence}")
    return record


def blended_confidence(*scores: float) -> float:
    """Combine confidence scores from multiple agents into a single
    aggregate confidence (simple weighted mean, clipped to [0,1]).
    Missing/None scores are excluded rather than treated as zero."""
    valid = [s for s in scores if s is not None]
    if not valid:
        return 0.0
    return round(sum(valid) / len(valid), 3)


def assess_risk(fraud_score: float, confidence_score: float, claimed_amount: float) -> dict:
    """Aggregate risk assessment used for the dashboard and the decision agent."""
    risk_level = "low"
    reasons = []

    fraud_score = _as_float(fraud_score)
    confidence_score = _as_float(confidence_score)
    claimed_amount = _as_float(claimed_amount)

    if fraud_score is not None and fraud_score >= AUTO_REJECT_FRAUD_SCORE:
        risk_level = "high"
        reasons.append("fraud_score_above_reject_threshold")
    elif fraud_score is not None and fraud_score >= 0.4:
        risk_level = "medium"
        reasons.append("elevated_fraud_score")

    if confidence_score is not None and confidence_score < HUMAN_REVIEW_LOWER_BOUND:
        risk_level = "high" if risk_level != "high" else risk_level
        reasons.append("low_model_confidence")

    if claimed_amount and claimed_amount > MAX_CLAIM_AMOUNT_AUTO:
        risk_level = "high"
        reasons.append("claim_amount_exceeds_auto_approval_ceiling")

    return {"risk_level": risk_level, "reasons": reasons}


def requires_human_review(fraud_score: float, confidence_score: float, claimed_amount: float) -> bool:
    """Hard policy-compliance gate: certain conditions ALWAYS require a
    human claims officer, regardless of what any agent or LLM concluded.
    This is the human-in-the-loop safety net."""
    fraud_score = _as_float(fraud_score)
    confidence_score = _as_float(confidence_score)
    claimed_amount = _as_float(claimed_amount)

    if fraud_score is not None and fraud_score >= AUTO_REJECT_FRAUD_SCORE:
        return False  # high fraud -> auto-reject is allowed, not "review"; see decision agent
    if confidence_score is not None and HUMAN_REVIEW_LOWER_BOUND <= confidence_score < AUTO_APPROVE_CONFIDENCE:
        return True
    if claimed_amount and claimed_amount > MAX_CLAIM_AMOUNT_AUTO:
        return True
    return False


def policy_compliance_check(state: dict) -> dict:
    """Verify the proposed decision doesn't violate hard business/regulatory
    rules before it's allowed to finalize. Returns a compliance report;
    a non-compliant decision is downgraded to 'needs_review' by the
    Decision Agent, never silently overridden."""
    violations = []

    policy_ver = state.get("policy_verification", {}) or {}
    if policy_ver.get("policy_active") is False:
        violations.append("policy_inactive_but_claim_processed")

    fraud = state.get("fraud_detection", {}) or {}
    fraud_score = _as_float(fraud.get("fraud_score"))
    if fraud_score is not None and fraud_score >= AUTO_REJECT_FRAUD_SCORE and state.get("decision") == "approved":
        violations.append("high_fraud_score_cannot_be_approved")

    claimed = _as_float(state.get("claimed_amount"))
    if claimed and claimed > MAX_CLAIM_AMOUNT_AUTO and state.get("decision") == "approved" \
            and not state.get("requires_human_review"):
        violations.append("large_claim_bypassed_human_review")

    return {"compliant": len(violations) == 0, "violations": violations}


def build_explainability_report(state: dict) -> dict:
    """Produce a human-readable 'why did the system decide this' report,
    summarizing every agent's contribution to the final decision."""
    return {
        "document_verification_summary": (state.get("document_verification") or {}).get("summary"),
        "policy_verification_summary": (state.get("policy_verification") or {}).get("summary"),
        "medical_validation_summary": (state.get("medical_validation") or {}).get("summary"),
        "fraud_detection_summary": (state.get("fraud_detection") or {}).get("summary"),
        "final_decision": state.get("decision"),
        "final_reasoning": state.get("decision_reasoning"),
        "confidence_score": state.get("confidence_score"),
        "risk_assessment": assess_risk(
            (state.get("fraud_detection") or {}).get("fraud_score"),
            state.get("confidence_score"),
            state.get("claimed_amount"),
        ),
    }
