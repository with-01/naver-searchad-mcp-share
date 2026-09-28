import json
import os
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from naver_searchad_mcp.auth import NaverSearchAdCredentials
from naver_searchad_mcp.client import (
    AUTO_SAVE_THRESHOLD_BYTES,
    CONFIRM_ACTION,
    NaverSearchAdClient,
    WriteConfirmationRequired,
    _is_failure_item,
    _save_body_to_file,
    _serialize_query_collection_format,
    read_saved_response,
    resolve_public_api_path,
)
from naver_searchad_mcp.spec import get_registry
from naver_searchad_mcp.validation import ValidationError


@pytest.fixture(autouse=True)
def private_response_cache(tmp_path, monkeypatch):
    cache = tmp_path / "responses"
    cache.mkdir()
    monkeypatch.setattr("naver_searchad_mcp.client._RESPONSE_CACHE", SimpleNamespace(name=str(cache)))
    monkeypatch.setattr("naver_searchad_mcp.client._SAVED_RESPONSES", set())
    monkeypatch.delenv("NAVER_SEARCHAD_UPLOAD_DIR", raising=False)
    return cache


def client_with_mock(handler):
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    creds = NaverSearchAdCredentials(customer_id="123", access_license="license", secret_key="secret")
    return NaverSearchAdClient(credentials=creds, http_client=http_client)


def test_get_operation_sends_public_path_and_full_body():
    operation = get_registry().get_operation("ncc-heroes-ncc:getUsingGET_16")

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.searchad.naver.com/ncc/adgroups/grp-a001"
        assert request.headers["X-API-KEY"] == "license"
        return httpx.Response(200, json={"ok": True, "items": [1, 2, 3]})

    client = client_with_mock(handler)
    result = client.execute_operation(operation, path_params={"adgroupId": "grp-a001"})
    assert result.to_dict()["body"] == {"ok": True, "items": [1, 2, 3]}


def test_resolve_public_api_path_uses_claude_audit_mapping():
    cases = [
        ("ncc-heroes-ncc", "/api/ncc/campaigns", "/ncc/campaigns"),
        ("ncc-inspect-history", "/api/ncc/inspect-history", "/ncc/inspect-history"),
        ("ncc-heroes-billing", "/api/billing/bizmoney", "/billing/bizmoney"),
        ("ncc-heroes-tool", "/api/tool/analyticses", "/tool/analyticses"),
        ("ncc-report", "/api/stat-reports", "/stat-reports"),
        ("ncc-report", "/api/stats", "/stats"),
        ("atower", "/api/ad-accounts", "/ad-accounts"),
        ("atower", "/api/manager-accounts", "/manager-accounts"),
        ("estimate", "/estimate/median-bid/keyword", "/estimate/median-bid/keyword"),
        ("master-report", "/master-reports", "/master-reports"),
        ("ncc-keywordstool", "/keywordstool", "/keywordstool"),
    ]
    for section, official_path, expected in cases:
        assert resolve_public_api_path(section, official_path) == expected


def test_signature_uri_uses_rewritten_public_path(monkeypatch):
    operation = get_registry().get_operation("ncc-heroes-ncc:getUsingGET_16")
    captured = {}

    def fake_build_headers(credentials, *, method, uri, content_type):
        captured["method"] = method
        captured["uri"] = uri
        return {"X-API-KEY": credentials.access_license}

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.searchad.naver.com/ncc/adgroups/grp-a001"
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr("naver_searchad_mcp.client.build_headers", fake_build_headers)
    client = client_with_mock(handler)
    client.execute_operation(operation, path_params={"adgroupId": "grp-a001"})
    assert captured == {"method": "GET", "uri": "/ncc/adgroups/grp-a001"}


def test_write_operation_requires_confirm_before_network_call():
    operation = get_registry().get_operation("ncc-heroes-ncc:addUsingPOST_3")
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    client = client_with_mock(handler)
    with pytest.raises(WriteConfirmationRequired):
        client.execute_operation(operation, body={"name": "campaign"})
    assert called is False


def test_validation_error_blocks_network_call_before_confirmed_write():
    operation = get_registry().get_operation("ncc-heroes-ncc:addUsingPOST_3")
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    client = client_with_mock(handler)
    with pytest.raises(ValidationError):
        client.execute_operation(operation, body=[], confirm_action=CONFIRM_ACTION)
    assert called is False


