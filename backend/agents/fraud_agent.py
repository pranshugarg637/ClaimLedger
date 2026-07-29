# # """
# # Fraud Detection Agent
# # ------------------------
# # Responsibilities:
# #   1. Gather fraud signals via MCP: duplicate-claim check, hospital fraud
# #      flags, deterministic rule-based risk scoring
# #   2. Ask the LLM to reason over the signals and produce a narrative summary
# #   3. Blend the deterministic score (authoritative) with LLM commentary

# # Tools used (via MCP): fraud.check_duplicate_claims, fraud.score_claim_risk,
# #                        hospital.is_in_network
# # """
# # from datetime import datetime, timezone

# # from mcp_servers.fraud_server import check_duplicate_claims, score_claim_risk
# # from mcp_servers.hospital_server import is_in_network
# # from agents.llm_utils import ask_llm_json
# # from guardrails_engine.validators import engine as guardrails_engine
# # from governance.audit import log_agent_action
# # from database import db


# # def _risk_tier(score: float) -> str:
# #     if score < 0.40:
# #         return "low"
# #     if score < 0.70:
# #         return "medium"
# #     if score < 0.90:
# #         return "high"
# #     return "critical"

# # SYSTEM_PROMPT = """You are a Fraud Detection Agent for medical insurance claims.
# # You are given a deterministic, rule-based fraud_score (0-1, ALREADY COMPUTED,
# # you must not change this number) plus supporting signals. Write a short
# # narrative explanation of the fraud risk for a human claims officer.

# # Respond with ONLY a JSON object in exactly this shape:
# # {"fraud_score": <same number as given>, "risk_reasons": ["..."], "confidence": 0.0-1.0, "summary": "one sentence"}
# # """


# # async def run(state: dict) -> dict:
# #     claim_id = state["claim_id"]
# #     patient_id = state["patient_id"]
# #     procedure_code = state.get("procedure_code")
# #     claimed_amount = state["claimed_amount"]
# #     hospital_id = state.get("hospital_id")

# #     duplicate_check = check_duplicate_claims(
# #         patient_id, procedure_code, exclude_claim_id=claim_id
# #     )
# #     network_check = is_in_network(hospital_id)

# #     policy = db.get_policy(state["policy_number"])
# #     days_since_start = 9999
# #     if policy and policy.get("start_date"):
# #         try:
# #             start = datetime.fromisoformat(policy["start_date"])
# #             days_since_start = (datetime.now(timezone.utc).replace(tzinfo=None) - start).days
# #         except Exception:
# #             pass

# #     risk_score_result = score_claim_risk(
# #         claimed_amount=claimed_amount,
# #         procedure_code=procedure_code,
# #         hospital_fraud_flags=network_check.get("prior_fraud_flags", 0),
# #         duplicate_count=duplicate_check.get("duplicate_count", 0),
# #         days_since_policy_start=days_since_start,
# #     )

# #     deterministic_fraud_score = risk_score_result["fraud_score"]
# #     deterministic_reasons = risk_score_result["risk_reasons"]
# #     fraud_risk_tier = _risk_tier(deterministic_fraud_score)

# #     user_prompt = f"""Deterministic fraud_score (authoritative, do not change): {deterministic_fraud_score}
# # Contributing rule-based reasons: {deterministic_reasons}
# # Duplicate claims found: {duplicate_check.get('duplicate_count')}
# # Hospital in-network: {network_check.get('in_network')}
# # Hospital prior fraud flags: {network_check.get('prior_fraud_flags')}
# # Days since policy started: {days_since_start}
# # """
# #     parsed, raw = await ask_llm_json(SYSTEM_PROMPT, user_prompt)

# #     if not parsed:
# #         parsed = {
# #             "fraud_score": deterministic_fraud_score,
# #             "risk_reasons": deterministic_reasons,
# #             "confidence": 0.6,
# #             "summary": "LLM narrative unavailable; deterministic fraud score used as-is.",
# #         }

