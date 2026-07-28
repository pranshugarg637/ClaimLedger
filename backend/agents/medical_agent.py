"""
Medical Validation Agent
--------------------------
Responsibilities:
  1. Fetch procedure reference data & patient history via MCP
  2. Check whether the claimed procedure + amount are clinically/cost plausible
  3. Ask the LLM to reason about plausibility given patient history

Tools used (via MCP): history.get_procedure_reference, history.get_patient_history
"""
from mcp_servers.history_server import get_patient_history, get_procedure_reference
from agents.llm_utils import ask_llm_json
from guardrails_engine.validators import engine as guardrails_engine
from governance.audit import log_agent_action
from config import PLAN_LIMITS

SYSTEM_PROMPT = """You are a Medical Validation Agent for insurance claims.
You are given the claimed procedure, claimed amount, reference cost range
for that procedure, and the patient's medical history. Judge whether the
claim is clinically plausible and whether the cost is within a reasonable range.

Respond with ONLY a JSON object in exactly this shape:
{"clinically_plausible": true/false, "cost_within_range": true/false, "confidence": 0.0-1.0, "summary": "one sentence"}
"""


async def run(state: dict) -> dict:
    claim_id = state["claim_id"]
    procedure_code = state.get("procedure_code")
    patient_id = state["patient_id"]
    claimed_amount = state["claimed_amount"]

    procedure = get_procedure_reference(procedure_code)
    history = get_patient_history(patient_id)

    plan_type = (state.get("policy_verification") or {}).get("plan_type") or "Standard"
    limits = PLAN_LIMITS.get(plan_type, PLAN_LIMITS["Standard"])
    cost_within_range = False
    if procedure.get("found"):
        min_limit = limits.get("medical_min_ratio", 0.5)
        max_limit = limits.get("medical_max_ratio", 1.5)
        cost_within_range = procedure["typical_cost_min"] * min_limit <= claimed_amount <= procedure["typical_cost_max"] * max_limit

    ground_truth = {"cost_within_range": cost_within_range}

    user_prompt = f"""Procedure reference data: {procedure}
Patient history: {history}
Claimed amount: {claimed_amount}
Deterministic cost-range check result (ground truth, do not contradict): cost_within_range = {cost_within_range}
"""
    parsed, raw = await ask_llm_json(SYSTEM_PROMPT, user_prompt)

    if not parsed:
        parsed = {
            "clinically_plausible": procedure.get("found", False),
            "cost_within_range": cost_within_range,
            "confidence": 0.5,
            "summary": "LLM summary unavailable; based on deterministic procedure reference check only.",
        }

    hallucination = guardrails_engine.check_hallucination(
        {"cost_within_range": parsed.get("cost_within_range")}, ground_truth
    )
    if hallucination["hallucination_detected"]:
        parsed["cost_within_range"] = cost_within_range
        parsed["confidence"] = min(parsed.get("confidence", 0.5), 0.5)

    if not procedure.get("found"):
        parsed["clinically_plausible"] = False
        parsed["summary"] = f"Procedure code {procedure_code} not found in medical procedures reference."
        parsed["confidence"] = max(parsed.get("confidence", 0.5), 0.8)
    parsed["reason_codes"] = []
    if not parsed.get("clinically_plausible"):
        parsed["reason_codes"].append("MEDICAL_UNCERTAINTY")
    if not parsed.get("cost_within_range"):
        parsed["reason_codes"].append("COST_OUT_OF_RANGE")
    parsed["evidence"] = {"findings": {"clinically_plausible": parsed.get("clinically_plausible"), "cost_within_range": parsed.get("cost_within_range")}, "confidence": parsed.get("confidence"), "warnings": parsed["reason_codes"], "evidence": {"procedure": procedure, "history": history, "plan_type": plan_type}}

    validation_report = guardrails_engine.validate_agent_output("medical_validation", parsed)
    if not validation_report["schema_valid"]:
        try:
            parsed["confidence"] = min(float(parsed.get("confidence", 0.4)), 0.4)
        except (TypeError, ValueError):
            parsed["confidence"] = 0.4

    log_agent_action(claim_id, "medical_validation_agent", "validate_medical_claim",
                      {"procedure_code": procedure_code, "claimed_amount": claimed_amount}, parsed,
                      parsed.get("confidence"), parsed.get("summary"))

    return {
        "medical_validation": parsed,
        "current_stage": "medical_validated",
        "trace": [{"agent": "medical_validation", "detail": {"procedure": procedure, "history": history},
                   "llm_raw": raw}],
    }
