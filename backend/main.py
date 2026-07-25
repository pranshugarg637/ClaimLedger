import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import APP_LOG_PATH
from database.db import init_db, seed_if_empty
from api.routes import router as api_router
from mcp_client.client import close_mcp_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler(APP_LOG_PATH), logging.StreamHandler()],
)
logger = logging.getLogger("main")

app = FastAPI(
    title="Agentic AI Medical Insurance Claim Processing System",
    description="Local, fully open-source multi-agent claims pipeline (LangGraph + Ollama + MCP + Guardrails AI).",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    logger.info("Initializing local SQLite database...")
    init_db()
    seed_if_empty()
    logger.info("Database ready. Reference data seeded (policies, hospitals, fraud patterns, procedures).")


@app.on_event("shutdown")
async def shutdown():
    """Release the persistent MCP stdio sessions and their subprocesses."""
    await close_mcp_client()


app.include_router(api_router, prefix="/api")


@app.get("/")
def root():
    return {
        "service": "Agentic AI Medical Insurance Claim Processing System",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
