"""
MCP Client Manager
--------------------
Wraps `langchain_mcp_adapters.MultiServerMCPClient` so every agent gets
LangChain-compatible Tool objects backed by real MCP servers running as
local stdio subprocesses (OCR, Policy, Hospital, Fraud, Patient History).

This is the single integration point between LangGraph agents and MCP —
agents never import mcp_servers/* directly, they only ever see `tools`.
"""
import asyncio
import inspect
import json
from langchain_mcp_adapters.client import MultiServerMCPClient

from config import MCP_SERVERS

_client = None
_tools_cache = None
_lock = asyncio.Lock()


async def get_mcp_client() -> MultiServerMCPClient:
    """Create and keep one connected MCP client for the API process.

    ``MultiServerMCPClient`` 0.0.5 establishes its stdio sessions when it is
    entered as an async context manager; merely constructing it leaves the
    client disconnected.  Keeping the context open here lets the LangChain
    tools retain their backing MCP sessions for the lifetime of the app.
    """
    global _client
    if _client is None:
        _client = MultiServerMCPClient(MCP_SERVERS)
        await _client.__aenter__()
    return _client


async def get_all_tools():
    """Return a flat list of LangChain tools across all MCP servers,
    cached for the lifetime of the process (subprocess spin-up is not free)."""
    global _tools_cache
    async with _lock:
        if _tools_cache is None:
            client = await get_mcp_client()
            # Adapter releases differ: current pinned versions return the
            # already-discovered list synchronously, while newer releases
            # expose an awaitable.  Support both contracts.
            tools = client.get_tools()
            _tools_cache = await tools if inspect.isawaitable(tools) else tools
    return _tools_cache


async def get_tools_by_server(server_names: list[str]):
    """Return only the tools exposed by specific MCP servers, so each agent
    is scoped to the minimum tool surface it needs (least-privilege)."""
    # ``MultiServerMCPClient`` discovers tools lazily.  A newly-entered
    # client has no entries in ``server_name_to_tools`` until ``get_tools``
    # is called, which previously made the first document claim fail with
    # "MCP server(s) failed to expose tools: ocr".
    await get_all_tools()
    client = await get_mcp_client()
    unknown = [name for name in server_names if name not in client.server_name_to_tools]
    if unknown:
        raise RuntimeError(f"MCP server(s) failed to expose tools: {', '.join(unknown)}")
    return [tool for name in server_names for tool in client.server_name_to_tools[name]]


async def close_mcp_client():
    """Close MCP stdio subprocesses cleanly when FastAPI shuts down."""
    global _client, _tools_cache
    if _client is not None:
        await _client.__aexit__(None, None, None)
    _client = None
    _tools_cache = None


async def invoke_json_tool(tool, arguments: dict):
    """Invoke an MCP tool and decode the JSON returned over MCP stdio.

    FastMCP serializes structured return values as JSON text.  LangChain's
    adapter deliberately preserves that text, whereas agent code needs a
    Python mapping to make deterministic decisions.  Decode at this one
    boundary instead of trusting every agent to implement its own parser.
    """
    result = await tool.ainvoke(arguments)
    if isinstance(result, (dict, list)):
        return result
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"MCP tool '{tool.name}' returned invalid JSON: {result[:200]}") from exc
    raise RuntimeError(f"MCP tool '{tool.name}' returned unsupported data: {type(result).__name__}")


async def invoke_text_tool(tool, arguments: dict) -> str:
    """Invoke an MCP tool whose contract is plain text (for OCR output)."""
    result = await tool.ainvoke(arguments)
    return result if isinstance(result, str) else str(result)
