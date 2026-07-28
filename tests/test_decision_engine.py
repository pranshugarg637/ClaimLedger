import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from agents import decision_agent


def test_stage1_rejects_invalid_document():
    state = {
        "document_verification": {"is_valid": False},
        "policy_verification": {"policy_active": True, "procedure_covered": True, "patient_is_covered": True},
        "medical_validation": {"clinically_plausible": True, "cost_within_range": True},
        "fraud_detection": {"fraud_score": 0.1},
    }
    decision, confidence, fraud_score = decision_agent._deterministic_decision(state)
    assert decision == "rejected"
    assert confidence == 0.0


def test_stage2_reviews_medical_uncertainty():
    state = {
        "document_verification": {"is_valid": True, "field_matches": True},
        "policy_verification": {"policy_active": True, "procedure_covered": True, "patient_is_covered": True, "sufficient_balance": True},
        "medical_validation": {"clinically_plausible": False, "cost_within_range": False},
        "fraud_detection": {"fraud_score": 0.2},
    }
    decision, _, _ = decision_agent._deterministic_decision(state)
    assert decision == "needs_review"


def test_stage3_approves_when_all_checks_pass():
    state = {
        "document_verification": {"is_valid": True, "field_matches": True, "confidence": 0.95},
        "policy_verification": {"policy_active": True, "procedure_covered": True, "patient_is_covered": True, "sufficient_balance": True, "confidence": 1.0},
        "medical_validation": {"clinically_plausible": True, "cost_within_range": True, "confidence": 0.9},
        "fraud_detection": {"fraud_score": 0.1, "confidence": 0.9},
    }
    decision, _, _ = decision_agent._deterministic_decision(state)
    assert decision == "approved"
