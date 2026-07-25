# ClaimLedger — Agentic AI Medical Insurance Claim Processing System

A production-shaped, **100% local, open-source** multi-agent system that
processes medical insurance claims end-to-end: document verification →
policy check → medical validation → fraud detection → governed decision —
with every step logged, explained, and guardrailed.

No OpenAI, no Anthropic, no Gemini, no paid APIs. The only LLM is
**Ollama running `llama3.2:1b` on your own machine.**

```
Frontend (React+Tailwind) → FastAPI → LangGraph → 5 Agents → MCP Tools → Guardrails AI → Governance → Decision → Dashboard
```

---

## 1. What's in the box

| Layer | Technology | Purpose |
|---|---|---|
| LLM | Ollama (`llama3.2:1b`) | Local reasoning/synthesis only — never the source of facts |
| Agent orchestration | LangGraph + LangChain | Stateful multi-agent graph with parallel branches, retries, checkpointing |
| Tool access | MCP (Model Context Protocol) | 5 standalone local MCP servers (OCR, Policy, Hospital, Fraud, Patient History) |
| Guardrails | Guardrails AI (offline validators) | PII detection, prompt-injection detection, JSON schema, confidence bounds |
| Governance | Custom module | Audit log, explainability, risk assessment, HITL gate, policy compliance |
| Database | SQLite | Policies, hospitals, fraud patterns, procedures, patient history, claims, audit logs |
| API | FastAPI | Upload / process / status / audit / dashboard / report, + WebSocket for live progress |
| Frontend | React + Tailwind | Dashboard, upload, live tracking, audit trail, analytics |

Full architecture write-up: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
Sequence diagram: [`docs/SEQUENCE.md`](docs/SEQUENCE.md)
API reference: [`docs/API.md`](docs/API.md)

---

## 2. Why the design looks the way it does

**The LLM never gets the final vote.** Every agent fetches *ground-truth
facts* from a database or OCR engine through an MCP tool call first. The
local `llama3.2:1b` model is only asked to *summarize and explain* those
facts in plain English and estimate its own confidence. A
hallucination-guard cross-checks any factual claim the LLM makes (e.g.
"policy is active") against the tool's actual return value — if they
disagree, the tool's answer always wins and confidence is capped. The
**Decision Agent** computes approve/reject/needs-review with pure,
deterministic Python logic; the LLM is only asked to phrase the
explanation. This is what makes a 1B-parameter local model viable for a
compliance-sensitive workflow: it never has to be right about the facts,
only about the wording.

**Everything downstream of "does this look right" is a governance gate,
not an LLM opinion.** Fraud score, policy compliance, and the
human-in-the-loop threshold are hard-coded business rules
(`backend/config.py`, `backend/governance/audit.py`) that a prompt cannot
talk its way around.

---

## 3. Project structure

```
medical-claim-ai/
├── backend/
│   ├── main.py                 # FastAPI app entrypoint
│   ├── config.py                # Central config: LLM, thresholds, MCP registry, RBAC
│   ├── schemas.py                # Pydantic request/response models
│   ├── database/
│   │   └── db.py                 # SQLite schema, seed data, CRUD helpers
│   ├── mcp_servers/              # 5 standalone MCP servers (FastMCP, stdio transport)
│   │   ├── ocr_server.py          #   OCR / document field extraction
│   │   ├── policy_server.py       #   Policy database lookups
│   │   ├── hospital_server.py     #   Hospital/provider network lookups
│   │   ├── fraud_server.py        #   Fraud pattern catalogue + rule-based scoring
│   │   └── history_server.py      #   Patient history + procedure reference data
│   ├── mcp_client/
│   │   └── client.py              # LangChain↔MCP bridge (langchain-mcp-adapters)
│   ├── agents/                   # The 5 agents — each: MCP tools → facts → LLM → guardrails
│   │   ├── llm_utils.py           #   Shared Ollama client + robust JSON parsing
│   │   ├── document_agent.py
│   │   ├── policy_agent.py
│   │   ├── medical_agent.py
│   │   ├── fraud_agent.py
│   │   └── decision_agent.py
│   ├── graph/
│   │   ├── state.py                # Shared LangGraph state schema (ClaimState)
│   │   └── workflow.py             # Graph wiring: nodes, conditional/parallel edges, retries
│   ├── guardrails_engine/
│   │   └── validators.py           # Local offline Guardrails AI validators + JSON schemas
│   ├── governance/
│   │   └── audit.py                # Audit logging, risk scoring, compliance, HITL, explainability
│   ├── api/
│   │   └── routes.py               # All REST + WebSocket endpoints
│   ├── logs/                      # app.log, audit_log.jsonl (created at runtime)
│   └── uploads/                   # Uploaded claim documents (created at runtime)
├── frontend/
│   └── src/
│       ├── App.jsx                 # Shell, nav, role switcher
│       ├── api/api.js               # Axios client + WebSocket URL helper
│       └── components/
│           ├── Dashboard.jsx         # Stats + recent claims table
│           ├── ClaimUpload.jsx        # Claim intake form + file upload
│           ├── ClaimTracking.jsx      # Live workflow visualization (WebSocket)
│           ├── AuditLogs.jsx          # Audit trail viewer (role-gated)
│           └── Analytics.jsx          # Charts: decision mix, procedure volume, confidence
├── docs/
│   ├── ARCHITECTURE.md
│   ├── SEQUENCE.md
│   └── API.md
└── requirements.txt
```

