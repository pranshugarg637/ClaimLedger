"""
Guardrails AI Integration
---------------------------
All validators here are implemented as local, offline `guardrails-ai`
Validator subclasses (no calls to the Guardrails Hub, no network access) —
in keeping with the "local open-source only" constraint of this system.

Covers:
  * Input validation        -> reject malformed/oversized claim inputs
  * Prompt-injection guard   -> scan OCR text & user-supplied fields
  * PII detection            -> flag raw Aadhaar/phone/email/card numbers
  * JSON schema validation    -> every agent output validated against a
                                 pydantic schema before entering state
  * Hallucination guard      -> cross-check agent claims against DB facts
  * Confidence validation     -> reject nonsensical/out-of-range scores
"""
import re
from typing import Any, Dict
from pydantic import BaseModel, Field, ValidationError

from guardrails.validators import Validator, register_validator, PassResult, FailResult

# ---------------------------------------------------------------------------
# Local, offline custom validators (registered with the Guardrails AI runtime)
# ---------------------------------------------------------------------------

PII_PATTERNS = {
    "aadhaar": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
    "phone": re.compile(r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
}

PROMPT_INJECTION_PATTERNS = [
    r"ignore (all )?previous instructions",
    r"disregard (the )?(system|above) prompt",
    r"you are now",
    r"act as (an? )?(unrestricted|jailbroken)",
    r"reveal (your|the) (system prompt|instructions)",
    r"override (the )?(guardrails|policy|rules)",
]


@register_validator(name="local/pii-detector", data_type="string")
class PIIDetector(Validator):
    """Flags (does not silently strip) PII-looking substrings in free text
    such as OCR output, so governance can decide whether to redact/escalate."""

    def validate(self, value: str, metadata: Dict) -> PassResult | FailResult:
        findings = {}
        for label, pattern in PII_PATTERNS.items():
            matches = pattern.findall(value or "")
            if matches:
                findings[label] = len(matches)
        if findings:
            return FailResult(
                error_message=f"PII detected: {findings}",
                fix_value=value,  # we flag, we don't auto-redact claim documents
            )
        return PassResult()


@register_validator(name="local/prompt-injection-detector", data_type="string")
class PromptInjectionDetector(Validator):
    """Scans any text that will be interpolated into an LLM prompt (OCR
    output, form fields) for known prompt-injection phrasing. This is a
    heuristic first line of defense — it complements, not replaces, treating
    all document content as untrusted data rather than instructions."""

    def validate(self, value: str, metadata: Dict) -> PassResult | FailResult:
        text = (value or "").lower()
        hits = [p for p in PROMPT_INJECTION_PATTERNS if re.search(p, text)]
        if hits:
            return FailResult(error_message=f"Possible prompt injection detected: {hits}")
        return PassResult()


@register_validator(name="local/confidence-range", data_type="float")
class ConfidenceRangeValidator(Validator):
    """Confidence scores must be a real probability in [0, 1]. Anything
    outside that range indicates a malformed/hallucinated LLM output."""

    def validate(self, value, metadata: Dict) -> PassResult | FailResult:
        try:
            v = float(value)
        except (TypeError, ValueError):
            return FailResult(error_message="Confidence score is not numeric")
        if not (0.0 <= v <= 1.0):
            return FailResult(error_message=f"Confidence {v} outside valid [0,1] range")
        return PassResult()


# ---------------------------------------------------------------------------
# JSON schema contracts for each agent's structured output
# ---------------------------------------------------------------------------

class DocumentVerificationSchema(BaseModel):
    is_valid: bool
    document_type: str = Field(default="unknown")
    issues: list[str] = Field(default_factory=list)
    confidence: float
    summary: str


class PolicyVerificationSchema(BaseModel):
    policy_active: bool
    procedure_covered: bool
    sufficient_balance: bool
    confidence: float
    summary: str


class MedicalValidationSchema(BaseModel):
    clinically_plausible: bool
    cost_within_range: bool
    confidence: float
    summary: str


class FraudDetectionSchema(BaseModel):
    fraud_score: float
    risk_reasons: list[str] = Field(default_factory=list)
    confidence: float
    summary: str


class DecisionSchema(BaseModel):
    decision: str  # approved | rejected | needs_review
    reasoning: str
    confidence: float


AGENT_SCHEMAS = {
    "document_verification": DocumentVerificationSchema,
    "policy_verification": PolicyVerificationSchema,
    "medical_validation": MedicalValidationSchema,
    "fraud_detection": FraudDetectionSchema,
    "decision": DecisionSchema,
}


# ---------------------------------------------------------------------------
# Guardrails engine facade used by agents/graph nodes
# ---------------------------------------------------------------------------

class GuardrailsEngine:
    """Single entry point agents call to run every guardrail check and get
    back one consolidated validation report."""

    def validate_input_text(self, text: str) -> Dict[str, Any]:
        pii_result = PIIDetector().validate(text, {})
        injection_result = PromptInjectionDetector().validate(text, {})
        return {
            "pii_detected": isinstance(pii_result, FailResult),
            "pii_detail": getattr(pii_result, "error_message", None),
            "prompt_injection_detected": isinstance(injection_result, FailResult),
            "prompt_injection_detail": getattr(injection_result, "error_message", None),
            "safe_to_process": not isinstance(injection_result, FailResult),
        }

    def validate_agent_output(self, agent_name: str, raw_output: dict) -> Dict[str, Any]:
        schema = AGENT_SCHEMAS.get(agent_name)
        if schema is None:
            return {"schema_valid": False, "errors": [f"no schema registered for {agent_name}"]}
        try:
            validated = schema(**raw_output)
        except ValidationError as e:
            return {"schema_valid": False, "errors": e.errors(), "validated": None}

        conf_result = ConfidenceRangeValidator().validate(validated.confidence, {})
        return {
            "schema_valid": True,
            "confidence_valid": isinstance(conf_result, PassResult),
            "validated": validated.model_dump(),
        }

    def check_hallucination(self, claimed_facts: Dict[str, Any], ground_truth: Dict[str, Any]) -> Dict[str, Any]:
        """Cross-reference facts the LLM asserted against tool/DB ground
        truth. Any mismatch is flagged as a potential hallucination rather
        than silently trusted."""
        mismatches = []
        for key, claimed_value in (claimed_facts or {}).items():
            if key in (ground_truth or {}) and ground_truth[key] is not None:
                if str(claimed_value).strip().lower() != str(ground_truth[key]).strip().lower():
                    mismatches.append({"field": key, "claimed": claimed_value, "actual": ground_truth[key]})
        return {"hallucination_detected": len(mismatches) > 0, "mismatches": mismatches}


engine = GuardrailsEngine()
