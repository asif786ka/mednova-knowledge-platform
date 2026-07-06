"""
MCP client + local server tests.

The config/registry logic is tested unconditionally. The live stdio round-trip (which spawns
the local FastMCP server subprocess) is skipped if the `mcp` SDK isn't installed, so the suite
still passes in a minimal environment.
"""
import pytest

from app.mcp.config import MCPServerConfig, load_mcp_config
from app.mcp.client import get_mcp_manager, MCPClientManager

try:
    import mcp  # noqa: F401

    MCP_INSTALLED = True
except Exception:
    MCP_INSTALLED = False


def test_config_defaults_to_local_stdio():
    servers = load_mcp_config()
    assert servers, "should always yield at least the default server"
    assert any(s.transport == "stdio" for s in servers)


def test_config_validation_rejects_bad_transport():
    with pytest.raises(ValueError):
        MCPServerConfig(name="x", transport="carrier-pigeon").validate()


def test_config_remote_requires_url():
    with pytest.raises(ValueError):
        MCPServerConfig(name="x", transport="streamable_http").validate()


def test_manager_status_shape():
    status = MCPClientManager().status()
    assert "available" in status and "servers" in status and "sdk_installed" in status


@pytest.mark.skipif(not MCP_INSTALLED, reason="mcp SDK not installed")
def test_stdio_roundtrip_lists_and_calls_tools():
    mgr = get_mcp_manager()
    assert mgr.available
    names = {t.name for t in mgr.list_tools()}
    assert {"search_documents", "graph_neighbors", "list_projects",
            "current_datetime"} <= names
    # call a KB-backed tool
    out = mgr.call_tool("list_projects", {})
    assert "Knowledge Platform" in out
    # call a generic tool
    ts = mgr.call_tool("current_datetime", {})
    assert "T" in ts and ":" in ts


@pytest.mark.skipif(not MCP_INSTALLED, reason="mcp SDK not installed")
def test_agent_routes_datetime_to_mcp_tool():
    from app.agents.router import AgenticRouter
    from app.ingestion.pipeline import load_stores

    vs, gs = load_stores()
    router = AgenticRouter(vs, gs)
    assert router.classify("What is the current date and time?") == "tool"
    ans = router.answer("What is the current date and time?")
    assert ans.route == "tool"
    assert ans.retrieval_strategy == "mcp_tool"
    assert ans.sources and ans.sources[0].startswith("mcp://")
