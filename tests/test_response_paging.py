"""Large-response regressions use synthetic data and never call Naver."""
import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from naver_searchad_mcp.auth import NaverSearchAdCredentials
from naver_searchad_mcp.client import (
    AUTO_SAVE_THRESHOLD_BYTES,
    CONFIRM_ACTION,
    FAILURE_PREVIEW_LIMIT,
    READ_BYTE_LIMIT,
    READ_PAGE_LIMIT,
    READ_PAGE_SIZE,
    NaverSearchAdClient,
    _build_api_response,
    _save_body_to_file,
    read_saved_response,
)
from naver_searchad_mcp.spec import get_registry


@pytest.fixture(autouse=True)
def private_response_cache(tmp_path, monkeypatch):
    cache = tmp_path / "responses"
    cache.mkdir()
    monkeypatch.setattr("naver_searchad_mcp.client._RESPONSE_CACHE", SimpleNamespace(name=str(cache)))
    monkeypatch.setattr("naver_searchad_mcp.client._SAVED_RESPONSES", set())


def test_twenty_thousand_failures_return_bounded_preview_and_keep_full_body():
    body = [
        {"nccKeywordId": f"fixture-{index}", "keyword": f"키워드{index}", "status": "ERROR", "message": "rejected"}
        for index in range(20_000)
    ]
    body[0]["message"] = "큰 오류 메시지" * 10_000
    result = _build_api_response(
        status_code=200, response_headers={}, raw_body=body, save_response_to_file=None,
    )
    assert result.body is None
    assert result.meta["item_count"] == result.meta["fail_count"] == 20_000
    assert result.meta["ok_count"] == 0
    assert result.meta["failure_preview_count"] == FAILURE_PREVIEW_LIMIT
    assert result.meta["more_failures"] is True
    assert len(result.failures) == FAILURE_PREVIEW_LIMIT
    assert [entry["index"] for entry in result.failures] == list(range(FAILURE_PREVIEW_LIMIT))
    assert "message" not in result.failures[0]["item"]
    assert len(json.dumps(result.to_dict(), ensure_ascii=False).encode("utf-8")) < READ_BYTE_LIMIT
    assert json.loads(Path(result.meta["saved_to"]).read_text(encoding="utf-8")) == body


def test_large_http_error_is_saved_without_losing_status_or_error_body():
    body = {"status": "ERROR", "code": "fixture-error", "message": "error detail " * AUTO_SAVE_THRESHOLD_BYTES}
    result = _build_api_response(
        status_code=429, response_headers={"retry-after": "60"}, raw_body=body, save_response_to_file=None,
    )
    assert result.status_code == 429
    assert result.headers == {"retry-after": "60"}
    assert result.body is None
    assert result.meta["auto_saved"] is True
    assert result.failures[0]["item"]["code"] == "fixture-error"
    assert "message" not in result.failures[0]["item"]
    assert json.loads(Path(result.meta["saved_to"]).read_text(encoding="utf-8")) == body


def test_summary_mode_saves_small_write_response_without_repeating_the_request():
    calls = []
    body = {"nccCampaignId": "fixture-campaign", "name": "fixture"}

    def handler(request):
        calls.append(request.method)
        assert json.loads(request.content)["name"] == "fixture"
        return httpx.Response(201, json=body)

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = NaverSearchAdClient(
            NaverSearchAdCredentials("fixture-account", "fixture-license", "fixture-secret"), http_client=http,
        )
        result = client.execute_operation(
            get_registry().get_operation("ncc-heroes-ncc:addUsingPOST_3"),
            body={"name": "fixture"}, confirm_action=CONFIRM_ACTION, response_mode="summary",
        )
        assert result.body is None
        assert result.status_code == 201
        assert result.meta["byte_size"] < AUTO_SAVE_THRESHOLD_BYTES
        assert read_saved_response(result.meta["saved_to"])["body"] == body
    assert calls == ["POST"]


