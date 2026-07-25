from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ClaimSubmitRequest(BaseModel):
    patient_id: str = Field(..., examples=["PAT-001"])
    patient_name: str = Field(..., examples=["Ravi Kumar"])
    policy_number: str = Field(..., examples=["POL-1001"])
    hospital_id: str = Field(..., examples=["HOSP-01"])
    procedure_code: str = Field(..., examples=["CARD-ANGIO"])
    claimed_amount: float = Field(..., gt=0, examples=[120000])


class ClaimResponse(BaseModel):
    claim_id: str
    status: str
    message: str


class ClaimStatusResponse(BaseModel):
    claim_id: str
    status: str
    current_stage: str
    decision: Optional[str] = None
    confidence_score: Optional[float] = None
    fraud_score: Optional[float] = None
    created_at: str
    updated_at: str


class AuditLogEntry(BaseModel):
    id: str
    claim_id: str
    agent: str
    action: str
    input_summary: Optional[str]
    output_summary: Optional[str]
    confidence: Optional[float]
    reasoning: Optional[str]
    timestamp: str


class DashboardStats(BaseModel):
    total_claims: int
    approved: int
    rejected: int
    needs_review: int
    pending: int
    avg_confidence: Optional[float]
    total_claimed_amount: float
    direct_approved: int = 0
    direct_rejected: int = 0
    human_approved: int = 0
    human_rejected: int = 0


class RoleHeader(BaseModel):
    role: str


class ManualReviewRequest(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected)$")
    reasoning: str = Field(..., min_length=10, max_length=2000)


class PolicyImportRequest(BaseModel):
    policy_number: str
    holder_name: str
    patient_id: str
    plan_type: str
    coverage_limit: float = Field(gt=0)
    remaining_coverage: float = Field(ge=0)
    covered_procedures: List[str]
    status: str = Field(pattern="^(active|expired|suspended)$")
    start_date: str
    end_date: str
    policy_text: str = ""


class AuthRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(pattern="^(patient|claims_officer|verifier|auditor|admin)$")
