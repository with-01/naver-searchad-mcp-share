"""Protocol tests use metadata only; no credentials or Naver API access."""
import asyncio
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import pytest
from starlette.testclient import TestClient

from naver_searchad_mcp.server import mcp


@pytest.mark.asyncio
async def test_stdio_initialize_discover_and_call():
    source = Path(__file__).resolve().parents[1] / "src"
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "naver_searchad_mcp.server"],
        env={"PYTHONPATH": str(source), "NAVER_SEARCHAD_ALLOW_WRITES": "0"},
    )
    async with asyncio.timeout(30):
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                initialized = await session.initialize()
                assert initialized.serverInfo.name == "naver-searchad"
                listing = await session.list_tools()
                tools = {tool.name: tool for tool in listing.tools}
                assert tools["execute_read_operation"].annotations.readOnlyHint is True
                assert tools["execute_operation"].annotations.destructiveHint is True
                assert tools["execute_operation"].annotations.readOnlyHint is False
                assert tools["execute_keyword_batch"].annotations.destructiveHint is True
                assert tools["prepare_keyword_batch"].annotations.readOnlyHint is True
                assert tools["get_keyword_batch_status"].annotations.readOnlyHint is True
                assert all(tool.annotations is not None for tool in listing.tools)
                guide = await session.call_tool("get_usage_guide", {"topic": "tools-cheatsheet"})
                assert guide.isError is False
                assert guide.structuredContent["found"] is True
                assert guide.structuredContent["body"]
                rejected = await session.call_tool(
                    "execute_operation",
                    {"operation_key": "ncc-heroes-ncc:addUsingPOST_3", "confirm_action": "NAVER_SEARCHAD_WRITE"},
                )
                assert rejected.isError is True
                assert "writes are disabled" in rejected.content[0].text
                rejected_batch = await session.call_tool("execute_keyword_batch", {
                    "plan_id": "unknown", "sha256": "unknown", "start_offset": 0,
                    "confirm_action": "NAVER_SEARCHAD_WRITE",
                })
                assert rejected_batch.isError is True
                assert "writes are disabled" in rejected_batch.content[0].text


def test_streamable_http_initialize_metadata_and_origin_protection():
    headers = {"Accept": "application/json, text/event-stream", "Origin": "http://localhost:8000"}
    with TestClient(mcp.streamable_http_app(), base_url="http://localhost:8000") as client:
        response = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "compatibility-test", "version": "1"},
                },
            },
        )
        assert response.status_code == 200
        initialized = response.json()["result"]
        assert initialized["serverInfo"]["name"] == "naver-searchad"
        headers["MCP-Protocol-Version"] = initialized["protocolVersion"]
        response = client.post(
            "/mcp", headers=headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        )
        assert response.status_code == 202
        response = client.post(
            "/mcp", headers=headers,
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "list_sections", "arguments": {}}},
        )
        assert response.status_code == 200
        assert len(response.json()["result"]["structuredContent"]["sections"]) == 9
        response = client.post(
            "/mcp",
            headers={"Accept": "application/json, text/event-stream", "Origin": "https://untrusted.example"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        )
        assert response.status_code == 403
