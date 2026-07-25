"""
MCP Server: Hospital Database
-------------------------------
Exposes hospital/provider network and accreditation lookups.
"""
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mcp.server.fastmcp import FastMCP
from database import db

mcp = FastMCP("hospital-database")


@mcp.tool()
def get_hospital_details(hospital_id: str) -> dict:
    """Fetch hospital/provider details including network status and
    accreditation.

    Args:
        hospital_id: hospital identifier, e.g. 'HOSP-01'.
    """
    hospital = db.get_hospital(hospital_id)
    if not hospital:
        return {"found": False, "hospital_id": hospital_id}
    hospital["found"] = True
    return hospital


@mcp.tool()
def is_in_network(hospital_id: str) -> dict:
    """Check whether a hospital is in the insurer's network.

    Args:
        hospital_id: hospital identifier.
    """
    hospital = db.get_hospital(hospital_id)
    if not hospital:
        return {"in_network": False, "reason": "hospital_not_found"}
    return {
        "in_network": hospital["network_status"] == "in-network",
        "accreditation": hospital["accreditation"],
        "prior_fraud_flags": hospital["fraud_flags"],
    }


if __name__ == "__main__":
    mcp.run(transport="stdio")
