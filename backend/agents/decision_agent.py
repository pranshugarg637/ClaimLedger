# """
# Decision Agent
# ----------------
# Final synthesis node. The verdict is determined by the deterministic engine
# below; the LLM is only used to produce human-readable reasoning text.
# """
# from agents.llm_utils import ask_llm_json
# from guardrails_engine.validators import engine as guardrails_engine
# from governance.audit import log_agent_action, assess_risk, policy_compliance_check, build_explainability_report
# from engine.decision_engine import evaluate_claim
# from engine.evidence_aggregator import aggregate_evidence

# SYSTEM_PROMPT = """You are the Decision Agent for a medical insurance claims system.
# You are given the FINAL, ALREADY-DETERMINED decision (approved/rejected/needs_review)
# plus every upstream agent's summary. Your only job is to write one clear,
# professional paragraph explaining the decision to the policyholder. Do not
# change the decision, and do not invent facts not present in the summaries.

# Respond with ONLY a JSON object in exactly this shape:
# {"decision": "<same as given>", "reasoning": "one paragraph", "confidence": 0.0-1.0}
# """


# def _deterministic_decision(state: dict) -> tuple[str, float, float]:
#     """The authoritative decision logic. Pure, deterministic, testable."""
#     result = evaluate_claim(state)
#     return result["decision"], result.get("confidence", 0.0), (state.get("fraud_detection") or {}).get("fraud_score", 0.0) or 0.0


# async def run(state: dict) -> dict:
#     claim_id = state["claim_id"]
#     evidence_bundle = aggregate_evidence(state)
#     working_state = {**state, "evidence_bundle": evidence_bundle}

#     decision_result = evaluate_claim(working_state)
#     decision = decision_result["decision"]
#     confidence = decision_result.get("confidence", 0.0)
#     fraud_score = (working_state.get("fraud_detection") or {}).get("fraud_score", 0.0) or 0.0

#     user_prompt = f"""Final decision (do not change): {decision}
# Document verification: {working_state.get('document_verification')}
# Policy verification: {working_state.get('policy_verification')}
# Medical validation: {working_state.get('medical_validation')}
# Fraud detection: {working_state.get('fraud_detection')}
# Evidence bundle: {evidence_bundle}
# Reason codes: {decision_result.get('reason_codes', [])}
# """
#     # LLM boundary: only summarize evidence and produce human-facing text; never decide or override policy facts.
#     parsed, raw = await ask_llm_json(SYSTEM_PROMPT, user_prompt)

#     if not parsed or parsed.get("decision") != decision:
#         parsed = {
#             "decision": decision,
#             "reasoning": _fallback_reasoning(decision, working_state),
#             "confidence": confidence,
#         }

#     # Governance gates run regardless of what the LLM said
#     compliance_state = {**working_state, "decision": decision, "confidence_score": confidence,
#                          "requires_human_review": decision == "needs_review"}
#     compliance = policy_compliance_check(compliance_state)
#     if not compliance["compliant"]:
#         decision = "needs_review"
#         parsed["decision"] = decision
#         parsed["reasoning"] += " [Escalated to human review due to policy compliance check.]"

#     risk = assess_risk(fraud_score, confidence, working_state.get("claimed_amount"))

#     final_state = {**working_state, "decision": decision, "confidence_score": confidence,
#                    "requires_human_review": decision == "needs_review", "reason_codes": decision_result.get("reason_codes", [])}
#     explainability = build_explainability_report(final_state)

#     log_agent_action(claim_id, "decision_agent", "finalize_decision",
#                       {"fraud_score": fraud_score, "confidence": confidence},
#                       {"decision": decision, "reasoning": parsed.get("reasoning"), "reason_codes": decision_result.get("reason_codes", [])},
#                       confidence, parsed.get("reasoning"))

#     return {
#         "decision": decision,
#         "decision_reasoning": parsed.get("reasoning"),
#         "confidence_score": confidence,
#         "requires_human_review": decision == "needs_review",
#         "reason_codes": decision_result.get("reason_codes", []),
#         "governance_report": {
#             "risk_assessment": risk,
#             "policy_compliance": compliance,
#             "explainability": explainability,
#         },
#         "evidence_bundle": evidence_bundle,
#         "current_stage": "completed",
#         "trace": [{"agent": "decision_agent", "detail": {"decision": decision, "fraud_score": fraud_score, "reason_codes": decision_result.get("reason_codes", [])}, "llm_raw": raw}],
#     }


# def _fallback_reasoning(decision: str, state: dict) -> str:
#     reasons = []
#     doc = state.get("document_verification", {}) or {}
#     pol = state.get("policy_verification", {}) or {}
#     med = state.get("medical_validation", {}) or {}
#     fraud = state.get("fraud_detection", {}) or {}
#     duplicate = state.get("duplicate_claim_detection", {}) or {}

#     if doc.get("summary"):
#         reasons.append(doc["summary"])
#     if pol.get("summary"):
#         reasons.append(pol["summary"])
#     if med.get("summary"):
#         reasons.append(med["summary"])
#     if fraud.get("summary"):
#         reasons.append(fraud["summary"])
#     if duplicate.get("summary"):
#         reasons.append(duplicate["summary"])

#     prefix = {
#         "approved": "This claim has been approved.",
#         "rejected": "This claim has been rejected.",
#         "needs_review": "This claim requires manual review by a claims officer.",
#     }.get(decision, "This claim's status has been determined.")

#     if state.get("reason_codes"):
#         return prefix + " Reasons: " + ", ".join(state["reason_codes"])
#     return prefix + " " + " ".join(reasons)


