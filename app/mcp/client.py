"""
Transport-agnostic MCP client manager.

Connects to one or more MCP servers declared in mcp.config.json and exposes their tools to
the rest of the app. The transport (stdio / streamable_http / sse) is chosen per-server from
config, so the SAME client code talks to a local subprocess today and a remote HTTP endpoint
tomorrow — that is the "agnostic" requirement.

Design notes
------------
* Uses the official `mcp` Python SDK when installed; if it's missing the manager degrades
  gracefully (no tools, `available=False`) and the platform keeps working.
* MCP is async; the router and endpoints call the sync helpers (`list_tools`, `call_tool`)
  which run the coroutine on a private event loop in a worker thread, avoiding any
  "event loop already running" conflicts inside FastAPI/uvicorn.
* A session is opened per operation. For stdio that spawns the server subprocess on demand;
  tool listings are cached so we don't pay that cost on every request.
"""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional

from app.mcp.config import MCPServerConfig, load_mcp_config
from app.observability import get_logger
from app.observability.logging import log

logger = get_logger("mcp.client")

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    _MCP_AVAILABLE = True
except Exception:  # pragma: no cover
    _MCP_AVAILABLE = False


@dataclass
class ToolInfo:
    server: str
    name: str
    description: str
    input_schema: Dict[str, Any]

    def dict(self) -> Dict[str, Any]:
        return {"server": self.server, "name": self.name,
                "description": self.description, "input_schema": self.input_schema}


def _run_sync(coro):
    """Run an async coroutine to completion on a fresh loop in a dedicated thread."""
    box: Dict[str, Any] = {}

    def runner():
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            box["value"] = loop.run_until_complete(coro)
        except Exception as exc:  # pragma: no cover - surfaced to caller
            box["error"] = exc
        finally:
            loop.close()

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    t.join()
    if "error" in box:
        raise box["error"]
    return box.get("value")


class MCPClientManager:
    def __init__(self, servers: Optional[List[MCPServerConfig]] = None) -> None:
        self.servers = [s for s in (servers or load_mcp_config()) if s.enabled]
        self._tools_cache: Optional[List[ToolInfo]] = None

    @property
    def available(self) -> bool:
        return _MCP_AVAILABLE and bool(self.servers)

    # -- transport-agnostic session factory --------------------------------
    @asynccontextmanager
    async def _session(self, cfg: MCPServerConfig):
        if not _MCP_AVAILABLE:  # pragma: no cover
            raise RuntimeError("mcp SDK not installed")
        if cfg.transport == "stdio":
            import os

            params = StdioServerParameters(
                command=cfg.command, args=cfg.args,
                env={**os.environ, **cfg.env} if cfg.env else None)
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
        elif cfg.transport == "streamable_http":
            from mcp.client.streamable_http import streamablehttp_client

            async with streamablehttp_client(cfg.url, headers=cfg.headers or None) as (
                    read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
        elif cfg.transport == "sse":
            from mcp.client.sse import sse_client

            async with sse_client(cfg.url, headers=cfg.headers or None) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
        else:  # pragma: no cover
            raise ValueError(f"unknown transport {cfg.transport}")

    # -- async core --------------------------------------------------------
    async def _alist_tools(self) -> List[ToolInfo]:
        tools: List[ToolInfo] = []
        for cfg in self.servers:
            try:
                async with self._session(cfg) as session:
                    result = await session.list_tools()
                    for t in result.tools:
                        tools.append(ToolInfo(
                            server=cfg.name, name=t.name,
                            description=(t.description or "").strip(),
                            input_schema=t.inputSchema or {}))
            except Exception as exc:
                log(logger, "WARNING", "mcp server unreachable",
                    server=cfg.name, transport=cfg.transport, error=str(exc))
        return tools

    async def _acall_tool(self, tool_name: str,
                          arguments: Dict[str, Any]) -> str:
        target = None
        for t in self._tools_cache or await self._alist_tools():
            if t.name == tool_name:
                target = t
                break
        if target is None:
            raise KeyError(f"tool '{tool_name}' not found on any configured MCP server")
        cfg = next(c for c in self.servers if c.name == target.server)
        async with self._session(cfg) as session:
            result = await session.call_tool(tool_name, arguments)
            parts = []
            for block in result.content:
                text = getattr(block, "text", None)
                parts.append(text if text is not None else str(block))
            return "\n".join(parts).strip()

    # -- sync API (used by router + endpoints) -----------------------------
    def list_tools(self, refresh: bool = False) -> List[ToolInfo]:
        if not self.available:
            return []
        if self._tools_cache is None or refresh:
            self._tools_cache = _run_sync(self._alist_tools())
        return self._tools_cache

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        if not self.available:
            raise RuntimeError("MCP is not available (SDK missing or no servers configured)")
        return _run_sync(self._acall_tool(tool_name, arguments))

    def status(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "sdk_installed": _MCP_AVAILABLE,
            "servers": [{"name": s.name, "transport": s.transport} for s in self.servers],
            "tool_count": len(self.list_tools()) if self.available else 0,
        }


@lru_cache(maxsize=1)
def get_mcp_manager() -> MCPClientManager:
    return MCPClientManager()
