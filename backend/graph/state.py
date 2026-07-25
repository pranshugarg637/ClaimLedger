"""
Shared LangGraph state for the claim-processing workflow.

Every agent node reads from and writes to this single TypedDict. LangGraph
merges partial updates returned by each node into the running state, so
agents only need to return the keys they changed. This is how "agents
communicate" in this system — there is no direct agent-to-agent messaging,
only state passed through the graph.
"""
from typing import TypedDict, Optional, List, Dict, Any
import operator
from typing_extensions import Annotated


def _merge_dicts(a: dict, b: dict) -> dict:
    merged = dict(a or {})
    merged.update(b or {})
    return merged


def _latest_stage(_: str | None, new: str | None) -> str | None:
    """Allow the three independent validation branches to report progress.

    LangGraph requires an explicit reducer when parallel nodes update the
    same state key.  The newest emitted stage is appropriate for the live UI;
    the complete per-agent results remain in their own dedicated state keys.
    """
    return new


class ClaimState(TypedDict, total=False):
    # ---- input ----
    claim_id: str
    patient_id: str
    patient_name: str
    policy_number: str
    hospital_id: str
    procedure_code: str
    claimed_amount: float
    document_path: str

    # ---- workflow control ----
    current_stage: Annotated[str, _latest_stage]
    retry_count: int
    errors: Annotated[List[str], operator.add]

    # ---- agent outputs (each agent writes its own key) ----
    document_verification: Dict[str, Any]
    ocr_result: Dict[str, Any]
    policy_verification: Dict[str, Any]
    medical_validation: Dict[str, Any]
    fraud_detection: Dict[str, Any]

    # ---- guardrails / governance ----
    guardrails_report: Dict[str, Any]
    governance_report: Dict[str, Any]

    # ---- final decision ----
    decision: str                 # approved | rejected | needs_review
    decision_reasoning: str
    confidence_score: float
    requires_human_review: bool

    # ---- audit trail (accumulates across all nodes) ----
    trace: Annotated[List[Dict[str, Any]], operator.add]
