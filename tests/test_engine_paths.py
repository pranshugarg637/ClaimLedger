import os
import sys
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from engine.decision_engine import evaluate_claim
from agents import medical_agent


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


def test_medical_agent_handles_string_claim_amount(monkeypatch):
    monkeypatch.setattr("agents.medical_agent.get_procedure_reference", lambda procedure_code: {"found": True, "typical_cost_min": "80000", "typical_cost_max": "150000"})
    monkeypatch.setattr("agents.medical_agent.get_patient_history", lambda patient_id: {"found": True, "known_conditions": []})
    monkeypatch.setattr("agents.medical_agent.log_agent_action", lambda *args, **kwargs: None)
    async def _fake_ask_llm_json(system_prompt, user_prompt):
        return {}, "raw"

    monkeypatch.setattr("agents.medical_agent.ask_llm_json", _fake_ask_llm_json)

    state = {
        "claim_id": "CLM-1",
        "patient_id": "PAT-001",
        "procedure_code": "CARD-ANGIO",
        "claimed_amount": "120000",
        "policy_verification": {"plan_type": "Standard"},
    }

    result = asyncio.run(medical_agent.run(state))
    assert result["medical_validation"]["cost_within_range"] is True
