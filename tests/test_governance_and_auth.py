import os
import sys

import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from governance.audit import assess_risk, policy_compliance_check, requires_human_review
from api.routes import login, signup
from schemas import AuthRequest


def test_assess_risk_accepts_string_inputs():
    report = assess_risk("0.8", "0.6", "120000")
    assert report["risk_level"] == "high"
    assert "fraud_score_above_reject_threshold" in report["reasons"]


def test_policy_compliance_check_accepts_string_inputs():
    report = policy_compliance_check(
        {
            "decision": "approved",
            "claimed_amount": "650000",
            "fraud_detection": {"fraud_score": "0.9"},
            "requires_human_review": False,
        }
    )
    assert report["compliant"] is False
    assert "high_fraud_score_cannot_be_approved" in report["violations"]


def test_requires_human_review_accepts_string_inputs():
    assert requires_human_review("0.1", "0.6", "100000") is True


def test_signup_maps_duplicate_value_error(monkeypatch):
    def _raise(*args, **kwargs):
        raise ValueError("Username is already registered")

    monkeypatch.setattr("api.routes.user_store.create_user", _raise)

    with pytest.raises(HTTPException) as exc_info:
        signup(AuthRequest(username="tester01", password="password123", role="patient"))

    assert exc_info.value.status_code == 409


def test_login_maps_runtime_error(monkeypatch):
    def _raise(*args, **kwargs):
        raise RuntimeError("MongoDB Atlas is configured but unavailable; fix the connection before signing in or signing up.")

    monkeypatch.setattr("api.routes.user_store.authenticate_user", _raise)

    with pytest.raises(HTTPException) as exc_info:
        login(AuthRequest(username="tester01", password="password123", role="patient"))

    assert exc_info.value.status_code == 503