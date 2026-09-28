import pytest

from naver_searchad_mcp.client import CONFIRM_ACTION, NaverSearchAdClient, WriteConfirmationRequired
from naver_searchad_mcp.server import (
    get_error_code,
    get_operation_schema,
    list_operations,
    list_sections,
    list_tags,
    search_error_codes,
    search_operations,
    validate_official_spec,
)
from naver_searchad_mcp.spec import get_registry


def test_metadata_tools_return_full_registry_data():
    sections = list_sections()["sections"]
    assert len(sections) == 9
    ops = list_operations("ncc-report")["operations"]
    assert len(ops) == 8
    schema = get_operation_schema(ops[0]["operation_key"], view="full")
    assert "raw" in schema
    assert schema["operation_key"] == ops[0]["operation_key"]
    assert validate_official_spec()["ok"] is True


def test_error_tool():
    assert get_error_code("1001")["found"] is True


def test_write_confirmation_constant_is_required_by_client():
    operation = get_registry().get_operation("ncc-heroes-ncc:addUsingPOST_3")
    client = NaverSearchAdClient.__new__(NaverSearchAdClient)
    with pytest.raises(WriteConfirmationRequired):
        client.execute_operation(operation)


def test_list_tags_tool_exposes_all_official_tags():
    result = list_tags()
    tags = {t["tag"] for t in result["tags"]}
    # 25 official user tags + 3 swagger-only extras = 28
    assert len(tags) >= 25
    assert "Campaign" in tags
    assert "Adgroup" in tags
    assert "Bizmoney" in tags


def test_list_operations_tool_supports_tag_filter():
    only_campaign = list_operations(tag="Campaign")["operations"]
    assert only_campaign
    for op in only_campaign:
        assert "Campaign" in op["tags"]


def test_search_operations_tool_returns_dict_with_operations_key():
    result = search_operations("campaign")
    assert "operations" in result
    assert result["operations"]


def test_search_error_codes_tool_returns_dict_with_results_key():
    result = search_error_codes("그룹")
    assert "results" in result
    assert isinstance(result["results"], list)


def test_read_tool_rejects_writes_before_loading_credentials(monkeypatch):
    from naver_searchad_mcp import server

    monkeypatch.setattr(server, "NaverSearchAdClient", lambda: pytest.fail("Client must not be created"))
    with pytest.raises(ValueError, match="GET operations only"):
        server.execute_read_operation("ncc-heroes-ncc:addUsingPOST_3")


@pytest.mark.parametrize("enabled", [None, "0", "true"])
def test_writes_disabled_before_loading_credentials(monkeypatch, enabled):
    from naver_searchad_mcp import server

    monkeypatch.setattr(server, "_allow_writes", False)
    monkeypatch.delenv("NAVER_SEARCHAD_ALLOW_WRITES", raising=False)
    if enabled is not None:
        monkeypatch.setenv("NAVER_SEARCHAD_ALLOW_WRITES", enabled)
    monkeypatch.setattr(server, "NaverSearchAdClient", lambda: pytest.fail("Client must not be created"))
    with pytest.raises(PermissionError, match="writes are disabled"):
        server.execute_operation("ncc-heroes-ncc:addUsingPOST_3", confirm_action=CONFIRM_ACTION)


def test_enabled_writes_still_require_per_call_confirmation(monkeypatch):
    from naver_searchad_mcp import server
    from naver_searchad_mcp.auth import NaverSearchAdCredentials
    import httpx

    monkeypatch.setenv("NAVER_SEARCHAD_ALLOW_WRITES", "1")
    client = NaverSearchAdClient(
        NaverSearchAdCredentials("test-account", "test-license", "test-secret"),
        http_client=httpx.Client(transport=httpx.MockTransport(lambda request: pytest.fail("No request expected"))),
    )
    monkeypatch.setattr(server, "NaverSearchAdClient", lambda: client)
    try:
        with pytest.raises(WriteConfirmationRequired):
            server.execute_operation("ncc-heroes-ncc:addUsingPOST_3")
    finally:
        client.http_client.close()


@pytest.mark.parametrize("state", ["ready", "completed", "stopped"])
@pytest.mark.asyncio
async def test_batch_mcp_results_preserve_error_state_and_close_client(monkeypatch, state):
    import json
    from naver_searchad_mcp import server

    class FakeClient:
        closed = False

        def close(self):
            self.closed = True

    fake = FakeClient()
    monkeypatch.setenv("NAVER_SEARCHAD_ALLOW_WRITES", "1")
    monkeypatch.setattr(server, "NaverSearchAdClient", lambda: fake)
    monkeypatch.setattr(server.bulk, "execute_keyword_batch", lambda *args, **kwargs: {
        "state": state, "next_offset": 100, "batches": [],
    })
    result = await server.mcp.call_tool("execute_keyword_batch", {
        "plan_id": "test", "sha256": "test", "start_offset": 0, "confirm_action": CONFIRM_ACTION,
    })
    assert result.isError is (state == "stopped")
    assert json.loads(result.content[0].text) == result.structuredContent
    assert fake.closed


@pytest.mark.parametrize("status_code", [200, 400, 429, 500])
@pytest.mark.asyncio
async def test_upstream_error_status_and_body_reach_mcp(monkeypatch, status_code):
    import json
    from naver_searchad_mcp import server
    from naver_searchad_mcp.client import ApiResponse

    class FakeClient:
        closed = False

        def execute_operation(self, operation, **kwargs):
            assert operation.method == "GET"
            return ApiResponse(status_code, {}, {"message": "네이버 응답", "code": "1001"})

        def close(self):
            self.closed = True

    fake = FakeClient()
    monkeypatch.setattr(server, "NaverSearchAdClient", lambda: fake)
    operation_key = next(op["operation_key"] for op in list_operations()["operations"] if op["method"] == "GET")
    result = await server.mcp.call_tool("execute_read_operation", {"operation_key": operation_key})
    assert result.isError is (status_code >= 400)
    assert result.structuredContent["body"] == {"message": "네이버 응답", "code": "1001"}
    assert json.loads(result.content[0].text) == result.structuredContent
    assert fake.closed


@pytest.mark.parametrize("args", [["--host", "0.0.0.0"], ["--host", "192.168.1.2"], ["--port", "0"], ["--port", "65536"]])
def test_cli_rejects_public_binding_and_invalid_ports(monkeypatch, args):
    from naver_searchad_mcp import server

    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: pytest.fail("Server must not start"))
    with pytest.raises(SystemExit) as error:
        server.main(args)
    assert error.value.code == 2


@pytest.mark.parametrize("transport", ["stdio", "streamable-http"])
def test_cli_configures_transport_without_starting_server(monkeypatch, transport):
    from naver_searchad_mcp import server

    received = []
    monkeypatch.setattr(server.mcp, "run", lambda **kwargs: received.append(kwargs))
    monkeypatch.setattr(server, "_allow_writes", False)
    monkeypatch.setattr(server.mcp.settings, "host", "127.0.0.1")
    monkeypatch.setattr(server.mcp.settings, "port", 8000)
    server.main(["--transport", transport, "--host", "localhost", "--port", "8765", "--allow-writes"])
    assert received == [{"transport": transport}]
    assert server._allow_writes is True
    assert server.mcp.settings.host == "localhost"
    assert server.mcp.settings.port == 8765
