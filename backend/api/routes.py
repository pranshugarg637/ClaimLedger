import os
import json
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Header, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import Response

from config import UPLOAD_DIR, ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB, ROLES
from database import db
from database import user_store
from graph.workflow import run_claim_workflow
from schemas import ClaimResponse, ClaimStatusResponse, DashboardStats, ManualReviewRequest, PolicyImportRequest, AuthRequest

logger = logging.getLogger("api")
router = APIRouter()


@router.post("/auth/signup")
def signup(payload: AuthRequest):
    try:
        user_store.create_user(payload.username, payload.password, payload.role)
    except ValueError as exc:
        if "already registered" in str(exc).lower():
            raise HTTPException(409, "Username is already registered")
        raise
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise HTTPException(409, "Username is already registered")
        raise
    return {"username": payload.username, "role": payload.role}


@router.post("/auth/login")
def login(payload: AuthRequest):
    try:
        user = user_store.authenticate_user(payload.username, payload.password)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc))
    if not user or user["role"] != payload.role:
        raise HTTPException(401, "Invalid username, password, or role")
    return {"username": user["username"], "role": user["role"]}

# ---------------------------------------------------------------------------
# Simple RBAC dependency (role passed via header for this local demo system;
# swap for real auth/session middleware in production)
# ---------------------------------------------------------------------------


def require_role(allowed_roles: set):
    def _dep(x_user_role: str = Header(default="claims_officer")):
        if x_user_role not in ROLES:
            raise HTTPException(400, f"Unknown role '{x_user_role}'. Must be one of {ROLES}")
        if x_user_role not in allowed_roles:
            raise HTTPException(403, f"Role '{x_user_role}' is not permitted to perform this action")
        return x_user_role
    return _dep


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------


def _validate_upload(file: UploadFile, contents: bytes):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {ALLOWED_EXTENSIONS}")
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(400, f"File too large ({size_mb:.1f}MB). Max is {MAX_FILE_SIZE_MB}MB")
    if len(contents) == 0:
        raise HTTPException(400, "Uploaded file is empty")


# ---------------------------------------------------------------------------
# 1. Upload claim
# ---------------------------------------------------------------------------


@router.post("/claims/upload", response_model=ClaimResponse)
async def upload_claim(
    patient_id: str = Form(...),
    patient_name: str = Form(...),
    policy_number: str = Form(...),
    hospital_id: str = Form(...),
    procedure_code: str = Form(...),
    claimed_amount: float = Form(...),
    document: UploadFile = File(...),
    role: str = Depends(require_role({"patient", "claims_officer", "admin"})),
    x_user_name: str = Header(default=""),
):
    contents = await document.read()
    _validate_upload(document, contents)

    # Never allow a client-provided filename to choose a path, or overwrite a
    # previous upload with the same display name.
    original_name = Path(document.filename).name
    safe_name = f"{patient_id}_{uuid.uuid4().hex[:12]}_{original_name}".replace(" ", "_")
    dest_path = UPLOAD_DIR / safe_name
    with open(dest_path, "wb") as f:
        f.write(contents)

    claim_id = db.new_claim(
        patient_id=patient_id, patient_name=patient_name, policy_number=policy_number,
        hospital_id=hospital_id, procedure_code=procedure_code, claimed_amount=claimed_amount,
        document_path=str(dest_path), submitted_by=x_user_name.strip() or None,
    )
    logger.info(f"Claim {claim_id} uploaded by role={role}")
    return ClaimResponse(claim_id=claim_id, status="submitted", message="Claim uploaded successfully. Call /claims/{claim_id}/process to run the agentic workflow.")


# ---------------------------------------------------------------------------
# 2. Process claim (runs the LangGraph workflow end-to-end)
# ---------------------------------------------------------------------------


