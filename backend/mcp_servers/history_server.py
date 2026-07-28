"""
MCP Server: Patient History
-----------------------------
Exposes patient medical/claims history used by the Medical Validation
Agent to sanity-check clinical plausibility.
"""
import sys
import os

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

mcp = FastMCP("patient-history")


@mcp.tool()
def get_patient_history(patient_id: str) -> dict:
    """Fetch a patient's claims history and known medical conditions.

    Args:
        patient_id: patient identifier, e.g. 'PAT-001'.
    """
    history = db.get_patient_history(patient_id)
    if not history:
        return {"found": False, "patient_id": patient_id}
    import json
    history["known_conditions"] = json.loads(history["known_conditions"])
    history["found"] = True
    return history


@mcp.tool()
def get_procedure_reference(procedure_code: str) -> dict:
    """Fetch reference clinical/cost data for a medical procedure code,
    used to validate whether the claimed procedure and amount are plausible.

    Args:
        procedure_code: procedure code, e.g. 'ORTHO-KNEE'.
    """
    proc = db.get_procedure(procedure_code)
    if not proc:
        return {"found": False, "procedure_code": procedure_code}
    proc["found"] = True
    return proc


if __name__ == "__main__":
    mcp.run(transport="stdio")
