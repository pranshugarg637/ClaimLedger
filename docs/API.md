# API Documentation

Base URL: `http://localhost:8000/api`
Interactive Swagger UI: `http://localhost:8000/docs`

All endpoints that mutate or view sensitive data expect an `X-User-Role`
header (`patient` | `claims_officer` | `auditor` | `admin`). If omitted,
defaults to `claims_officer`.

---

## POST `/claims/upload`
Upload a new claim with its supporting document.

**Roles allowed:** `patient`, `claims_officer`, `admin`
**Content-Type:** `multipart/form-data`

| Field | Type | Notes |
|---|---|---|
| `patient_id` | string | e.g. `PAT-001` |
| `patient_name` | string | |
| `policy_number` | string | e.g. `POL-1001` |
| `hospital_id` | string | e.g. `HOSP-01` |
| `procedure_code` | string | e.g. `CARD-ANGIO` |
| `claimed_amount` | float | > 0 |
| `document` | file | `.pdf`, `.png`, `.jpg`, `.jpeg`, max 10MB |

**Response `200`**
```json
{ "claim_id": "CLM-8E5B7C0FEF", "status": "submitted", "message": "..." }
```

**Errors:** `400` unsupported file type / too large / empty file.

---

## POST `/claims/{claim_id}/process`
Runs the full LangGraph agentic workflow synchronously and returns the
final decision. For live progress, use the WebSocket endpoint instead.

**Roles allowed:** `claims_officer`, `admin`

**Response `200`**
```json
{
  "claim_id": "CLM-8E5B7C0FEF",
  "decision": "approved",
  "confidence_score": 0.87,
  "reasoning": "This claim has been approved. ...",
  "governance_report": {
    "risk_assessment": { "risk_level": "low", "reasons": [] },
    "policy_compliance": { "compliant": true, "violations": [] },
    "explainability": { "...": "..." }
  }
}
```

---

## WS `/ws/claims/{claim_id}/process`
Streams each LangGraph superstep as a JSON message, for live workflow
visualization.

**Message shape (per stage):**
```json
{
  "stage": "policy_verified",
  "document_verification": { "is_valid": true, "confidence": 0.9, "summary": "..." },
  "policy_verification": { "policy_active": true, "confidence": 0.85, "summary": "..." },
  "medical_validation": null,
  "fraud_detection": null,
  "decision": null
}
```

**Final message:**
```json
{ "stage": "done", "final": true, "decision": "approved", "confidence_score": 0.87, "reasoning": "..." }
```

---

## GET `/claims/{claim_id}`
Fetch current status/stage of a claim.

**Response `200`**
```json
{
  "claim_id": "CLM-8E5B7C0FEF",
  "status": "approved",
  "current_stage": "completed",
  "decision": "approved",
  "confidence_score": 0.87,
  "fraud_score": 0.05,
  "created_at": "2026-07-22T10:15:34.158835+00:00",
  "updated_at": "2026-07-22T10:16:01.442112+00:00"
}
```

---

## GET `/claims?limit=100`
List recent claims (most recent first).

---

## GET `/claims/{claim_id}/audit-logs`
Full audit trail for one claim, in chronological order.

**Roles allowed:** `claims_officer`, `auditor`, `admin`

---

## GET `/audit-logs?limit=200`
Global audit trail across all claims, most recent first.

**Roles allowed:** `auditor`, `admin`

**Response item shape:**
```json
{
  "id": "d290f1ee-...",
  "claim_id": "CLM-8E5B7C0FEF",
  "agent": "fraud_detection_agent",
  "action": "assess_fraud_risk",
  "input_summary": "{...json...}",
  "output_summary": "{...json...}",
  "confidence": 0.8,
  "reasoning": "Fraud risk is low; no duplicate claims or provider flags found.",
  "timestamp": "2026-07-22T10:15:58.001234+00:00"
}
```

---

## GET `/dashboard/stats`
Aggregate stats for the dashboard.

```json
{
  "total_claims": 42,
  "approved": 30,
  "rejected": 5,
  "needs_review": 4,
  "pending": 3,
  "avg_confidence": 0.812,
  "total_claimed_amount": 4820000.0
}
```

---

## GET `/claims/{claim_id}/report`
Downloads a Markdown claim report (decision, confidence, fraud score,
explainability, risk assessment, compliance check, and full audit trail)
as an attachment.

---

## Error format
All errors follow FastAPI's standard shape:
```json
{ "detail": "Human-readable error message" }
```
Common status codes: `400` (validation), `403` (role not permitted),
`404` (claim/policy not found), `500` (unexpected workflow failure).