def test_multipart_file_upload_uses_files_not_json(tmp_path, monkeypatch):
    monkeypatch.setenv("NAVER_SEARCHAD_UPLOAD_DIR", str(tmp_path))
    operation = get_registry().get_operation("ncc-heroes-tool:fileUploadUsingPOST_1")
    upload = tmp_path / "keywords.csv"
    upload.write_text("keyword\nwithdetective\n", encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read()
        assert request.url.params["data"] == "metadata"
        assert request.headers["content-type"].startswith("multipart/form-data; boundary=")
        assert b"keywords.csv" in body
        assert b"withdetective" in body
        assert b"application/json" not in body
        return httpx.Response(200, json={"uploaded": True})

    client = client_with_mock(handler)
    result = client.execute_operation(
        operation,
        query={"data": "metadata"},
        body={"file": str(upload)},
        confirm_action=CONFIRM_ACTION,
    )
    assert result.body == {"uploaded": True}


def test_multipart_file_upload_rejects_missing_local_file(tmp_path, monkeypatch):
    monkeypatch.setenv("NAVER_SEARCHAD_UPLOAD_DIR", str(tmp_path))
    operation = get_registry().get_operation("ncc-heroes-tool:fileUploadUsingPOST_1")
    client = client_with_mock(lambda request: httpx.Response(500, json={"called": True}))
    with pytest.raises(RuntimeError, match="path does not exist"):
        client.execute_operation(
            operation,
            query={"data": "metadata"},
            body={"file": str(tmp_path / "missing.csv")},
            confirm_action=CONFIRM_ACTION,
        )


# === Phase 8: response file save / meta / failures / read_saved_response ===

def test_small_response_kept_as_body_without_meta():
    """작은 응답 (50KB 미만) + 실패 0건 → 기존처럼 body 그대로, meta 없음."""
    operation = get_registry().get_operation("ncc-heroes-ncc:getUsingGET_16")
    handler = lambda req: httpx.Response(200, json={"id": "grp-a001", "name": "x"})
    client = client_with_mock(handler)
    result = client.execute_operation(operation, path_params={"adgroupId": "grp-a001"})
    out = result.to_dict()
    assert out["body"] == {"id": "grp-a001", "name": "x"}
    assert "meta" not in out
    assert "failures" not in out


def test_response_redacts_customer_id_before_mcp_stdio_serialization():
    """customerId 값은 1Password stdout conceal 이 JSON-RPC 를 깨지 않도록 응답 전 마스킹."""
    operation = get_registry().get_operation("ncc-heroes-billing:getBizmoneyUsingGET")
    handler = lambda req: httpx.Response(
        200,
        json={"customerId": 123, "nested": {"customerId": "123"}, "bizmoney": 1000},
    )
    client = client_with_mock(handler)
    result = client.execute_operation(operation)
    out = result.to_dict()
    assert out["body"] == {
        "customerId": "[REDACTED]",
        "nested": {"customerId": "[REDACTED]"},
        "bizmoney": 1000,
    }



def test_large_response_auto_saved_to_temp_file():
    """50KB 초과 응답 → 자동 임시 파일 저장, body=None, meta.saved_to 채움."""
    operation = get_registry().get_operation("ncc-heroes-ncc:getCampaignsUsingGET_2")
    big = [{"nccCampaignId": f"cmp-{i:08d}", "name": "x" * 200} for i in range(500)]
    handler = lambda req: httpx.Response(200, json=big)
    client = client_with_mock(handler)
    result = client.execute_operation(operation, query={"ids": "x"})
    out = result.to_dict()
    assert out["body"] is None
    assert out["meta"]["item_count"] == 500
    assert out["meta"]["byte_size"] > AUTO_SAVE_THRESHOLD_BYTES
    assert out["meta"]["auto_saved"] is True
    saved = out["meta"]["saved_to"]
    assert os.path.isfile(saved)
    # 파일 내용 검증 후 정리
    with open(saved, encoding="utf-8") as f:
        assert json.load(f) == big
    os.remove(saved)


def test_explicit_save_filename_used_regardless_of_size(private_response_cache):
    """Explicit saves stay inside the process cache."""
    operation = get_registry().get_operation("ncc-heroes-ncc:getUsingGET_16")
    target = private_response_cache / "out.json"
    handler = lambda req: httpx.Response(200, json={"id": "grp-a001"})
    client = client_with_mock(handler)
    result = client.execute_operation(
        operation,
        path_params={"adgroupId": "grp-a001"},
        save_response_to_file="out.json",
    )
    out = result.to_dict()
    assert out["body"] is None
    assert out["meta"]["saved_to"] == str(target)
    assert out["meta"]["auto_saved"] is False
    assert target.is_file()
    assert json.loads(target.read_text(encoding="utf-8")) == {"id": "grp-a001"}


def test_failures_extracted_for_error_status_items():
    """응답 list 안에 status=ERROR 항목이 있으면 failures 배열로 노출."""
    operation = get_registry().get_operation("ncc-heroes-ncc:getCampaignsUsingGET_2")
    body = [
        {"nccKeywordId": "nkw-1", "status": "ELIGIBLE"},
        {"nccKeywordId": "nkw-2", "status": "ERROR", "statusReason": "duplicate"},
        {"nccKeywordId": "nkw-3", "inspectStatus": "REJECTED"},
    ]
    handler = lambda req: httpx.Response(200, json=body)
    client = client_with_mock(handler)
    result = client.execute_operation(operation, query={"ids": "x"})
    out = result.to_dict()
    assert out["body"] == body  # 작은 응답이라 본문 유지
    assert out["meta"]["fail_count"] == 2
    assert out["meta"]["ok_count"] == 1
    fail_indices = [f["index"] for f in out["failures"]]
    assert fail_indices == [1, 2]


def test_is_failure_item_detects_status_and_inspect():
    assert _is_failure_item({"status": "ERROR"}) is True
    assert _is_failure_item({"status": "REJECTED"}) is True
    assert _is_failure_item({"inspectStatus": "REJECTED"}) is True
    assert _is_failure_item({"status": "ELIGIBLE"}) is False
    assert _is_failure_item({"status": "ELIGIBLE", "inspectStatus": "WAITING"}) is False
    assert _is_failure_item({}) is False
    assert _is_failure_item("not-a-dict") is False


def test_read_saved_response_slice_and_fields(tmp_path):
    """read_saved_response 가 slice / fields 로 일부만 추출."""
    body = [
        {"id": i, "keyword": f"kw-{i}", "extra": "noise" * 50}
        for i in range(20)
    ]
    saved = _save_body_to_file(body, "list.json")
    result = read_saved_response(
        str(saved),
        slice_start=5,
        slice_end=10,
        fields=["id", "keyword"],
    )
    assert result["total_items"] == 20
    assert result["returned_items"] == 5
    assert result["body"] == [
        {"id": 5, "keyword": "kw-5"},
        {"id": 6, "keyword": "kw-6"},
        {"id": 7, "keyword": "kw-7"},
        {"id": 8, "keyword": "kw-8"},
        {"id": 9, "keyword": "kw-9"},
    ]


def test_read_saved_response_only_failures_filter(tmp_path):
    body = [
        {"id": 1, "status": "ELIGIBLE"},
        {"id": 2, "status": "ERROR"},
        {"id": 3, "inspectStatus": "REJECTED"},
        {"id": 4, "status": "ELIGIBLE"},
    ]
    saved = _save_body_to_file(body, "mixed.json")
    result = read_saved_response(str(saved), only_failures=True)
    assert [item["id"] for item in result["body"]] == [2, 3]


def test_read_saved_response_dict_payload(tmp_path):
    saved = _save_body_to_file({"a": 1, "b": 2, "c": 3}, "dict.json")
    result = read_saved_response(str(saved), fields=["a", "c"])
    assert result["body"] == {"a": 1, "c": 3}


@pytest.mark.parametrize("name", ["../credentials.json", "/tmp/credentials.json", "C:\\data\\credentials.json", "..\\credentials.json", "report.txt", "", "bad\u0000.json", "bad?.json", "CON.json", "LPT1.report.json", "COM¹.json", "report.json "])
def test_unsafe_save_target_is_rejected_before_network(name):
    operation = get_registry().get_operation("ncc-heroes-billing:getBizmoneyUsingGET")

    def no_network(request):
        pytest.fail("Invalid output path must fail before API execution")

    with pytest.raises(ValueError, match="filename"):
        client_with_mock(no_network).execute_operation(operation, save_response_to_file=name)


def test_saved_response_cannot_be_overwritten_before_network():
    path = _save_body_to_file({"original": True}, "report.json")
    operation = get_registry().get_operation("ncc-heroes-billing:getBizmoneyUsingGET")

    def no_network(request):
        pytest.fail("Existing output must fail before API execution")

    with pytest.raises(FileExistsError):
        client_with_mock(no_network).execute_operation(operation, save_response_to_file="report.json")
    assert json.loads(Path(path).read_text()) == {"original": True}


def test_read_saved_response_rejects_unrelated_json(tmp_path, private_response_cache):
    for path in (tmp_path / "credentials.json", private_response_cache / "unregistered.json"):
        path.write_text('{"private":"fixture"}')
        with pytest.raises(PermissionError):
            read_saved_response(str(path))


def test_read_saved_response_rejects_symlink_swap(tmp_path):
    saved = Path(_save_body_to_file({"ok": True}, "report.json"))
    unrelated = tmp_path / "unrelated.json"
    unrelated.write_text('{"private":"fixture"}')
    saved.unlink()
    try:
        saved.symlink_to(unrelated)
    except OSError:
        pytest.skip("Symlinks are unavailable on this host")
    with pytest.raises(PermissionError):
        read_saved_response(str(saved))


def test_upload_requires_explicit_directory_before_network(tmp_path):
    upload = tmp_path / "upload.csv"
    upload.write_text("keyword\nexample\n")
    operation = get_registry().get_operation("ncc-heroes-tool:fileUploadUsingPOST_1")

    def no_network(request):
        pytest.fail("Disabled upload must not call the API")

    with pytest.raises(PermissionError, match="NAVER_SEARCHAD_UPLOAD_DIR"):
        client_with_mock(no_network).execute_operation(operation, query={"data": "metadata"}, body={"file": str(upload)}, confirm_action=CONFIRM_ACTION)


def test_upload_cannot_escape_configured_directory(tmp_path, monkeypatch):
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    monkeypatch.setenv("NAVER_SEARCHAD_UPLOAD_DIR", str(allowed))
    outside = tmp_path / "outside.csv"
    outside.write_text("private fixture")
    operation = get_registry().get_operation("ncc-heroes-tool:fileUploadUsingPOST_1")

    def no_network(request):
        pytest.fail("Out-of-root upload must not call the API")

    with pytest.raises(PermissionError, match="inside"):
        client_with_mock(no_network).execute_operation(operation, query={"data": "metadata"}, body={"file": str(outside)}, confirm_action=CONFIRM_ACTION)


def test_default_swagger_query_array_encoding_is_csv():
    operation = SimpleNamespace(parameters=[{"in": "query", "name": "ids", "type": "array"}])
    assert _serialize_query_collection_format(operation, {"ids": ["a", "b"]}) == {"ids": "a,b"}


def test_cache_failure_does_not_hide_successful_ad_change(monkeypatch):
    operation = get_registry().get_operation("ncc-heroes-ncc:addUsingPOST_3")
    requests = []

    def handler(request):
        requests.append(request.method)
        return httpx.Response(200, json={"nccCampaignId": "created-campaign"})

    def unavailable_cache(*args, **kwargs):
        raise OSError("Simulated full disk")

    monkeypatch.setattr("naver_searchad_mcp.client._save_body_to_file", unavailable_cache)
    result = client_with_mock(handler).execute_operation(
        operation, body={"name": "campaign"}, confirm_action=CONFIRM_ACTION, save_response_to_file="result.json"
    )
    assert requests == ["POST"]
    assert result.status_code == 200
    assert result.body == {"nccCampaignId": "created-campaign"}
    assert "cache_error" in result.meta


@pytest.mark.parametrize("status,content,expected", [(204, b"", None), (200, b"not-json", "not-json")])
def test_empty_or_malformed_json_response_preserves_status(status, content, expected):
    operation = get_registry().get_operation("ncc-heroes-ncc:addUsingPOST_3")
    requests = []

    def handler(request):
        requests.append(request.method)
        return httpx.Response(status, content=content, headers={"Content-Type": "application/json"})

    result = client_with_mock(handler).execute_operation(operation, body={"name": "campaign"}, confirm_action=CONFIRM_ACTION)
    assert result.status_code == status
    assert result.body == expected
    assert requests == ["POST"]
