"""
Document Verification Agent
------------------------------
Responsibilities:
  1. Validate the uploaded document's structural integrity (via OCR MCP tool)
  2. Run OCR extraction to pull structured fields
  3. Run guardrails input validation (PII / prompt-injection) on OCR text
  4. Ask the local LLM to judge document validity & confidence

Tools used (via MCP): ocr.validate_document_integrity, ocr.extract_document_text,
                       ocr.extract_claim_fields
"""
import logging
import asyncio
import re
from datetime import datetime, timezone

# OCR is local and deterministic.  Calling it directly avoids making the
# critical upload path dependent on a separate stdio MCP process starting in
# time (which was causing every claim to be forced to manual review on
# Windows).  The same functions remain exposed through MCP for integrations.
from mcp_servers.ocr_server import (
    extract_claim_fields,
    extract_document_text,
    validate_document_integrity,
)
from agents.llm_utils import ask_llm_json
from guardrails_engine.validators import engine as guardrails_engine
from governance.audit import log_agent_action

logger = logging.getLogger("agents.document")


def _normalise(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _document_matches_submission(fields: dict, state: dict) -> list[str]:
    """Compare only fields actually found in the document. Missing OCR data
    leads to review, while a conflicting value is never silently trusted."""
    mappings = {"patient_name": "patient_name", "policy_number": "policy_number",
                "hospital_id": "hospital_id", "procedure_code": "procedure_code"}
    mismatches = [key for key, state_key in mappings.items()
                  if fields.get(key) and _normalise(fields[key]) != _normalise(state.get(state_key))]
    if fields.get("amount"):
        try:
            if abs(float(str(fields["amount"]).replace(",", "")) - float(state["claimed_amount"])) > 1:
                mismatches.append("amount")
        except ValueError:
            mismatches.append("amount")
    return mismatches


def _build_evidence_payload(parsed: dict, fields: dict, mismatches: list[str], fallback_failed: bool = False) -> dict:
    return {
        "findings": {
            "is_valid": parsed.get("is_valid"),
            "field_matches": not mismatches,
            "prompt_injection_detected": parsed.get("issues", []) and any("prompt_injection" in issue for issue in parsed.get("issues", [])),
            "document_fallback_failed": fallback_failed,
        },
        "confidence": float(parsed.get("confidence", 0.0) or 0.0),
        "warnings": parsed.get("issues", []),
        "evidence": {
            "ocr_fields": fields,
            "mismatches": mismatches,
            "blacklisted_hospital": False,
            "document_fallback_failed": fallback_failed,
        },
    }

SYSTEM_PROMPT = """You are a Document Verification Agent for a medical insurance claims system.
You are given OCR-extracted text and structured fields from a claim document.
Judge whether the document looks like a legitimate medical claim document
(hospital bill / discharge summary / invoice), note any issues, and give a
confidence score.

Respond with ONLY a JSON object, no other text, in exactly this shape:
{"is_valid": true/false, "document_type": "string", "issues": ["..."], "confidence": 0.0-1.0, "summary": "one sentence"}
"""


async def run(state: dict) -> dict:
    claim_id = state["claim_id"]
    document_path = state["document_path"]
    trace = []

    # Step 1: structural integrity check
    integrity = await asyncio.to_thread(validate_document_integrity, document_path)
    trace.append({"step": "document_integrity_check", "output": integrity})

    if isinstance(integrity, dict) and not integrity.get("valid", False):
        result = {
            "is_valid": False,
            "document_type": "unknown",
            "issues": [f"integrity_check_failed: {integrity.get('reason')}", "DOCUMENT_FALLBACK_FAILED"],
            "confidence": 0.95,
            "summary": f"Document failed integrity check: {integrity.get('reason')}",
            "reason_codes": ["INVALID_DOCUMENT", "DOCUMENT_FALLBACK_FAILED"],
        }
        result["evidence"] = _build_evidence_payload(result, {}, [], fallback_failed=True)
        log_agent_action(claim_id, "document_verification_agent", "reject_invalid_file",
                          {"document_path": document_path}, result, result["confidence"], result["summary"])
        return {
            "document_verification": result,
            "current_stage": "document_verification_failed",
            "trace": [{"agent": "document_verification", "detail": trace}],
        }

    # Step 2: OCR extraction
    fallback_failed = False
    try:
        ocr_text = await asyncio.wait_for(
            asyncio.to_thread(extract_document_text, document_path), timeout=30
        )
        ocr_fields = await asyncio.wait_for(
            asyncio.to_thread(extract_claim_fields, document_path), timeout=10
        )
    except (TimeoutError, asyncio.TimeoutError, RuntimeError) as exc:
        logger.warning("OCR unavailable for claim %s; continuing with review-forcing fallback: %s", claim_id, exc)
        ocr_text = "[OCR unavailable; document integrity passed but text extraction timed out.]"
        ocr_fields = {"raw_text_length": 0, "ocr_engine_status": "timeout_fallback"}
        fallback_failed = True
    trace.append({"step": "ocr_extraction", "fields": ocr_fields})
    mismatches = _document_matches_submission(ocr_fields, state)

    # Step 3: Guardrails input validation on OCR text (PII + prompt injection)
    input_validation = guardrails_engine.validate_input_text(str(ocr_text))
    trace.append({"step": "guardrails_input_validation", "output": input_validation})

    if not input_validation["safe_to_process"]:
        result = {
            "is_valid": False,
            "document_type": "unknown",
            "issues": ["prompt_injection_detected_in_document_text", "DOCUMENT_FALLBACK_FAILED"],
            "confidence": 0.9,
            "summary": "Document text contained suspicious instruction-like content and was blocked.",
            "reason_codes": ["INVALID_DOCUMENT", "DOCUMENT_FALLBACK_FAILED"],
        }
        result["evidence"] = _build_evidence_payload(result, ocr_fields, [], fallback_failed=fallback_failed)
        log_agent_action(claim_id, "document_verification_agent", "block_prompt_injection",
                          {"ocr_text_snippet": str(ocr_text)[:200]}, result, result["confidence"], result["summary"])
        return {
            "document_verification": result,
            "ocr_result": ocr_fields,
            "current_stage": "document_verification_failed",
            "trace": [{"agent": "document_verification", "detail": trace}],
        }

    # Step 4: LLM judgment (reasoning only — facts come from OCR tool, not the LLM)
    user_prompt = f"""OCR extracted fields: {ocr_fields}
Claimed patient name (from form): {state.get('patient_name')}
Claimed amount (from form): {state.get('claimed_amount')}
OCR text length: {len(str(ocr_text))} characters.
PII detected in document: {input_validation['pii_detected']}
"""
    parsed, raw = await ask_llm_json(SYSTEM_PROMPT, user_prompt)

    if not parsed:
        # Local model failed to produce valid JSON -> degrade gracefully,
        # force human review rather than guessing.
        parsed = {
            "is_valid": True,
            "document_type": "unclassified",
            "issues": ["llm_output_unparseable_defaulted_to_manual_review"],
            "confidence": 0.4,
            "summary": "LLM output could not be parsed; flagged for manual review.",
        }

    # Evidence from the document is authoritative for matching submitted
    # identifiers; a language model may describe it but cannot override it.
    parsed["field_matches"] = not mismatches
    if mismatches:
        parsed["issues"] = list(parsed.get("issues", [])) + [f"document_form_mismatch:{name}" for name in mismatches]
        parsed["confidence"] = min(float(parsed.get("confidence", 0.5)), 0.65)
        parsed["summary"] = "Document details conflict with the submitted claim fields; verifier review is required."
    elif ocr_fields.get("raw_text_length", 0) > 100:
        parsed["confidence"] = max(float(parsed.get("confidence", 0.5)), 0.9)
    parsed.setdefault("reason_codes", [])
    if fallback_failed:
        parsed["reason_codes"].append("DOCUMENT_FALLBACK_FAILED")
    if mismatches:
        parsed["reason_codes"].append("DOCUMENT_FIELD_MISMATCH")
    parsed["evidence"] = _build_evidence_payload(parsed, ocr_fields, mismatches, fallback_failed=fallback_failed)

    validation_report = guardrails_engine.validate_agent_output("document_verification", parsed)
    if not validation_report["schema_valid"]:
        try:
            parsed["confidence"] = min(float(parsed.get("confidence", 0.4)), 0.4)
        except (TypeError, ValueError):
            parsed["confidence"] = 0.4
        parsed["issues"] = parsed.get("issues", []) + ["schema_validation_failed"]

    log_agent_action(claim_id, "document_verification_agent", "verify_document",
                      {"document_path": document_path, "ocr_fields": ocr_fields},
                      parsed, parsed.get("confidence"), parsed.get("summary"))

    return {
        "document_verification": parsed,
        "ocr_result": ocr_fields,
        "current_stage": "document_verified",
        "trace": [{"agent": "document_verification", "detail": trace, "llm_raw": raw}],
    }