"""
Decision Agent
----------------
Final synthesis node. The verdict is determined by the deterministic engine
below; the LLM is only used to produce human-readable reasoning text.
"""
from agents.llm_utils import ask_llm_json
from guardrails_engine.validators import engine as guardrails_engine
from governance.audit import log_agent_action, assess_risk, policy_compliance_check, build_explainability_report
from engine.decision_engine import evaluate_claim
from engine.evidence_aggregator import aggregate_evidence

SYSTEM_PROMPT = """You are the Decision Agent for a medical insurance claims system.
You are given the FINAL, ALREADY-DETERMINED decision (approved/rejected/needs_review)
plus every upstream agent's summary. Your only job is to write one clear,
professional paragraph explaining the decision to the policyholder. Do not
change the decision, and do not invent facts not present in the summaries.

Respond with ONLY a JSON object in exactly this shape:
{"decision": "<same as given>", "reasoning": "one paragraph", "confidence": 0.0-1.0}
"""


def _deterministic_decision(state: dict) -> tuple[str, float, float]:
    """The authoritative decision logic. Pure, deterministic, testable."""
    result = evaluate_claim(state)
    return result["decision"], result.get("confidence", 0.0), (state.get("fraud_detection") or {}).get("fraud_score", 0.0) or 0.0


async def run(state: dict) -> dict:
    claim_id = state["claim_id"]
    evidence_bundle = aggregate_evidence(state)
    working_state = {**state, "evidence_bundle": evidence_bundle}

    decision_result = evaluate_claim(working_state)
    decision = decision_result["decision"]
    confidence = decision_result.get("confidence", 0.0)
    fraud_score = (working_state.get("fraud_detection") or {}).get("fraud_score", 0.0) or 0.0

    user_prompt = f"""Final decision (do not change): {decision}
Document verification: {working_state.get('document_verification')}
Policy verification: {working_state.get('policy_verification')}
Medical validation: {working_state.get('medical_validation')}
Fraud detection: {working_state.get('fraud_detection')}
Evidence bundle: {evidence_bundle}
Reason codes: {decision_result.get('reason_codes', [])}
"""
    # LLM boundary: only summarize evidence and produce human-facing text; never decide or override policy facts.
    parsed, raw = await ask_llm_json(SYSTEM_PROMPT, user_prompt)

    if not parsed or parsed.get("decision") != decision or not parsed.get("reasoning"):
        # NOTE: added `or not parsed.get("reasoning")` — previously, if the
        # LLM returned a matching "decision" but forgot/misnamed the
        # "reasoning" field, this fallback block was skipped and `parsed`
        # ended up with no "reasoning" key at all. Later, `parsed["reasoning"] +=`
        # (below) would then raise a KeyError and crash the whole request.
        parsed = {
            "decision": decision,
            "reasoning": _fallback_reasoning(decision, working_state),
            "confidence": confidence,
        }

    # Governance gates run regardless of what the LLM said
    compliance_state = {**working_state, "decision": decision, "confidence_score": confidence,
                         "requires_human_review": decision == "needs_review"}
    compliance = policy_compliance_check(compliance_state)
    if not compliance["compliant"]:
        decision = "needs_review"
        parsed["decision"] = decision
        # Use .get() with a fallback instead of a bare [] access, so a
        # missing "reasoning" key can never crash this line.
        base_reasoning = parsed.get("reasoning") or _fallback_reasoning(decision, working_state)
        parsed["reasoning"] = base_reasoning + " [Escalated to human review due to policy compliance check.]"

    risk = assess_risk(fraud_score, confidence, working_state.get("claimed_amount"))

    final_state = {**working_state, "decision": decision, "confidence_score": confidence,
                   "requires_human_review": decision == "needs_review", "reason_codes": decision_result.get("reason_codes", [])}
    explainability = build_explainability_report(final_state)

    log_agent_action(claim_id, "decision_agent", "finalize_decision",
                      {"fraud_score": fraud_score, "confidence": confidence},
                      {"decision": decision, "reasoning": parsed.get("reasoning"), "reason_codes": decision_result.get("reason_codes", [])},
                      confidence, parsed.get("reasoning"))

    return {
        "decision": decision,
        "decision_reasoning": parsed.get("reasoning"),
        "confidence_score": confidence,
        "requires_human_review": decision == "needs_review",
        "reason_codes": decision_result.get("reason_codes", []),
        "governance_report": {
            "risk_assessment": risk,
            "policy_compliance": compliance,
            "explainability": explainability,
        },
        "evidence_bundle": evidence_bundle,
        "current_stage": "completed",
        "trace": [{"agent": "decision_agent", "detail": {"decision": decision, "fraud_score": fraud_score, "reason_codes": decision_result.get("reason_codes", [])}, "llm_raw": raw}],
    }


def _fallback_reasoning(decision: str, state: dict) -> str:
    reasons = []
    doc = state.get("document_verification", {}) or {}
    pol = state.get("policy_verification", {}) or {}
    med = state.get("medical_validation", {}) or {}
    fraud = state.get("fraud_detection", {}) or {}
    duplicate = state.get("duplicate_claim_detection", {}) or {}

    if doc.get("summary"):
        reasons.append(doc["summary"])
    if pol.get("summary"):
        reasons.append(pol["summary"])
    if med.get("summary"):
        reasons.append(med["summary"])
    if fraud.get("summary"):
        reasons.append(fraud["summary"])
    if duplicate.get("summary"):
        reasons.append(duplicate["summary"])

    prefix = {
        "approved": "This claim has been approved.",
        "rejected": "This claim has been rejected.",
        "needs_review": "This claim requires manual review by a claims officer.",
    }.get(decision, "This claim's status has been determined.")

    if state.get("reason_codes"):
        return prefix + " Reasons: " + ", ".join(state["reason_codes"])
    return prefix + " " + " ".join(reasons)