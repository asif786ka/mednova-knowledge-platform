"""
MCP server registry — transport-agnostic configuration.

Servers are declared in `mcp.config.json` at the repo root (or the path in MCP_CONFIG).
Each entry names a transport; the client builds the matching session for it. Switching a
server from local to remote is a pure config change — no code edits:

    {
      "servers": [
        {
          "name": "mednova-knowledge",
          "transport": "stdio",
          "command": "python",
          "args": ["mcp_servers/knowledge_server.py"]
        },
        {
          "name": "remote-tools",
          "transport": "streamable_http",
          "url": "https://tools.example.com/mcp",
          "headers": {"Authorization": "Bearer ${TOOLS_TOKEN}"},
          "enabled": false
        }
      ]
    }

Supported transports: "stdio" (local subprocess), "streamable_http" and "sse" (remote).
`${VAR}` placeholders in string fields are expanded from the environment.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import BASE_DIR
from app.observability import get_logger

logger = get_logger("mcp.config")

VALID_TRANSPORTS = {"stdio", "streamable_http", "sse"}


def _expand(value: Any) -> Any:
    if isinstance(value, str):
        return os.path.expandvars(value)
    if isinstance(value, list):
        return [_expand(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    return value


@dataclass
class MCPServerConfig:
    name: str
    transport: str = "stdio"
    enabled: bool = True
    # stdio
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    # remote (streamable_http / sse)
    url: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if self.transport not in VALID_TRANSPORTS:
            raise ValueError(f"{self.name}: invalid transport '{self.transport}'")
        if self.transport == "stdio" and not self.command:
            raise ValueError(f"{self.name}: stdio transport requires 'command'")
        if self.transport in ("streamable_http", "sse") and not self.url:
            raise ValueError(f"{self.name}: {self.transport} transport requires 'url'")


def _default_config() -> List[MCPServerConfig]:
    """Ship a working default: the local knowledge server over stdio."""
    return [MCPServerConfig(
        name="mednova-knowledge",
        transport="stdio",
        command="python",
        args=["mcp_servers/knowledge_server.py"],
    )]


def load_mcp_config(path: Optional[Path] = None) -> List[MCPServerConfig]:
    path = Path(path or os.getenv("MCP_CONFIG", BASE_DIR / "mcp.config.json"))
    if not path.exists():
        logger.info("No mcp.config.json found; using default local stdio server")
        return _default_config()
    try:
        raw = _expand(json.loads(path.read_text()))
        servers = []
        for entry in raw.get("servers", []):
            cfg = MCPServerConfig(
                name=entry["name"],
                transport=entry.get("transport", "stdio"),
                enabled=entry.get("enabled", True),
                command=entry.get("command"),
                args=entry.get("args", []),
                env=entry.get("env", {}),
                url=entry.get("url"),
                headers=entry.get("headers", {}),
            )
            cfg.validate()
            servers.append(cfg)
        return servers or _default_config()
    except Exception as exc:
        logger.warning("Failed to load %s (%s); using default", path, exc)
        return _default_config()
