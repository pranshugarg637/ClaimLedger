import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from engine.decision_engine import evaluate_claim


def test_reject_path():
    state = {
        "document_verification": {"is_valid": False, "confidence": 0.95},
        "policy_verification": {"policy_active": True, "procedure_covered": True, "patient_is_covered": True, "sufficient_balance": True, "confidence": 1.0},
        "medical_validation": {"clinically_plausible": True, "cost_within_range": True, "confidence": 0.9},
        "fraud_detection": {"fraud_score": 0.1, "confidence": 0.9},
        "duplicate_claim_detection": {"duplicate_probability": 0.1, "confidence": 0.95},
    }
    result = evaluate_claim(state)
    assert result["decision"] == "rejected"
    assert result["reason_codes"] == ["INVALID_DOCUMENT"]


def test_review_path():
    state = {
        "document_verification": {"is_valid": True, "field_matches": True, "confidence": 0.95},
        "policy_verification": {"policy_active": True, "procedure_covered": True, "patient_is_covered": True, "sufficient_balance": True, "confidence": 1.0},
        "medical_validation": {"clinically_plausible": False, "cost_within_range": False, "confidence": 0.8},
        "fraud_detection": {"fraud_score": 0.2, "confidence": 0.9},
        "duplicate_claim_detection": {"duplicate_probability": 0.1, "confidence": 0.95},
    }
    result = evaluate_claim(state)
    assert result["decision"] == "needs_review"
    assert "MEDICAL_UNCERTAINTY" in result["reason_codes"]


def test_approve_path():
    state = {
        "document_verification": {"is_valid": True, "field_matches": True, "confidence": 0.95},
        "policy_verification": {"policy_active": True, "procedure_covered": True, "patient_is_covered": True, "sufficient_balance": True, "confidence": 1.0},
        "medical_validation": {"clinically_plausible": True, "cost_within_range": True, "confidence": 0.9},
        "fraud_detection": {"fraud_score": 0.1, "confidence": 0.9},
        "duplicate_claim_detection": {"duplicate_probability": 0.1, "confidence": 0.95},
    }
    result = evaluate_claim(state)
    assert result["decision"] == "approved"
