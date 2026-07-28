"""
MCP Server: Policy Database
----------------------------
Exposes insurance-policy lookups as MCP tools so the Policy Verification
Agent never touches SQL directly — it only knows the tool contract.
"""
import sys
import os
import json
from datetime import date

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

mcp = FastMCP("policy-database")


def _as_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@mcp.tool()
def get_policy_details(policy_number: str) -> dict:
    """Fetch full details of an insurance policy by policy number.

    Args:
        policy_number: the policy identifier, e.g. 'POL-1001'.
    """
    policy = db.get_policy(policy_number)
    if not policy:
        return {"found": False, "policy_number": policy_number}
    policy["covered_procedures"] = json.loads(policy["covered_procedures"])
    policy["found"] = True
    return policy


@mcp.tool()
def check_procedure_coverage(policy_number: str, procedure_code: str, patient_id: str | None = None) -> dict:
    """Check whether a specific procedure is covered under a policy, and
    whether the policy is active.

    Args:
        policy_number: the policy identifier.
        procedure_code: procedure code, e.g. 'CARD-ANGIO'.
    """
    policy = db.get_policy(policy_number)
    if not policy:
        return {"covered": False, "reason": "policy_not_found"}

    covered_procedures = json.loads(policy["covered_procedures"])
    today = date.today().isoformat()
    is_active = policy["status"] == "active" and policy["start_date"] <= today <= policy["end_date"]
    is_covered = procedure_code in covered_procedures
    member_covered = db.policy_has_member(policy_number, patient_id) if patient_id else True

    return {
        "covered": bool(is_active and is_covered),
        "policy_active": is_active,
        "procedure_in_plan": is_covered,
        "patient_is_covered": member_covered,
        "policy_dates_valid": policy["start_date"] <= today <= policy["end_date"],
        "remaining_coverage": policy["remaining_coverage"],
        "plan_type": policy["plan_type"],
    }


@mcp.tool()
def check_sufficient_balance(policy_number: str, claimed_amount: float) -> dict:
    """Check whether the policy has enough remaining coverage balance for
    the claimed amount.

    Args:
        policy_number: the policy identifier.
        claimed_amount: the amount being claimed, in INR.
    """
    policy = db.get_policy(policy_number)
    if not policy:
        return {"sufficient": False, "reason": "policy_not_found"}
    remaining_coverage = _as_float(policy.get("remaining_coverage"))
    claimed_amount = _as_float(claimed_amount)
    sufficient = remaining_coverage >= claimed_amount
    return {
        "sufficient": sufficient,
        "remaining_coverage": remaining_coverage,
        "claimed_amount": claimed_amount,
        "shortfall": max(0, claimed_amount - remaining_coverage),
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