@router.post("/claims/{claim_id}/process")
async def process_claim(claim_id: str, role: str = Depends(require_role({"claims_officer", "admin"}))):
    claim = db.get_claim(claim_id)
    if not claim:
        raise HTTPException(404, "Claim not found")

    db.update_claim_stage(claim_id, "processing", status="processing")

    initial_state = {
        "claim_id": claim_id,
        "patient_id": claim["patient_id"],
        "patient_name": claim["patient_name"],
        "policy_number": claim["policy_number"],
        "hospital_id": claim["hospital_id"],
        "procedure_code": claim["procedure_code"],
        "claimed_amount": claim["claimed_amount"],
        "document_path": claim["document_path"],
        "current_stage": "uploaded",
        "retry_count": 0,
        "errors": [],
        "trace": [],
    }

    final_state = None
    async for step_state in run_claim_workflow(initial_state):
        final_state = step_state
        db.update_claim_stage(claim_id, step_state.get("current_stage", "processing"))

    if final_state is None:
        raise HTTPException(500, "Workflow produced no output")

    db.finalize_claim(
        claim_id=claim_id,
        decision=final_state.get("decision", "needs_review"),
        confidence_score=final_state.get("confidence_score"),
        fraud_score=(final_state.get("fraud_detection") or {}).get("fraud_score"),
        state_json=json.dumps(final_state, default=str),
    )

    return {
        "claim_id": claim_id,
        "decision": final_state.get("decision"),
        "confidence_score": final_state.get("confidence_score"),
        "reasoning": final_state.get("decision_reasoning"),
        "reason_codes": final_state.get("reason_codes"),
        "evidence_bundle": final_state.get("evidence_bundle"),
        "governance_report": final_state.get("governance_report"),
    }


# ---------------------------------------------------------------------------
# 2b. Live workflow visualization via WebSocket
# ---------------------------------------------------------------------------


@router.websocket("/ws/claims/{claim_id}/process")
async def process_claim_ws(websocket: WebSocket, claim_id: str):
    """Streams each LangGraph superstep to the frontend in real time, so the
    React dashboard can render a live-updating workflow diagram."""
    await websocket.accept()
    claim = db.get_claim(claim_id)
    if not claim:
        await websocket.send_json({"error": "Claim not found"})
        await websocket.close()
        return

    db.update_claim_stage(claim_id, "processing", status="processing")

    initial_state = {
        "claim_id": claim_id,
        "patient_id": claim["patient_id"],
        "patient_name": claim["patient_name"],
        "policy_number": claim["policy_number"],
        "hospital_id": claim["hospital_id"],
        "procedure_code": claim["procedure_code"],
        "claimed_amount": claim["claimed_amount"],
        "document_path": claim["document_path"],
        "current_stage": "uploaded",
        "retry_count": 0,
        "errors": [],
        "trace": [],
    }

    try:
        final_state = None
        async for step_state in run_claim_workflow(initial_state):
            final_state = step_state
            stage = step_state.get("current_stage", "processing")
            db.update_claim_stage(claim_id, stage)
            await websocket.send_json({
                "stage": stage,
                "document_verification": step_state.get("document_verification"),
                "policy_verification": step_state.get("policy_verification"),
                "medical_validation": step_state.get("medical_validation"),
                "fraud_detection": step_state.get("fraud_detection"),
                "decision": step_state.get("decision"),
            })

        if final_state:
            db.finalize_claim(
                claim_id=claim_id,
                decision=final_state.get("decision", "needs_review"),
                confidence_score=final_state.get("confidence_score"),
                fraud_score=(final_state.get("fraud_detection") or {}).get("fraud_score"),
                state_json=json.dumps(final_state, default=str),
            )
            await websocket.send_json({"stage": "done", "final": True,
                                        "decision": final_state.get("decision"),
                                        "confidence_score": final_state.get("confidence_score"),
                                        "reasoning": final_state.get("decision_reasoning"),
                                        "reason_codes": final_state.get("reason_codes"),
                                        "evidence_bundle": final_state.get("evidence_bundle")})
    except WebSocketDisconnect:
        logger.info(f"Client disconnected during processing of {claim_id}")
    except Exception as e:
        logger.exception(f"Error processing claim {claim_id}")
        await websocket.send_json({"error": str(e)})
    finally:
        await websocket.close()


# ---------------------------------------------------------------------------
# 3. Claim status
# ---------------------------------------------------------------------------


@router.get("/claims/{claim_id}", response_model=ClaimStatusResponse)
def get_claim_status(claim_id: str):
    claim = db.get_claim(claim_id)
    if not claim:
        raise HTTPException(404, "Claim not found")
    return ClaimStatusResponse(
        claim_id=claim["claim_id"], status=claim["status"], current_stage=claim["current_stage"],
        decision=claim["decision"], confidence_score=claim["confidence_score"], fraud_score=claim["fraud_score"],
        created_at=claim["created_at"], updated_at=claim["updated_at"],
    )