# #     # The deterministic score is authoritative — never let the LLM alter it.
# #     if parsed.get("fraud_score") != deterministic_fraud_score:
# #         parsed["fraud_score"] = deterministic_fraud_score
# #         parsed["confidence"] = min(parsed.get("confidence", 0.6), 0.6)

# #     validation_report = guardrails_engine.validate_agent_output("fraud_detection", parsed)
# #     if not validation_report["schema_valid"]:
# #         try:
# #             parsed["confidence"] = min(float(parsed.get("confidence", 0.4)), 0.4)
# #         except (TypeError, ValueError):
# #             parsed["confidence"] = 0.4
# #         parsed["fraud_score"] = deterministic_fraud_score
# #         parsed["risk_reasons"] = deterministic_reasons
# #         parsed["summary"] = "Fraud narrative was malformed; deterministic fraud checks were used."

# #     parsed["risk_tier"] = fraud_risk_tier
# #     parsed["reason_codes"] = []
# #     if fraud_risk_tier == "critical":
# #         parsed["reason_codes"].append("CRITICAL_FRAUD_RISK")
# #     elif fraud_risk_tier in {"high", "medium"}:
# #         parsed["reason_codes"].append("FRAUD_RISK_REVIEW")
# #     parsed["evidence"] = {"findings": {"risk_tier": fraud_risk_tier, "fraud_score": deterministic_fraud_score}, "confidence": parsed.get("confidence"), "warnings": deterministic_reasons, "evidence": {"duplicate_check": duplicate_check, "network_check": network_check, "risk_score_result": risk_score_result}}

# #     log_agent_action(claim_id, "fraud_detection_agent", "assess_fraud_risk",
# #                       {"patient_id": patient_id, "procedure_code": procedure_code}, parsed,
# #                       parsed.get("confidence"), parsed.get("summary"))

# #     return {
# #         "fraud_detection": parsed,
# #         "current_stage": "fraud_checked",
# #         "trace": [{"agent": "fraud_detection",
# #                    "detail": {"duplicate_check": duplicate_check, "network_check": network_check,
# #                               "risk_score_result": risk_score_result},
# #                    "llm_raw": raw}],
# #     }





# """
# Fraud Detection Agent
# ------------------------
# Responsibilities:
#   1. Gather fraud signals via MCP: duplicate-claim check, hospital fraud
#      flags, deterministic rule-based risk scoring
#   2. Ask the LLM to reason over the signals and produce a narrative summary
#   3. Blend the deterministic score (authoritative) with LLM commentary

# Tools used (via MCP): fraud.check_duplicate_claims, fraud.score_claim_risk,
#                        hospital.is_in_network
# """

# from datetime import datetime, timezone

# from mcp_servers.fraud_server import check_duplicate_claims, score_claim_risk
# from mcp_servers.hospital_server import is_in_network
# from agents.llm_utils import ask_llm_json
# from guardrails_engine.validators import engine as guardrails_engine
# from governance.audit import log_agent_action
# from database import db


# def _as_float(value, default: float = 0.0) -> float:
#     """Safely convert a value to float."""
#     try:
#         return float(value)
#     except (TypeError, ValueError):
#         return default


# def _risk_tier(score: float) -> str:
#     score = _as_float(score)

#     if score < 0.40:
#         return "low"
#     if score < 0.70:
#         return "medium"
#     if score < 0.90:
#         return "high"
#     return "critical"


# SYSTEM_PROMPT = """
# You are a Fraud Detection Agent for medical insurance claims.

# You are given a deterministic, rule-based fraud_score (0-1, ALREADY COMPUTED,
# you must not change this number) plus supporting signals.

# Write a short narrative explanation of the fraud risk for a human claims officer.

# Respond ONLY with valid JSON:

# {
#   "fraud_score": <same number provided>,
#   "risk_reasons": ["..."],
#   "confidence": 0.0,
#   "summary": "..."
# }
# """


# async def run(state: dict) -> dict:
#     claim_id = state["claim_id"]
#     patient_id = state["patient_id"]
#     procedure_code = state.get("procedure_code")
#     claimed_amount = state["claimed_amount"]
#     hospital_id = state.get("hospital_id")

