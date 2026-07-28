"""
Policy Verification Agent
----------------------------
Responsibilities:
  1. Fetch policy details via MCP (policy database)
  2. Check procedure coverage & policy activity status
  3. Check remaining balance sufficiency
  4. Ask the LLM to synthesize a plain-language summary + confidence

Tools used (via MCP): policy.get_policy_details, policy.check_procedure_coverage,
                       policy.check_sufficient_balance
"""
# Use the local policy implementation directly in the live claim workflow.
# The functions are also exposed through MCP for external integrations, but
# stdio MCP startup must not be a dependency of a claim decision.
from mcp_servers.policy_server import (
    check_procedure_coverage,
    check_sufficient_balance,
    get_policy_details,
)
from agents.llm_utils import ask_llm_json
from guardrails_engine.validators import engine as guardrails_engine
from governance.audit import log_agent_action
from database import db

SYSTEM_PROMPT = """You are a Policy Verification Agent for medical insurance claims.
You are given deterministic facts already retrieved from the policy database
(these facts are ground truth — do not contradict them). Summarize the
policy verification outcome and give a confidence score for how clear-cut
the coverage decision is.

Respond with ONLY a JSON object in exactly this shape:
{"policy_active": true/false, "procedure_covered": true/false, "sufficient_balance": true/false, "confidence": 0.0-1.0, "summary": "one sentence"}
"""


async def run(state: dict) -> dict:
    claim_id = state["claim_id"]
    policy_number = state["policy_number"]
    patient_id = state["patient_id"]
    procedure_code = state.get("procedure_code")
    claimed_amount = state["claimed_amount"]

    details = get_policy_details(policy_number)
    coverage = check_procedure_coverage(policy_number, procedure_code, patient_id)
    balance = check_sufficient_balance(policy_number, claimed_amount)
    policy_context = db.retrieve_policy_context(policy_number, f"{procedure_code} coverage exclusions waiting period preauthorization")

    if not details.get("found", False):
        result = {
            "policy_active": False, "procedure_covered": False, "sufficient_balance": False,
            "confidence": 0.99, "summary": f"Policy {policy_number} was not found in the database.",
            "reason_codes": ["POLICY_NOT_FOUND"],
        }
        result["evidence"] = {"findings": {"policy_found": False}, "confidence": 0.99, "warnings": ["policy_not_found"], "evidence": {"policy_number": policy_number}}
        log_agent_action(claim_id, "policy_verification_agent", "policy_not_found",
                          {"policy_number": policy_number}, result, result["confidence"], result["summary"])
        return {"policy_verification": result, "current_stage": "policy_verification_failed",
                "trace": [{"agent": "policy_verification", "detail": {"details": details}}]}

    ground_truth = {
        "policy_active": coverage.get("policy_active"),
        "procedure_covered": coverage.get("procedure_in_plan"),
        "sufficient_balance": balance.get("sufficient"),
        "patient_is_covered": coverage.get("patient_is_covered"),
    }
    parsed_reason_codes = []
    if coverage.get("policy_active") is False:
        parsed_reason_codes.append("POLICY_INACTIVE")
    if coverage.get("patient_is_covered") is False:
        parsed_reason_codes.append("PATIENT_NOT_COVERED")
    if coverage.get("procedure_in_plan") is False:
        parsed_reason_codes.append("PROCEDURE_NOT_COVERED")
    if balance.get("sufficient") is False:
        parsed_reason_codes.append("INSUFFICIENT_POLICY_BALANCE")

    user_prompt = f"""Ground truth facts from the policy database (do not contradict these):
- Policy holder: {details.get('holder_name')}
- Plan type: {details.get('plan_type')}
- Policy status: {details.get('status')}
- Policy active: {coverage.get('policy_active')}
- Submitted patient covered: {coverage.get('patient_is_covered')}
- Procedure '{procedure_code}' covered under plan: {coverage.get('procedure_in_plan')}
- Remaining coverage balance: {balance.get('remaining_coverage')}
- Claimed amount: {claimed_amount}
- Sufficient balance for this claim: {balance.get('sufficient')}
- Retrieved policy clauses: {policy_context}
"""
    parsed, raw = await ask_llm_json(SYSTEM_PROMPT, user_prompt)

    if not parsed:
        parsed = {**ground_truth, "confidence": 0.5,
                  "summary": "LLM summary unavailable; result based on deterministic policy checks only."}

    # Hallucination guard: LLM's boolean claims must match deterministic ground truth
    hallucination = guardrails_engine.check_hallucination(
        {k: parsed.get(k) for k in ground_truth}, ground_truth
    )
    if hallucination["hallucination_detected"]:
        # Ground truth always wins over LLM narrative
        parsed.update(ground_truth)
        parsed["confidence"] = min(parsed.get("confidence", 0.5), 0.5)
        parsed["summary"] += " (auto-corrected to match verified policy database facts)"

    # Facts, not model self-confidence, determine confidence for policy data.
    parsed.update(ground_truth)
    parsed["confidence"] = 1.0 if all(ground_truth.values()) else 0.95
    parsed["reason_codes"] = parsed_reason_codes
    parsed["plan_type"] = details.get("plan_type")
    parsed["evidence"] = {"findings": {"policy_active": ground_truth["policy_active"], "procedure_covered": ground_truth["procedure_covered"], "sufficient_balance": ground_truth["sufficient_balance"], "patient_is_covered": ground_truth["patient_is_covered"]}, "confidence": parsed["confidence"], "warnings": parsed_reason_codes, "evidence": {"policy_details": details, "coverage": coverage, "balance": balance, "policy_context": policy_context}}

    validation_report = guardrails_engine.validate_agent_output("policy_verification", parsed)
    if not validation_report["schema_valid"]:
        try:
            parsed["confidence"] = min(float(parsed.get("confidence", 0.4)), 0.4)
        except (TypeError, ValueError):
            parsed["confidence"] = 0.4

    log_agent_action(claim_id, "policy_verification_agent", "verify_policy",
                      {"policy_number": policy_number, "procedure_code": procedure_code}, parsed,
                      parsed.get("confidence"), parsed.get("summary"))

    return {
        "policy_verification": parsed,
        "current_stage": "policy_verified",
        "trace": [{"agent": "policy_verification",
                   "detail": {"details": details, "coverage": coverage, "balance": balance,
                              "retrieved_policy_clauses": policy_context},
                   "llm_raw": raw}],
    }
