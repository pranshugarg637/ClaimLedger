"""
MCP Server: Fraud Database
----------------------------
Exposes known fraud patterns and a rule-based fraud scoring tool.
The Fraud Detection Agent combines this deterministic score with the
LLM's reasoning for a final blended fraud assessment.
"""
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - demo fallback
    class FastMCP:  # type: ignore[override]
        def __init__(self, name):
            self.name = name
        def tool(self):
            def decorator(func):
                return func
            return decorator
        def run(self, transport=None):
            return None

from database import db

mcp = FastMCP("fraud-database")


def _as_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@mcp.tool()
def list_fraud_patterns() -> list:
    """Return the catalogue of known fraud indicator patterns used for
    rule-based screening."""
    return db.all_fraud_patterns()


@mcp.tool()
def check_duplicate_claims(patient_id: str, procedure_code: str, exclude_claim_id: str | None = None) -> dict:
    """Check whether the patient has submitted a similar claim recently
    (duplicate-claim fraud pattern).

    Args:
        patient_id: patient identifier.
        procedure_code: the procedure code on the current claim.
    """
    with db.get_conn() as conn:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        sql = "SELECT claim_id, created_at FROM claims WHERE patient_id=? AND procedure_code=? AND created_at>=? AND status NOT IN ('rejected', 'cancelled')"
        params = [patient_id, procedure_code, cutoff]
        # The active claim is inserted before the workflow starts. It is not
        # evidence of a duplicate and must never count against itself.
        if exclude_claim_id:
            sql += " AND claim_id != ?"
            params.append(exclude_claim_id)
        rows = conn.execute(sql, params).fetchall()
    return {
        "duplicate_count": len(rows),
        "is_suspicious": len(rows) > 0,
        "matching_claims": [dict(r) for r in rows],
    }


@mcp.tool()
def score_claim_risk(claimed_amount: float, procedure_code: str, hospital_fraud_flags: int,
                      duplicate_count: int, days_since_policy_start: int) -> dict:
    """Compute a deterministic 0-1 fraud risk score from structured signals.
    This is a transparent, auditable rule-based score (NOT an LLM output),
    used to keep the fraud pipeline explainable and resistant to prompt
    manipulation.

    Args:
        claimed_amount: amount claimed in INR.
        procedure_code: the medical procedure code being claimed.
        hospital_fraud_flags: number of historical fraud flags on the hospital.
        duplicate_count: number of matching prior claims for this patient/procedure.
        days_since_policy_start: how many days ago the policy started.
    """
    proc = db.get_procedure(procedure_code)
    score = 0.0
    reasons = []
    claimed_amount = _as_float(claimed_amount)
    hospital_fraud_flags = int(_as_float(hospital_fraud_flags))
    duplicate_count = int(_as_float(duplicate_count))
    days_since_policy_start = int(_as_float(days_since_policy_start, 9999))

    if proc:
        typical_cost_max = _as_float(proc.get("typical_cost_max"))
        if claimed_amount > typical_cost_max * 1.3:
            score += 0.35
            reasons.append("claimed_amount_far_above_typical_cost")
        elif claimed_amount > typical_cost_max:
            score += 0.15
            reasons.append("claimed_amount_above_typical_cost")

    if hospital_fraud_flags > 0:
        score += min(0.3, 0.1 * hospital_fraud_flags)
        reasons.append("hospital_has_prior_fraud_flags")

    if duplicate_count > 0:
        score += 0.3
        reasons.append("duplicate_claim_detected")

    if days_since_policy_start < 15:
        score += 0.2
        reasons.append("claim_shortly_after_policy_start")

    score = min(1.0, round(score, 3))
    return {"fraud_score": score, "risk_reasons": reasons}


if __name__ == "__main__":
    mcp.run(transport="stdio")