**Why this separation?** `mcp_servers/` never imports `agents/`, and
`agents/` never imports `mcp_servers/` directly — they only ever meet
through `mcp_client/client.py`. That's the whole point of MCP: an agent
can be pointed at a completely different OCR or policy backend later
without changing a single line of agent code.

---

## 4. Setup guide

### Prerequisites
- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com) installed locally
- (optional, for real OCR) `tesseract-ocr` and `poppler-utils` system packages —
  without them, the OCR server automatically falls back to a stub so the
  pipeline still runs end-to-end.

### 4.1 Pull the local model
```bash
ollama pull llama3.2:1b
ollama serve   # if not already running as a service
```

### 4.2 Backend
```powershell
# Run from the project root (medical-claim-ai)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

cd backend
python -m uvicorn main:app --reload --port 8000
```
If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process Bypass`
once in that terminal. On shutdown, use `Ctrl+C`; the app now closes all MCP
subprocesses automatically.
On first boot, the SQLite database is created and seeded automatically
with sample policies, hospitals, fraud patterns, procedures, and patients.
Visit **http://localhost:8000/docs** for interactive API docs.

### 4.3 Frontend
```powershell
cd frontend
npm install
npm run dev
```
Visit **http://localhost:5173**.

### 4.4 Try it end-to-end
1. Go to **New Claim**, fill the form (sample IDs are pre-filled — try
   `POL-1001` / `HOSP-01` / `CARD-ANGIO`), attach any PDF/PNG/JPG, submit.
2. Copy the returned claim ID into **Track Claim** and click **Run Agentic
   Workflow** — watch the pipeline rail light up stage by stage in real time.
3. Check **Audit Trail** (switch role to `auditor` in the sidebar) for the
   full immutable log of every agent decision.
4. Check **Dashboard** / **Analytics** for aggregate stats.
5. Download the claim report from the tracking page once a decision lands.

### 4.5 Sample reference data (seeded automatically)
| Policies | Hospitals | Procedures |
|---|---|---|
| POL-1001 (Gold, active) | HOSP-01 (in-network) | CARD-ANGIO |
| POL-1002 (Silver, active) | HOSP-02 (in-network) | ORTHO-KNEE |
| POL-1003 (Platinum, active) | HOSP-03 (out-of-network, flagged) | GEN-SURGERY |
| POL-1004 (Silver, **expired**) | HOSP-04 (in-network) | MATERNITY, ONCOLOGY |

Try `POL-1004` to see an automatic rejection, or a `claimed_amount` far
above a procedure's typical cost to see the fraud agent trigger.

---

## 5. Configuration

All tunables live in `backend/config.py` and can be overridden via a
`.env` file in `backend/`:

```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:1b
AUTO_APPROVE_CONFIDENCE=0.85
AUTO_REJECT_FRAUD_SCORE=0.75
HUMAN_REVIEW_LOWER_BOUND=0.55
MAX_CLAIM_AMOUNT_AUTO=500000
```

---

## 6. Role-based access (demo RBAC)

Roles are passed via the `X-User-Role` header (the React sidebar has a
role switcher that sets this automatically):

| Role | Can |
|---|---|
| `patient` | Upload claims |
| `claims_officer` | Upload + process claims, view claim-level audit logs |
| `auditor` | View all audit logs (read-only) |
| `admin` | Everything |

Swap this for real session/JWT auth before any production deployment —
it's intentionally minimal here to keep the demo self-contained.

---

## 7. Known limitations (by design, for a local 1B-parameter model)

- `llama3.2:1b` occasionally returns malformed JSON. Every agent parses
  defensively (`agents/llm_utils.py:extract_json`) and falls back to a
  conservative, review-forcing default rather than guessing — this is
  intentional, not a bug to "fix" by trusting the model more.
- OCR quality depends entirely on your local `tesseract` install and the
  scan quality of the source document.
- This is a reference implementation for learning/prototyping the
  architecture, not a certified clinical or regulatory system — the
  fraud/compliance rules are illustrative, not legal advice.
