"""
Global configuration for the Agentic Medical Insurance Claim Processing System.
All values are overridable via environment variables (.env) so the same code
runs unmodified across dev / staging / on-prem deployments.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# LLM (local-only, no paid APIs)
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_TIMEOUT_SECONDS = int(os.getenv("LLM_TIMEOUT_SECONDS", "60"))

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
DATABASE_PATH = str(BASE_DIR / "database" / "claims.db")
UPLOAD_DIR = BASE_DIR / "uploads"
LOG_DIR = BASE_DIR / "logs"
AUDIT_LOG_PATH = LOG_DIR / "audit_log.jsonl"
APP_LOG_PATH = LOG_DIR / "app.log"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE_MB = 10

# ---------------------------------------------------------------------------
# Governance / Guardrails thresholds
# ---------------------------------------------------------------------------
AUTO_APPROVE_CONFIDENCE = float(os.getenv("AUTO_APPROVE_CONFIDENCE", "0.85"))
AUTO_REJECT_FRAUD_SCORE = float(os.getenv("AUTO_REJECT_FRAUD_SCORE", "0.75"))
HUMAN_REVIEW_LOWER_BOUND = float(os.getenv("HUMAN_REVIEW_LOWER_BOUND", "0.55"))
MAX_CLAIM_AMOUNT_AUTO = float(os.getenv("MAX_CLAIM_AMOUNT_AUTO", "500000"))

# ---------------------------------------------------------------------------
# Roles (simple RBAC)
# ---------------------------------------------------------------------------
ROLES = {"patient", "claims_officer", "verifier", "auditor", "admin"}

# ---------------------------------------------------------------------------
# MCP servers - launched as local stdio subprocesses
# ---------------------------------------------------------------------------
MCP_SERVERS = {
    "ocr": {
        # Use the interpreter running FastAPI. On Windows, the shell's
        # ``python`` can point outside .venv and then MCP servers cannot
        # import this project's dependencies.
        "command": sys.executable,
        "args": [str(BASE_DIR / "mcp_servers" / "ocr_server.py")],
        "transport": "stdio",
    },
    "policy": {
        "command": sys.executable,
        "args": [str(BASE_DIR / "mcp_servers" / "policy_server.py")],
        "transport": "stdio",
    },
    "hospital": {
        "command": sys.executable,
        "args": [str(BASE_DIR / "mcp_servers" / "hospital_server.py")],
        "transport": "stdio",
    },
    "fraud": {
        "command": sys.executable,
        "args": [str(BASE_DIR / "mcp_servers" / "fraud_server.py")],
        "transport": "stdio",
    },
    "history": {
        "command": sys.executable,
        "args": [str(BASE_DIR / "mcp_servers" / "history_server.py")],
        "transport": "stdio",
    },
}
