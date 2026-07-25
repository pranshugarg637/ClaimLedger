# Sequence Diagram — End-to-End Claim Processing

```mermaid
sequenceDiagram
    participant User as React Frontend
    participant API as FastAPI
    participant Graph as LangGraph Workflow
    participant DocA as Document Agent
    participant PolA as Policy Agent
    participant MedA as Medical Agent
    participant FrdA as Fraud Agent
    participant DecA as Decision Agent
    participant MCP as MCP Servers
    participant LLM as Ollama (llama3.2:1b)
    participant Grd as Guardrails AI
    participant Gov as Governance Layer
    participant DB as SQLite

    User->>API: POST /api/claims/upload (form + file)
    API->>API: validate file (extension, size, non-empty)
    API->>DB: INSERT claims (status=submitted)
    API-->>User: { claim_id }

    User->>API: WS /api/ws/claims/{id}/process
    API->>DB: UPDATE claims (status=processing)
    API->>Graph: run_claim_workflow(initial_state)

    Graph->>DocA: invoke(state)
    DocA->>MCP: validate_document_integrity(file_path)
    MCP-->>DocA: {valid: true}
    DocA->>MCP: extract_document_text / extract_claim_fields
    MCP-->>DocA: OCR text + structured fields
    DocA->>Grd: validate_input_text(ocr_text)  [PII + prompt-injection scan]
    Grd-->>DocA: {safe_to_process: true}
    DocA->>LLM: reason over OCR fields → JSON verdict
    LLM-->>DocA: {is_valid, document_type, confidence, summary}
    DocA->>Grd: validate_agent_output(schema)
    DocA->>Gov: log_agent_action(...)
    DocA-->>Graph: state += document_verification
    Graph-->>API: stream stage update
    API-->>User: WS message (document_verification result)

    alt document invalid
        Graph->>DecA: invoke(state)  [skip straight to decision]
    else document valid → parallel fan-out
        par
            Graph->>PolA: invoke(state)
            PolA->>MCP: get_policy_details / check_procedure_coverage / check_sufficient_balance
            MCP-->>PolA: policy facts (ground truth)
            PolA->>LLM: summarize policy facts → JSON
            LLM-->>PolA: {policy_active, procedure_covered, sufficient_balance, confidence, summary}
            PolA->>Grd: check_hallucination(llm claims, ground truth)
            Grd-->>PolA: mismatches (if any) → ground truth wins
            PolA->>Gov: log_agent_action(...)
            PolA-->>Graph: state += policy_verification
        and
            Graph->>MedA: invoke(state)
            MedA->>MCP: get_procedure_reference / get_patient_history
            MCP-->>MedA: procedure + history facts
            MedA->>LLM: assess plausibility → JSON
            LLM-->>MedA: {clinically_plausible, cost_within_range, confidence, summary}
            MedA->>Gov: log_agent_action(...)
            MedA-->>Graph: state += medical_validation
        and
            Graph->>FrdA: invoke(state)
            FrdA->>MCP: check_duplicate_claims / is_in_network / score_claim_risk
            MCP-->>FrdA: deterministic fraud_score + reasons
            FrdA->>LLM: narrate fraud risk (score is fixed, not chosen by LLM)
            LLM-->>FrdA: {fraud_score (unchanged), risk_reasons, confidence, summary}
            FrdA->>Gov: log_agent_action(...)
            FrdA-->>Graph: state += fraud_detection
        end
        Graph-->>API: stream 3 stage updates
        API-->>User: WS messages (policy / medical / fraud results)
    end

    Graph->>DecA: invoke(state)
    DecA->>DecA: _deterministic_decision(state)  [pure Python, no LLM vote]
    DecA->>LLM: phrase explanation for the already-fixed decision
    LLM-->>DecA: {decision (must match), reasoning, confidence}
    DecA->>Gov: policy_compliance_check(state)
    Gov-->>DecA: {compliant, violations}
    alt non-compliant
        DecA->>DecA: force decision = needs_review
    end
    DecA->>Gov: assess_risk() + build_explainability_report()
    DecA->>Gov: log_agent_action("finalize_decision")
    DecA-->>Graph: state += decision, confidence_score, governance_report

    Graph-->>API: final state
    API->>DB: UPDATE claims (decision, confidence_score, fraud_score, state_json)
    API-->>User: WS final message {decision, confidence, reasoning}

    User->>API: GET /api/claims/{id}/report
    API->>DB: SELECT claim + audit_logs
    API-->>User: downloadable Markdown report
```

## Notes on the diagram

- The **parallel block** (`par ... and ... and ... end`) is a literal
  LangGraph superstep — `policy_verification`, `medical_validation`, and
  `fraud_detection` all fire concurrently because none of them depends on
  another's output, only on the document-verification stage that
  preceded them.
- **Guardrails AI appears twice per agent**: once on *input* (PII /
  prompt-injection scanning of OCR text before it ever reaches the LLM)
  and once on *output* (schema + confidence-range validation of what the
  LLM returned). The hallucination check is a third guardrail specific to
  agents that receive both LLM claims and independently-fetched ground
  truth (Policy, Medical).
- **The Decision Agent's LLM call cannot change the outcome.** Its JSON
  response is discarded and replaced with a deterministic fallback
  explanation if it disagrees with the already-computed `decision` value.
  This is the key safety property that makes a 1B local model acceptable
  for this workflow.
