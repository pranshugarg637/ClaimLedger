"""
Shared helpers for all agents: a single local Ollama LLM instance and a
robust JSON-extraction utility (small local models don't always emit
perfectly clean JSON, so we parse defensively rather than trusting it blindly
— Guardrails AI does the final strict validation downstream).
"""
import json
import re
import logging

from langchain_ollama import ChatOllama
from config import OLLAMA_BASE_URL, OLLAMA_MODEL, LLM_TEMPERATURE, LLM_TIMEOUT_SECONDS

logger = logging.getLogger("agents.llm")

_llm = None


def get_llm():
    """Singleton local LLM client. Only ever talks to localhost Ollama —
    no external/paid API calls anywhere in this system."""
    global _llm
    if _llm is None:
        _llm = ChatOllama(
            base_url=OLLAMA_BASE_URL,
            model=OLLAMA_MODEL,
            temperature=LLM_TEMPERATURE,
            timeout=LLM_TIMEOUT_SECONDS,
        )
    return _llm


def extract_json(text: str) -> dict:
    """Best-effort extraction of a JSON object from an LLM response, tolerant
    of markdown fences, leading/trailing prose, and minor formatting noise.
    Returns {} (never raises) if nothing parseable is found — callers must
    treat an empty dict as 'low confidence, needs human review'.
    """
    if not text:
        return {}

    # Strip markdown code fences if present
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fenced.group(1) if fenced else text

    # Fallback: grab the first {...} block
    if not fenced:
        brace_match = re.search(r"\{.*\}", candidate, re.DOTALL)
        candidate = brace_match.group(0) if brace_match else candidate

    try:
        return json.loads(candidate)
    except Exception:
        # Last resort: fix common issues (single quotes, trailing commas)
        try:
            cleaned = candidate.replace("'", '"')
            cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
            return json.loads(cleaned)
        except Exception as e:
            logger.warning(f"Failed to parse LLM JSON output: {e}. Raw: {text[:200]}")
            return {}


async def ask_llm_json(system_prompt: str, user_prompt: str) -> dict:
    """Call the local Ollama model with a system+user prompt and parse the
    JSON object out of the response."""
    llm = get_llm()
    messages = [
        ("system", system_prompt),
        ("human", user_prompt),
    ]
    try:
        response = await llm.ainvoke(messages)
        content = response.content if hasattr(response, "content") else str(response)
        return extract_json(content), content
    except Exception as exc:
        # MCP/database facts and deterministic decision rules can still make
        # a safe review-forcing outcome if Ollama is restarting or unavailable.
        # Do not turn a transient narrative-model failure into a tool failure.
        logger.warning("Local Ollama request failed; using deterministic fallback: %s", exc)
        return {}, f"[LLM unavailable: {exc}]"