def test_pages_recover_all_twenty_thousand_rows_in_order():
    body = [{"id": index, "keyword": f"keyword-{index}"} for index in range(20_000)]
    path = _save_body_to_file(body, "all-rows.json")
    first = read_saved_response(path)
    assert first["returned_items"] == READ_PAGE_SIZE
    assert first["next_offset"] == READ_PAGE_SIZE
    recovered = first["body"]
    offset = first["next_offset"]
    while offset is not None:
        page = read_saved_response(path, slice_start=offset, slice_end=offset + READ_PAGE_LIMIT)
        assert page["returned_items"] <= READ_PAGE_LIMIT
        assert page["total_items"] == page["matching_items"] == len(body)
        assert len(json.dumps(page["body"], ensure_ascii=False).encode("utf-8")) <= READ_BYTE_LIMIT
        recovered.extend(page["body"])
        if page["next_offset"] is not None:
            assert page["next_offset"] > offset
        offset = page["next_offset"]
    assert recovered == body


def test_sparse_failures_are_filtered_before_pagination():
    failed = {3, 75, 249}
    body = [{"id": index, "status": "ERROR" if index in failed else "ELIGIBLE"} for index in range(250)]
    path = _save_body_to_file(body, "sparse-failures.json")
    first = read_saved_response(path, only_failures=True, slice_end=1)
    assert [item["id"] for item in first["body"]] == [3]
    assert first["next_offset"] == 1
    second = read_saved_response(path, only_failures=True, slice_start=first["next_offset"])
    assert [item["id"] for item in second["body"]] == [75, 249]
    assert second["total_items"] == 250
    assert second["matching_items"] == 3
    assert second["next_offset"] is None


def test_byte_limited_page_continues_at_the_first_unreturned_row():
    body = [{"id": index, "details": "x" * 11_000} for index in range(3)]
    path = _save_body_to_file(body, "large-rows.json")
    offset = 0
    recovered = []
    for expected_id in range(3):
        page = read_saved_response(path, slice_start=offset)
        assert page["returned_items"] == 1
        assert page["body"][0]["id"] == expected_id
        recovered.extend(page["body"])
        offset = page["next_offset"]
    assert offset is None
    assert recovered == body


def test_oversized_item_can_be_recovered_with_fields_without_skipping_it():
    body = [{"id": 0}, {"id": 1, "details": "x" * READ_BYTE_LIMIT}, {"id": 2}]
    path = _save_body_to_file(body, "oversized-item.json")
    first = read_saved_response(path)
    assert first["body"] == [{"id": 0}]
    assert first["next_offset"] == 1
    blocked = read_saved_response(path, slice_start=first["next_offset"])
    assert blocked["body"] == []
    assert blocked["requires_fields"] is True
    assert blocked["slice_start"] == blocked["slice_end"] == 1
    selected = read_saved_response(path, slice_start=blocked["slice_start"], fields=["id"])
    assert selected["body"] == [{"id": 1}, {"id": 2}]
    assert selected["next_offset"] is None
    assert json.loads(Path(path).read_text(encoding="utf-8")) == body


def test_nested_collection_key_supports_bounded_pages_and_field_selection():
    rows = [{"id": index, "extra": "fixture"} for index in range(125)]
    path = _save_body_to_file({"items": rows, "metadata": "x" * READ_BYTE_LIMIT}, "nested-list.json")
    assert read_saved_response(path)["requires_fields"] is True
    page = read_saved_response(path, collection_key="items", slice_start=10, slice_end=15, fields=["id"])
    assert page["body"] == [{"id": index} for index in range(10, 15)]
    assert page["total_items"] == page["matching_items"] == len(rows)
    assert page["next_offset"] == 15


def test_requesting_all_rows_is_capped_at_the_page_limit():
    path = _save_body_to_file(list(range(250)), "capped.json")
    page = read_saved_response(path, slice_end=250)
    assert page["body"] == list(range(READ_PAGE_LIMIT))
    assert page["returned_items"] == READ_PAGE_LIMIT
    assert page["next_offset"] == READ_PAGE_LIMIT


def test_byte_cap_accounts_for_json_array_separators():
    body = ["x" * 198 for _ in range(99)] + ["x" * 96]
    path = _save_body_to_file(body, "separator-boundary.json")
    first = read_saved_response(path, slice_end=100)
    assert len(json.dumps(first["body"], ensure_ascii=False).encode("utf-8")) <= READ_BYTE_LIMIT
    assert first["next_offset"] is not None
    second = read_saved_response(path, slice_start=first["next_offset"])
    assert first["body"] + second["body"] == body