#     duplicate_check = check_duplicate_claims(
#         patient_id,
#         procedure_code,
#         exclude_claim_id=claim_id,
#     )

#     network_check = is_in_network(hospital_id)

#     policy = db.get_policy(state["policy_number"])

#     days_since_start = 9999

#     if policy and policy.get("start_date"):
#         try:
#             start = datetime.fromisoformat(policy["start_date"])
#             days_since_start = (
#                 datetime.now(timezone.utc).replace(tzinfo=None) - start
#             ).days
#         except Exception:
#             pass

#     risk_score_result = score_claim_risk(
#         claimed_amount=claimed_amount,
#         procedure_code=procedure_code,
#         hospital_fraud_flags=network_check.get("prior_fraud_flags", 0),
#         duplicate_count=duplicate_check.get("duplicate_count", 0),
#         days_since_policy_start=days_since_start,
#     )

#     deterministic_fraud_score = _as_float(
#         risk_score_result.get("fraud_score"),
#         0.0,
#     )

#     deterministic_reasons = risk_score_result.get("risk_reasons", [])

#     fraud_risk_tier = _risk_tier(deterministic_fraud_score)

#     user_prompt = f"""
# Deterministic fraud_score (authoritative, do not change): {deterministic_fraud_score}
# Contributing rule-based reasons: {deterministic_reasons}
# Duplicate claims found: {duplicate_check.get('duplicate_count')}
# Hospital in-network: {network_check.get('in_network')}
# Hospital prior fraud flags: {network_check.get('prior_fraud_flags')}
# Days since policy started: {days_since_start}
# """

#     parsed, raw = await ask_llm_json(SYSTEM_PROMPT, user_prompt)

#     if not parsed:
#         parsed = {
#             "fraud_score": deterministic_fraud_score,
#             "risk_reasons": deterministic_reasons,
#             "confidence": 0.6,
#             "summary": "LLM narrative unavailable; deterministic fraud score used as-is.",
#         }

#     # ----------------------------------------------------------
#     # Normalize numeric values immediately after the LLM response
#     # ----------------------------------------------------------

#     parsed["fraud_score"] = _as_float(
#         parsed.get("fraud_score"),
#         deterministic_fraud_score,
#     )

#     parsed["confidence"] = _as_float(
#         parsed.get("confidence"),
#         0.6,
#     )

#     # ----------------------------------------------------------
#     # Fraud score must always match deterministic score
#     # ----------------------------------------------------------

#     if parsed["fraud_score"] != deterministic_fraud_score:
#         parsed["fraud_score"] = deterministic_fraud_score
#         parsed["confidence"] = min(parsed["confidence"], 0.6)

#     validation_report = guardrails_engine.validate_agent_output(
#         "fraud_detection",
#         parsed,
#     )

#     if not validation_report["schema_valid"]:
#         parsed["confidence"] = min(
#             _as_float(parsed.get("confidence"), 0.4),
#             0.4,
#         )

#         parsed["fraud_score"] = deterministic_fraud_score
#         parsed["risk_reasons"] = deterministic_reasons

#         parsed["summary"] = (
#             "Fraud narrative was malformed; deterministic fraud checks were used."
#         )

#     parsed["risk_tier"] = fraud_risk_tier

#     parsed["reason_codes"] = []

#     if fraud_risk_tier == "critical":
#         parsed["reason_codes"].append("CRITICAL_FRAUD_RISK")
#     elif fraud_risk_tier in ("high", "medium"):
#         parsed["reason_codes"].append("FRAUD_RISK_REVIEW")

#     parsed["evidence"] = {
#         "findings": {
#             "risk_tier": fraud_risk_tier,
#             "fraud_score": deterministic_fraud_score,
#         },
#         "confidence": parsed["confidence"],
#         "warnings": deterministic_reasons,
#         "evidence": {
#             "duplicate_check": duplicate_check,
#             "network_check": network_check,
#             "risk_score_result": risk_score_result,
#         },
#     }

