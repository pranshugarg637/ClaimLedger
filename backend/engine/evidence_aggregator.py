from __future__ import annotations

from typing import Any, Dict, List


def aggregate_evidence(state: Dict[str, Any]) -> Dict[str, Any]:
    document = state.get("document_verification") or {}
    policy = state.get("policy_verification") or {}
    medical = state.get("medical_validation") or {}
    fraud = state.get("fraud_detection") or {}
    duplicate = state.get("duplicate_claim_detection") or {}

    evidence = {
        "findings": {
            "document": document.get("findings", {}),
            "policy": policy.get("findings", {}),
            "medical": medical.get("findings", {}),
            "fraud": fraud.get("findings", {}),
            "duplicate": duplicate.get("findings", {}),
        },
        "confidence": round(
            sum(
                filter(None, [
                    document.get("confidence"),
                    policy.get("confidence"),
                    medical.get("confidence"),
                    fraud.get("confidence"),
                    duplicate.get("confidence"),
                ])
            ) / max(1, len([v for v in [document.get("confidence"), policy.get("confidence"), medical.get("confidence"), fraud.get("confidence"), duplicate.get("confidence")] if v is not None])),
            3,
        ),
        "warnings": [],
        "evidence": {
            "document": document.get("evidence", {}),
            "policy": policy.get("evidence", {}),
            "medical": medical.get("evidence", {}),
            "fraud": fraud.get("evidence", {}),
            "duplicate": duplicate.get("evidence", {}),
        },
    }

    for item in [document, policy, medical, fraud, duplicate]:
        evidence["warnings"].extend(item.get("warnings") or [])
    return evidence
