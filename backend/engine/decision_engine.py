from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from config import (
    DOCUMENT_MIN_CONFIDENCE,
    POLICY_MIN_CONFIDENCE,
    MEDICAL_MIN_CONFIDENCE,
    FRAUD_MIN_CONFIDENCE,
    AUTO_APPROVAL_LIMIT,
    AUTO_REVIEW_LIMIT,
    AUTO_ESCALATION_LIMIT,
    PLAN_LIMITS,
)


def _get_agent_confidence(agent_result: Optional[Dict[str, Any]], default: float = 0.0) -> float:
    if not agent_result:
        return default
    value = agent_result.get("confidence")
    if value is None:
        value = agent_result.get("confidence_score")
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return default


def _plan_limit(state: Dict[str, Any], key: str) -> float:
    plan_type = (state.get("policy_verification") or {}).get("plan_type") or (state.get("policy_plan_type") or "Standard")
    spec = PLAN_LIMITS.get(plan_type, {})
    value = spec.get(key)
    if value is None:
        value = {
            "auto_approval_limit": AUTO_APPROVAL_LIMIT,
            "auto_review_limit": AUTO_REVIEW_LIMIT,
            "auto_escalation_limit": AUTO_ESCALATION_LIMIT,
        }.get(key)
    return float(value or 0.0)


def _has_reason_code(result: Optional[Dict[str, Any]], code: str) -> bool:
    if not result:
        return False
    codes = result.get("reason_codes") or []
    return code in codes


def evaluate_claim(state: Dict[str, Any]) -> Dict[str, Any]:
    """Pure deterministic decision engine with explicit stage ordering."""
    document = state.get("document_verification") or {}
    policy = state.get("policy_verification") or {}
    medical = state.get("medical_validation") or {}
    fraud = state.get("fraud_detection") or {}
    duplicate = state.get("duplicate_claim_detection") or {}
    governance = state.get("governance_report") or {}

    doc_confidence = _get_agent_confidence(document, 0.0)
    policy_confidence = _get_agent_confidence(policy, 0.0)
    medical_confidence = _get_agent_confidence(medical, 0.0)
    fraud_confidence = _get_agent_confidence(fraud, 0.0)
    duplicate_probability = float(duplicate.get("duplicate_probability") or 0.0)

    claim_amount = float(state.get("claimed_amount") or 0.0)
    auto_approval_limit = _plan_limit(state, "auto_approval_limit")
    auto_review_limit = _plan_limit(state, "auto_review_limit")
    auto_escalation_limit = _plan_limit(state, "auto_escalation_limit")

    # Stage 1: hard reject
    if not document.get("is_valid", False):
        return {"decision": "rejected", "reason_codes": ["INVALID_DOCUMENT"], "confidence": 0.0, "governance_passed": False}
    if policy.get("policy_active") is False:
        return {"decision": "rejected", "reason_codes": ["POLICY_INACTIVE"], "confidence": 0.0, "governance_passed": False}
    if policy.get("patient_is_covered") is False:
        return {"decision": "rejected", "reason_codes": ["PATIENT_NOT_COVERED"], "confidence": 0.0, "governance_passed": False}
    if policy.get("procedure_covered") is False or policy.get("procedure_in_plan") is False:
        return {"decision": "rejected", "reason_codes": ["PROCEDURE_NOT_COVERED"], "confidence": 0.0, "governance_passed": False}
    if document.get("evidence", {}).get("blacklisted_hospital") or fraud.get("evidence", {}).get("blacklisted_hospital"):
        return {"decision": "rejected", "reason_codes": ["BLACKLISTED_HOSPITAL"], "confidence": 0.0, "governance_passed": False}
    if float(fraud.get("fraud_score") or 0.0) >= 0.90:
        return {"decision": "rejected", "reason_codes": ["CRITICAL_FRAUD_RISK"], "confidence": 0.0, "governance_passed": False}

    # Stage 2: needs review
    if document.get("evidence", {}).get("document_fallback_failed") or _has_reason_code(document, "DOCUMENT_FALLBACK_FAILED"):
        return {"decision": "needs_review", "reason_codes": ["DOCUMENT_FALLBACK_FAILED"], "confidence": 0.0, "governance_passed": False}
    if document.get("field_matches") is False:
        return {"decision": "needs_review", "reason_codes": ["DOCUMENT_FIELD_MISMATCH"], "confidence": 0.0, "governance_passed": False}
    if medical.get("clinically_plausible") is False or medical.get("cost_within_range") is False:
        return {"decision": "needs_review", "reason_codes": ["MEDICAL_UNCERTAINTY"], "confidence": 0.0, "governance_passed": False}
    if duplicate_probability >= 0.60:
        return {"decision": "needs_review", "reason_codes": ["DUPLICATE_CLAIM_SUSPECTED"], "confidence": 0.0, "governance_passed": False}
    fraud_score = float(fraud.get("fraud_score") or 0.0)
    if 0.40 <= fraud_score < 0.90:
        return {"decision": "needs_review", "reason_codes": ["FRAUD_RISK_REVIEW"], "confidence": 0.0, "governance_passed": False}
    if claim_amount > auto_approval_limit:
        return {"decision": "needs_review", "reason_codes": ["CLAIM_ABOVE_AUTO_APPROVAL_LIMIT"], "confidence": 0.0, "governance_passed": False}
    if policy.get("sufficient_balance") is False:
        return {"decision": "needs_review", "reason_codes": ["INSUFFICIENT_POLICY_BALANCE"], "confidence": 0.0, "governance_passed": False}
    if doc_confidence < DOCUMENT_MIN_CONFIDENCE or policy_confidence < POLICY_MIN_CONFIDENCE or medical_confidence < MEDICAL_MIN_CONFIDENCE or fraud_confidence < FRAUD_MIN_CONFIDENCE:
        return {"decision": "needs_review", "reason_codes": ["LOW_AGENT_CONFIDENCE"], "confidence": 0.0, "governance_passed": False}

    # Stage 3: approve only when governance also passes
    governance_passed = True
    if governance.get("compliant") is False:
        governance_passed = False
    if claim_amount > auto_review_limit:
        governance_passed = False
    if claim_amount > auto_escalation_limit:
        governance_passed = False

    if governance_passed:
        return {"decision": "approved", "reason_codes": [], "confidence": min(1.0, round((doc_confidence + policy_confidence + medical_confidence + fraud_confidence) / 4.0, 3)), "governance_passed": True}

    return {"decision": "needs_review", "reason_codes": ["GOVERNANCE_DOWNGRADE"], "confidence": min(1.0, round((doc_confidence + policy_confidence + medical_confidence + fraud_confidence) / 4.0, 3)), "governance_passed": False}