@router.get("/claims")
def list_all_claims(limit: int = 100, role: str = Depends(require_role({"patient", "claims_officer", "verifier", "admin"})),
                    x_user_name: str = Header(default="")):
    patient_id = x_user_name.strip() if role == "patient" and x_user_name.strip() else None
    return db.list_claims(limit=min(limit, 500), patient_id=patient_id)


# ---------------------------------------------------------------------------
# 4. Audit logs
# ---------------------------------------------------------------------------


@router.get("/claims/{claim_id}/audit-logs")
def get_claim_audit_logs(claim_id: str, role: str = Depends(require_role({"claims_officer", "auditor", "admin"}))):
    return db.get_audit_logs(claim_id=claim_id)


@router.get("/audit-logs")
def get_all_audit_logs(limit: int = 200, role: str = Depends(require_role({"auditor", "admin"}))):
    return db.get_audit_logs(limit=limit)


@router.get("/reviews/pending")
def pending_reviews(role: str = Depends(require_role({"verifier", "admin"}))):
    return db.list_claims_for_review()


@router.post("/claims/{claim_id}/review")
def manual_review(claim_id: str, review: ManualReviewRequest,
                  role: str = Depends(require_role({"verifier", "admin"}))):
    claim = db.get_claim(claim_id)
    if not claim:
        raise HTTPException(404, "Claim not found")
    if claim.get("decision") != "needs_review":
        raise HTTPException(409, "Only claims awaiting human review can be decided here")
    db.complete_manual_review(claim_id, role, review.decision, review.reasoning)
    db.insert_audit_log(claim_id, "human_verifier", "manual_claim_decision",
                        json.dumps({"previous_decision": "needs_review"}),
                        json.dumps(review.model_dump()), 1.0, review.reasoning)
    return {"claim_id": claim_id, "decision": review.decision, "reviewed_by": role}


@router.post("/policies/import")
def import_policy(policy: PolicyImportRequest, role: str = Depends(require_role({"admin"}))):
    """Admin-only ingestion point for policy data obtained from an authorised
    insurer source. `policy_text` becomes the local policy-RAG corpus."""
    db.import_policy(policy.model_dump(), policy.patient_id, policy.holder_name, policy.policy_text)
    return {"policy_number": policy.policy_number, "status": "imported"}


# ---------------------------------------------------------------------------
# 5. Dashboard statistics
# ---------------------------------------------------------------------------


@router.get("/dashboard/stats", response_model=DashboardStats)
def get_dashboard_stats(role: str = Depends(require_role({"patient", "claims_officer", "verifier", "admin"})),
                        x_user_name: str = Header(default="")):
    patient_id = x_user_name.strip() if role == "patient" and x_user_name.strip() else None
    return db.dashboard_stats(patient_id=patient_id)


# ---------------------------------------------------------------------------
# 6. Downloadable claim report
# ---------------------------------------------------------------------------


@router.get("/claims/{claim_id}/report")
def download_claim_report(claim_id: str):
    claim = db.get_claim(claim_id)
    if not claim:
        raise HTTPException(404, "Claim not found")

    audit_logs = db.get_audit_logs(claim_id=claim_id)
    state = json.loads(claim["state_json"]) if claim.get("state_json") else {}
    governance = state.get("governance_report", {})

    lines = [
        f"# Claim Report — {claim_id}",
        "",
        f"**Patient:** {claim['patient_name']} ({claim['patient_id']})",
        f"**Policy:** {claim['policy_number']}",
        f"**Hospital:** {claim['hospital_id']}",
        f"**Procedure:** {claim['procedure_code']}",
        f"**Claimed Amount:** ₹{claim['claimed_amount']:,.2f}",
        "",
        f"## Decision: {claim['decision'] or 'Pending'}",
        f"**Confidence Score:** {claim['confidence_score']}",
        f"**Fraud Score:** {claim['fraud_score']}",
        "",
        "## Explainability",
        json.dumps(governance.get("explainability", {}), indent=2, default=str),
        "",
        "## Risk Assessment",
        json.dumps(governance.get("risk_assessment", {}), indent=2, default=str),
        "",
        "## Policy Compliance",
        json.dumps(governance.get("policy_compliance", {}), indent=2, default=str),
        "",
        "## Full Audit Trail",
    ]
    for log in audit_logs:
        lines.append(f"- [{log['timestamp']}] **{log['agent']}** → {log['action']} "
                     f"(confidence={log['confidence']}): {log['reasoning']}")

    report_text = "\n".join(lines)
    return Response(
        content=report_text,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{claim_id}_report.md"'},
    )
