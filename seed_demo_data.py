import os
import sys
import json
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
from database import db


def seed_claim_scenarios():
    db.init_db()
    db.seed_if_empty()

    scenarios = [
        {
            "claim_id": "CLM-REJECT-INVALID",
            "patient_id": "PAT-001",
            "patient_name": "Ravi Kumar",
            "policy_number": "POL-1001",
            "hospital_id": "HOSP-01",
            "procedure_code": "CARD-ANGIO",
            "claimed_amount": 120000,
            "document_path": "tmp/pdfs/sample_invalid.pdf",
            "status": "submitted",
            "current_stage": "uploaded",
            "decision": "rejected",
            "confidence_score": 0.0,
            "fraud_score": 0.0,
            "state_json": json.dumps({"decision": "rejected", "reason_codes": ["INVALID_DOCUMENT"]}),
        },
        {
            "claim_id": "CLM-REVIEW-MEDICAL",
            "patient_id": "PAT-002",
            "patient_name": "Anita Sharma",
            "policy_number": "POL-1002",
            "hospital_id": "HOSP-02",
            "procedure_code": "MATERNITY",
            "claimed_amount": 130000,
            "document_path": "tmp/pdfs/sample_review.pdf",
            "status": "submitted",
            "current_stage": "uploaded",
            "decision": "needs_review",
            "confidence_score": 0.0,
            "fraud_score": 0.2,
            "state_json": json.dumps({"decision": "needs_review", "reason_codes": ["MEDICAL_UNCERTAINTY"]}),
        },
        {
            "claim_id": "CLM-APPROVE-CLEAN",
            "patient_id": "PAT-003",
            "patient_name": "Mohammed Farid",
            "policy_number": "POL-1003",
            "hospital_id": "HOSP-04",
            "procedure_code": "ONCOLOGY",
            "claimed_amount": 90000,
            "document_path": "tmp/pdfs/sample_approved.pdf",
            "status": "submitted",
            "current_stage": "uploaded",
            "decision": "approved",
            "confidence_score": 0.95,
            "fraud_score": 0.1,
            "state_json": json.dumps({"decision": "approved", "reason_codes": []}),
        },
        {
            "claim_id": "CLM-MULTI-CONDITION",
            "patient_id": "PAT-001",
            "patient_name": "Ravi Kumar",
            "policy_number": "POL-1001",
            "hospital_id": "HOSP-03",
            "procedure_code": "CARD-ANGIO",
            "claimed_amount": 650000,
            "document_path": "tmp/pdfs/sample_multi.pdf",
            "status": "submitted",
            "current_stage": "uploaded",
            "decision": "needs_review",
            "confidence_score": 0.0,
            "fraud_score": 0.95,
            "state_json": json.dumps({"decision": "needs_review", "reason_codes": ["CRITICAL_FRAUD_RISK", "CLAIM_ABOVE_AUTO_APPROVAL_LIMIT"]}),
        },
    ]

    with db.get_conn() as conn:
        for scenario in scenarios:
            conn.execute(
                "INSERT OR REPLACE INTO claims (claim_id, patient_id, patient_name, policy_number, hospital_id, procedure_code, claimed_amount, document_path, status, current_stage, decision, confidence_score, fraud_score, created_at, updated_at, state_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    scenario["claim_id"],
                    scenario["patient_id"],
                    scenario["patient_name"],
                    scenario["policy_number"],
                    scenario["hospital_id"],
                    scenario["procedure_code"],
                    scenario["claimed_amount"],
                    scenario["document_path"],
                    scenario["status"],
                    scenario["current_stage"],
                    scenario["decision"],
                    scenario["confidence_score"],
                    scenario["fraud_score"],
                    "2026-01-01T00:00:00+00:00",
                    "2026-01-01T00:00:00+00:00",
                    scenario["state_json"],
                ),
            )

    print("Seeded demo claims:")
    for scenario in scenarios:
        print(scenario["claim_id"])


if __name__ == "__main__":
    seed_claim_scenarios()
