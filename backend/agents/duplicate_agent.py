from __future__ import annotations

from typing import Any, Dict

from mcp_servers.fraud_server import check_duplicate_claims
from governance.audit import log_agent_action


async def run(state: dict) -> dict:
    claim_id = state["claim_id"]
    patient_id = state["patient_id"]
    procedure_code = state.get("procedure_code")
    duplicate_check = check_duplicate_claims(patient_id, procedure_code, exclude_claim_id=claim_id)
    duplicate_probability = 0.0
    if duplicate_check.get("duplicate_count", 0) > 0:
        duplicate_probability = min(1.0, 0.4 + 0.2 * duplicate_check.get("duplicate_count", 0))
    result = {
        "duplicate_probability": duplicate_probability,
        "confidence": 0.95,
        "summary": "Duplicate claim evaluation completed.",
        "reason_codes": [],
        "evidence": {
            "findings": {"duplicate_probability": duplicate_probability},
            "confidence": 0.95,
            "warnings": [],
            "evidence": {"duplicate_check": duplicate_check},
        },
    }
    if duplicate_probability >= 0.6:
        result["reason_codes"].append("DUPLICATE_CLAIM_SUSPECTED")
    log_agent_action(claim_id, "duplicate_claim_agent", "check_duplicates", {"patient_id": patient_id, "procedure_code": procedure_code}, result, result.get("confidence"), result.get("summary"))
    return {"duplicate_claim_detection": result, "current_stage": "duplicate_checked", "trace": [{"agent": "duplicate_claim_detection", "detail": {"duplicate_check": duplicate_check}}]}