#     log_agent_action(
#         claim_id,
#         "fraud_detection_agent",
#         "assess_fraud_risk",
#         {
#             "patient_id": patient_id,
#             "procedure_code": procedure_code,
#         },
#         parsed,
#         parsed["confidence"],
#         parsed.get("summary"),
#     )

#     return {
#         "fraud_detection": parsed,
#         "current_stage": "fraud_checked",
#         "trace": [
#             {
#                 "agent": "fraud_detection",
#                 "detail": {
#                     "duplicate_check": duplicate_check,
#                     "network_check": network_check,
#                     "risk_score_result": risk_score_result,
#                 },
#                 "llm_raw": raw,
#             }
#         ],
#     }




"""
Fraud Detection Agent
------------------------
Responsibilities:
  1. Gather fraud signals via MCP: duplicate-claim check, hospital fraud
     flags, deterministic rule-based risk scoring
  2. Ask the LLM to reason over the signals and produce a narrative summary
  3. Blend the deterministic score (authoritative) with LLM commentary

Tools used (via MCP): fraud.check_duplicate_claims, fraud.score_claim_risk,
                       hospital.is_in_network
"""

from datetime import datetime, timezone

from mcp_servers.fraud_server import check_duplicate_claims, score_claim_risk
from mcp_servers.hospital_server import is_in_network
from agents.llm_utils import ask_llm_json
from guardrails_engine.validators import engine as guardrails_engine
from governance.audit import log_agent_action
from database import db


def _as_float(value, default: float = 0.0) -> float:
    """Safely convert a value to float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _risk_tier(score: float) -> str:
    score = _as_float(score)

    if score < 0.40:
        return "low"
    if score < 0.70:
        return "medium"
    if score < 0.90:
        return "high"
    return "critical"


# NOTE: the JSON example below intentionally avoids literal, already-valid
# values (e.g. a bare "0.0") for fields the LLM must actually fill in.
# A model shown a fully-formed example will often just echo it back verbatim
# instead of generating a real value, and that failure mode is invisible to
# schema validation since the echoed value is still a valid float.
SYSTEM_PROMPT = """
You are a Fraud Detection Agent for medical insurance claims.

You are given a deterministic, rule-based fraud_score (0-1, ALREADY COMPUTED,
you must not change this number) plus supporting signals.

Write a short narrative explanation of the fraud risk for a human claims officer.

Respond ONLY with valid JSON, replacing every placeholder below with your
own real analysis (do not copy the placeholder text or format literally):

{
  "fraud_score": <same number provided, do not change>,
  "risk_reasons": ["<specific reason 1 based on the signals given>", "<specific reason 2, if applicable>"],
  "confidence": <a float between 0.0 and 1.0 reflecting how strong/complete the input signals are; do not default to 0.0>,
  "summary": "<one sentence written specifically for this claim>"
}
"""


async def run(state: dict) -> dict:
    claim_id = state["claim_id"]
    patient_id = state["patient_id"]
    procedure_code = state.get("procedure_code")
    claimed_amount = state["claimed_amount"]
    hospital_id = state.get("hospital_id")

    duplicate_check = check_duplicate_claims(
        patient_id,
        procedure_code,
        exclude_claim_id=claim_id,
    )

    network_check = is_in_network(hospital_id)

    policy = db.get_policy(state["policy_number"])

    days_since_start = 9999

    if policy and policy.get("start_date"):
        try:
            start = datetime.fromisoformat(policy["start_date"])
            days_since_start = (
                datetime.now(timezone.utc).replace(tzinfo=None) - start
            ).days
        except Exception:
            pass

    risk_score_result = score_claim_risk(
        claimed_amount=claimed_amount,
        procedure_code=procedure_code,
        hospital_fraud_flags=network_check.get("prior_fraud_flags", 0),
        duplicate_count=duplicate_check.get("duplicate_count", 0),
        days_since_policy_start=days_since_start,
    )

    deterministic_fraud_score = _as_float(
        risk_score_result.get("fraud_score"),
        0.0,
    )

    deterministic_reasons = risk_score_result.get("risk_reasons", [])

    fraud_risk_tier = _risk_tier(deterministic_fraud_score)

    user_prompt = f"""
