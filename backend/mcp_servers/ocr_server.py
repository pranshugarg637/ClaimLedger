"""
MCP Server: OCR Service
------------------------
Exposes document text-extraction as an MCP tool over stdio, using the
official `mcp` Python SDK (FastMCP). Runs 100% locally with pytesseract.

Any MCP-compatible client (our LangChain agents, Claude Desktop, another
LangGraph app, etc.) can attach to this server and call `extract_document_text`
or `extract_claim_fields` without knowing anything about the OCR internals —
that's the whole point of MCP: tools are decoupled from the agent that uses them.
"""
import sys
import re
import os
import subprocess
from functools import lru_cache

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ocr-service")


@lru_cache(maxsize=128)
def _run_ocr(file_path: str) -> str:
    """Best-effort local OCR. Falls back gracefully if tesseract isn't installed,
    so the demo still works end-to-end without extra system dependencies."""
    try:
        ext = os.path.splitext(file_path)[1].lower()
        # Most uploaded claim PDFs are digitally generated and already contain
        # selectable text. Extract that first: it is quicker and more accurate
        # than rendering pages and running OCR, especially for names and
        # monetary values. Scanned PDFs continue to the OCR path below.
        if ext == ".pdf":
            native_text = subprocess.run(
                ["pdftotext", file_path, "-"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            ).stdout.strip()
            if len(native_text) >= 40:
                return native_text

        from PIL import Image
        import pytesseract

        if ext == ".pdf":
            from pdf2image import convert_from_path
            # Bound external poppler/tesseract work so a malformed scan can
            # never leave the live claim workflow waiting indefinitely.
            pages = convert_from_path(file_path, timeout=20)
            text = "\n".join(pytesseract.image_to_string(p, timeout=20) for p in pages)
        else:
            text = pytesseract.image_to_string(Image.open(file_path), timeout=20)
        return text.strip()
    except Exception as e:
        # Deterministic offline fallback so the pipeline never hard-fails
        # just because tesseract/poppler aren't installed on the host.
        return (
            f"[OCR_FALLBACK: engine unavailable ({e.__class__.__name__}). "
            f"Returning filename-derived stub text for {os.path.basename(file_path)}]"
        )


@mcp.tool()
def extract_document_text(file_path: str) -> str:
    """Run OCR on a claim document (PDF or image) and return raw extracted text.

    Args:
        file_path: absolute path to the uploaded document on local disk.
    """
    if not os.path.exists(file_path):
        return f"ERROR: file not found at {file_path}"
    return _run_ocr(file_path)


@mcp.tool()
def extract_claim_fields(file_path: str) -> dict:
    """Extract structured fields (patient name, hospital, procedure, amount)
    from a claim document using OCR + regex heuristics.

    Args:
        file_path: absolute path to the uploaded document.
    """
    text = _run_ocr(file_path)

    def find(pattern, default=None):
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else default

    fields = {
        "raw_text_length": len(text),
        "patient_name": find(
            r"patient\s*name\s*[:\-]\s*(.+?)(?=\s{2,}date\s+of\s+birth\s*[:\-]|[\r\n]|$)"
        ),
        "hospital_name": find(
            r"hospital\s*name\s*[:\-]\s*(.+?)(?=\s{2,}hospital\s+address\s*[:\-]|[\r\n]|$)"
        ),
        "procedure": find(
            r"procedure\s*name\s*[:\-]\s*(.+?)(?=\s{2,}date\s+of\s+procedure\s*[:\-]|[\r\n]|$)"
        ),
        "amount": find(
            r"(?:claimed\s+amount(?:\s*\([^)]*\))?|total\s+hospital\s+bill\s+amount|amount\s+claimed|amount|total)\s*[:\-]?\s*(?:rs\.?|inr)?\s*([\d,]+)"
        ),
        "policy_number": find(r"policy\s*(?:number|no\.?)\s*[:\-]\s*([A-Za-z0-9-]+)"),
        "hospital_id": find(r"hospital\s*(?:code|id)\s*[:\-]\s*([A-Za-z0-9-]+)"),
        "procedure_code": find(r"(?:procedure|treatment)\s*code\s*[:\-]\s*([A-Za-z0-9-]+)"),
        "ocr_engine_status": "ok" if "OCR_FALLBACK" not in text else "fallback_stub",
    }
    return fields


@mcp.tool()
def validate_document_integrity(file_path: str) -> dict:
    """Check whether a document file looks structurally valid (non-empty,
    readable, correct extension) before running full OCR.

    Args:
        file_path: absolute path to the uploaded document.
    """
    if not os.path.exists(file_path):
        return {"valid": False, "reason": "file_not_found"}
    size = os.path.getsize(file_path)
    if size == 0:
        return {"valid": False, "reason": "empty_file"}
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in {".pdf", ".png", ".jpg", ".jpeg"}:
        return {"valid": False, "reason": f"unsupported_extension_{ext}"}
    return {"valid": True, "size_bytes": size, "extension": ext}


if __name__ == "__main__":
    mcp.run(transport="stdio")