Deterministic fraud_score (authoritative, do not change): {deterministic_fraud_score}
Contributing rule-based reasons: {deterministic_reasons}
Duplicate claims found: {duplicate_check.get('duplicate_count')}
Hospital in-network: {network_check.get('in_network')}
Hospital prior fraud flags: {network_check.get('prior_fraud_flags')}
Days since policy started: {days_since_start}
"""

    parsed, raw = await ask_llm_json(SYSTEM_PROMPT, user_prompt)

    if not parsed:
        parsed = {
            "fraud_score": deterministic_fraud_score,
            "risk_reasons": deterministic_reasons,
            "confidence": 0.6,
            "summary": "LLM narrative unavailable; deterministic fraud score used as-is.",
        }

    # ----------------------------------------------------------
    # Normalize numeric values immediately after the LLM response
    # ----------------------------------------------------------

    parsed["fraud_score"] = _as_float(
        parsed.get("fraud_score"),
        deterministic_fraud_score,
    )

    parsed["confidence"] = _as_float(
        parsed.get("confidence"),
        0.6,
    )

    # ----------------------------------------------------------
    # Guardrail: catch a suspiciously "echoed placeholder" confidence
    # (e.g. exactly 0.0, or 0.0-1.0 style artifacts slipping through as 0)
    # instead of silently letting it tank the downstream confidence gate.
    # ----------------------------------------------------------

    if parsed["confidence"] <= 0.0:
        parsed["confidence"] = 0.6
        parsed["summary"] = (
            parsed.get("summary")
            or "LLM confidence was missing/invalid; default confidence used."
        )

    # ----------------------------------------------------------
    # Fraud score must always match deterministic score
    # ----------------------------------------------------------

    if parsed["fraud_score"] != deterministic_fraud_score:
        parsed["fraud_score"] = deterministic_fraud_score
        parsed["confidence"] = min(parsed["confidence"], 0.6)

    validation_report = guardrails_engine.validate_agent_output(
        "fraud_detection",
        parsed,
    )

    if not validation_report["schema_valid"]:
        parsed["confidence"] = min(
            _as_float(parsed.get("confidence"), 0.4),
            0.4,
        )

        parsed["fraud_score"] = deterministic_fraud_score
        parsed["risk_reasons"] = deterministic_reasons

        parsed["summary"] = (
            "Fraud narrative was malformed; deterministic fraud checks were used."
        )

    parsed["risk_tier"] = fraud_risk_tier

    parsed["reason_codes"] = []

    if fraud_risk_tier == "critical":
        parsed["reason_codes"].append("CRITICAL_FRAUD_RISK")
    elif fraud_risk_tier in ("high", "medium"):
        parsed["reason_codes"].append("FRAUD_RISK_REVIEW")

    parsed["evidence"] = {
        "findings": {
            "risk_tier": fraud_risk_tier,
            "fraud_score": deterministic_fraud_score,
        },
        "confidence": parsed["confidence"],
        "warnings": deterministic_reasons,
        "evidence": {
            "duplicate_check": duplicate_check,
            "network_check": network_check,
            "risk_score_result": risk_score_result,
        },
    }

    log_agent_action(
        claim_id,
        "fraud_detection_agent",
        "assess_fraud_risk",
        {
            "patient_id": patient_id,
            "procedure_code": procedure_code,
        },
        parsed,
        parsed["confidence"],
        parsed.get("summary"),
    )

    return {
        "fraud_detection": parsed,
        "current_stage": "fraud_checked",
        "trace": [
            {
                "agent": "fraud_detection",
                "detail": {
                    "duplicate_check": duplicate_check,
                    "network_check": network_check,
                    "risk_score_result": risk_score_result,
                },
                "llm_raw": raw,
            }
        ],
    }