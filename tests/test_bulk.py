import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from naver_searchad_mcp import bulk
from naver_searchad_mcp.auth import NaverSearchAdCredentials
from naver_searchad_mcp.client import CONFIRM_ACTION, NaverSearchAdClient, WriteConfirmationRequired, read_saved_response
from naver_searchad_mcp.validation import ValidationError


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    cache = tmp_path / "responses"
    cache.mkdir()
    monkeypatch.setattr("naver_searchad_mcp.client._RESPONSE_CACHE", SimpleNamespace(name=str(cache)))
    monkeypatch.setattr("naver_searchad_mcp.client._SAVED_RESPONSES", set())
    monkeypatch.setattr(bulk, "_PLANS", {})
    monkeypatch.setenv("NAVER_SEARCHAD_CUSTOMER_ID", "10001234")
    monkeypatch.setenv("NAVER_SEARCHAD_ACCESS_LICENSE", "example-license")
    monkeypatch.setenv("NAVER_SEARCHAD_SECRET_KEY", "example-secret")


@pytest.fixture
def input_dir(tmp_path, monkeypatch):
    directory = tmp_path / "input"
    directory.mkdir()
    monkeypatch.setenv("NAVER_SEARCHAD_INPUT_DIR", str(directory))
    return directory


@pytest.fixture
def client_factory(request):
    def make(handler, account="10001234"):
        http_client = httpx.Client(transport=httpx.MockTransport(handler))
        request.addfinalizer(http_client.close)
        credentials = NaverSearchAdCredentials(account, "example-license", "example-secret")
        return NaverSearchAdClient(credentials, http_client=http_client)

    return make


def write_input(directory, items):
    path = directory / "keywords.json"
    path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return path


def create_plan(directory, count=201):
    write_input(directory, [{"keyword": f"example{i}"} for i in range(count)])
    return bulk.prepare_keyword_batch("keywords.json", bulk.CREATE_KEYWORDS, {"nccAdgroupId": "grp-example"})


def execute(plan, client, start_offset=0, **kwargs):
    return bulk.execute_keyword_batch(plan["plan_id"], plan["sha256"], start_offset, CONFIRM_ACTION, client=client, **kwargs)


def success_response(request):
    items = json.loads(request.content)
    return httpx.Response(200, json=[{**item, "nccKeywordId": item.get("nccKeywordId", f"kwd-example-{index}")} for index, item in enumerate(items)])


@pytest.mark.parametrize("operation,batch_size,method", [
    (bulk.CREATE_KEYWORDS, 100, "POST"),
    (bulk.UPDATE_BIDS, 200, "PUT"),
])
def test_twenty_thousand_records_send_exact_batches_without_model_sized_replies(input_dir, client_factory, operation, batch_size, method):
    if operation == bulk.CREATE_KEYWORDS:
        items = [{"keyword": f"example{i:05d}", "bidAmt": 1000, "useGroupBidAmt": False} for i in range(20000)]
        query = {"nccAdgroupId": "grp-example"}
    else:
        items = [{"nccKeywordId": f"kwd-example-{i}", "nccAdgroupId": "grp-example", "bidAmt": 1000 + i % 20 * 10, "useGroupBidAmt": False} for i in range(20000)]
        query = {"fields": "bidAmt"}
    write_input(input_dir, items)
    plan = bulk.prepare_keyword_batch("keywords.json", operation, query)
    assert plan["item_count"] == 20000
    assert plan["batch_count"] == 20000 // batch_size
    assert len(plan["sample"]) == 3
    assert len(json.dumps(plan)) < 4000
    seen = []
    requests = []

    def handler(request):
        payload = json.loads(request.content)
        assert request.method == method
        assert request.url.path == "/ncc/keywords"
        assert dict(request.url.params) == query
        assert request.headers["X-Customer"] == "10001234"
        assert len(payload) == batch_size
        requests.append(request)
        seen.extend(payload)
        return success_response(request)

    client = client_factory(handler)
    offset = 0
    while offset < 20000:
        reply = execute(plan, client, offset, max_batches=10)
        assert len(json.dumps(reply)) < 30000
        assert all("body" not in result for result in reply["batches"])
        assert all(Path(result["meta"]["saved_to"]).is_file() for result in reply["batches"])
        offset = reply["next_offset"]
    assert reply["state"] == "completed"
    assert seen == items
    assert len(requests) == 20000 // batch_size
    status = bulk.get_keyword_batch_status(plan["plan_id"])
    assert status["total_batches"] == len(requests)
    assert len(status["batches"]) == 20
    assert status["next_result_offset"] == 20
    assert len(bulk.get_keyword_batch_status(plan["plan_id"], 20)["batches"]) == 20


def test_prepared_snapshot_cannot_be_changed_by_file_query_or_preview(input_dir, client_factory):
    original = [{"keyword": "approved", "bidAmt": 1000, "useGroupBidAmt": False}]
    write_input(input_dir, original)
    query = {"nccAdgroupId": "grp-approved"}
    plan = bulk.prepare_keyword_batch("keywords.json", bulk.CREATE_KEYWORDS, query)
    write_input(input_dir, [{"keyword": "changed-on-disk", "bidAmt": 100000}])
    query["nccAdgroupId"] = "grp-changed"
    plan["sample"][0]["keyword"] = "changed-through-preview"

    def handler(request):
        assert json.loads(request.content) == original
        assert request.url.params["nccAdgroupId"] == "grp-approved"
        return success_response(request)

    assert execute(plan, client_factory(handler))["state"] == "completed"


def test_input_requires_operator_configured_directory(input_dir, monkeypatch):
    path = write_input(input_dir, [{"keyword": "example"}])
    monkeypatch.delenv("NAVER_SEARCHAD_INPUT_DIR")
    with pytest.raises(PermissionError, match="operator-configured"):
        bulk.prepare_keyword_batch(str(path), bulk.CREATE_KEYWORDS, {"nccAdgroupId": "grp-example"})


@pytest.mark.parametrize("path_kind", ["absolute", "traversal", "symlink"])
def test_input_cannot_escape_allowed_directory(input_dir, path_kind):
    outside = input_dir.parent / "outside.json"
    outside.write_text('[{"keyword":"outside"}]')
    if path_kind == "symlink":
        candidate = input_dir / "link.json"
        try:
            candidate.symlink_to(outside)
        except (OSError, NotImplementedError):
            pytest.skip("Creating symlinks is unavailable on this test host")
    elif path_kind == "traversal":
        candidate = "../outside.json"
    else:
        candidate = outside
    with pytest.raises(PermissionError, match="inside"):
        bulk.prepare_keyword_batch(str(candidate), bulk.CREATE_KEYWORDS, {"nccAdgroupId": "grp-example"})
    assert not bulk._PLANS


@pytest.mark.parametrize("items", [{}, [], [1], [{}], [{"keyword": " "}]])
def test_invalid_create_file_never_creates_executable_plan(input_dir, items):
    write_input(input_dir, items)
    with pytest.raises(ValueError):
        bulk.prepare_keyword_batch("keywords.json", bulk.CREATE_KEYWORDS, {"nccAdgroupId": "grp-example"})
    assert not bulk._PLANS


def test_all_batches_are_validated_before_plan_is_published(input_dir):
    items = [{"keyword": f"example{i}"} for i in range(201)]
    items[-1]["bidAmt"] = "not-an-integer"
    write_input(input_dir, items)
    with pytest.raises(ValidationError, match="bidAmt"):
        bulk.prepare_keyword_batch("keywords.json", bulk.CREATE_KEYWORDS, {"nccAdgroupId": "grp-example"})
    assert not bulk._PLANS


def test_oversized_input_is_rejected_without_creating_plan(input_dir):
    (input_dir / "keywords.json").write_bytes(b"[" + b" " * bulk.INPUT_BYTE_LIMIT + b"]")
    with pytest.raises(ValueError, match="file limit"):
        bulk.prepare_keyword_batch("keywords.json", bulk.CREATE_KEYWORDS, {"nccAdgroupId": "grp-example"})
    assert not bulk._PLANS


def test_preparation_does_not_echo_large_optional_payload(input_dir):
    write_input(input_dir, [{"keyword": "example", "links": {"pc": {"final": "https://example.com/" + "x" * 100000}}}])
    plan = bulk.prepare_keyword_batch("keywords.json", bulk.CREATE_KEYWORDS, {"nccAdgroupId": "grp-example"})
    assert plan["sample"] == [{"keyword": "example"}]
    assert len(json.dumps(plan)) < 4000


@pytest.mark.parametrize("missing", ["nccKeywordId", "nccAdgroupId", "bidAmt", "useGroupBidAmt"])
def test_bid_plan_requires_exact_identity_and_bid_fields(input_dir, missing):
    record = {"nccKeywordId": "kwd-example", "nccAdgroupId": "grp-example", "bidAmt": 1000, "useGroupBidAmt": False}
    del record[missing]
    write_input(input_dir, [record])
    with pytest.raises(ValueError, match=missing):
        bulk.prepare_keyword_batch("keywords.json", bulk.UPDATE_BIDS, {"fields": "bidAmt"})


def test_duplicate_bid_target_is_rejected_before_any_write(input_dir):
    record = {"nccKeywordId": "kwd-example", "nccAdgroupId": "grp-example", "bidAmt": 1000, "useGroupBidAmt": False}
    write_input(input_dir, [record, record])
    with pytest.raises(ValueError, match="unique"):
        bulk.prepare_keyword_batch("keywords.json", bulk.UPDATE_BIDS, {"fields": "bidAmt"})


@pytest.mark.parametrize("failure", ["confirmation", "digest", "account", "unknown_plan"])
def test_execution_authorization_is_checked_before_http(input_dir, client_factory, failure):
    plan = create_plan(input_dir, 1)

    def no_network(request):
        pytest.fail("Authorization failure must not send a request")

    client = client_factory(no_network, account="different-account" if failure == "account" else "10001234")
    with pytest.raises((WriteConfirmationRequired, PermissionError, ValueError)):
        bulk.execute_keyword_batch(
            "unknown" if failure == "unknown_plan" else plan["plan_id"],
            "wrong" if failure == "digest" else plan["sha256"],
            0, "wrong" if failure == "confirmation" else CONFIRM_ACTION, client=client,
        )
    assert bulk.get_keyword_batch_status(plan["plan_id"])["next_offset"] == 0


@pytest.mark.parametrize("max_batches", [0, 11])
def test_execution_call_has_bounded_number_of_requests(input_dir, client_factory, max_batches):
    plan = create_plan(input_dir)
    with pytest.raises(ValueError, match="max_batches"):
        execute(plan, client_factory(lambda request: pytest.fail("Unexpected request")), max_batches=max_batches)


def test_lost_reply_can_be_recovered_without_replaying_a_batch(input_dir, client_factory):
    plan = create_plan(input_dir)
    calls = []

    def handler(request):
        calls.append(request)
        return success_response(request)

    client = client_factory(handler)
    execute(plan, client)  # Simulate losing the tool reply after the HTTP response.
    status = bulk.get_keyword_batch_status(plan["plan_id"])
    assert status["state"] == "ready"
    assert status["next_offset"] == 100
    assert len(calls) == 1
    cached = read_saved_response(status["batches"][0]["meta"]["saved_to"])
    assert cached["body"][0]["keyword"] == "example0"
    with pytest.raises(ValueError, match="replay"):
        execute(plan, client, 0)
    assert len(calls) == 1
    assert execute(plan, client, 100, max_batches=10)["state"] == "completed"
    with pytest.raises(ValueError, match="replay"):
        execute(plan, client, 201)
    assert len(calls) == 3


@pytest.mark.parametrize("condition", ["http_error", "partial", "missing_ids", "explicit_failure"])
def test_uncertain_or_failed_response_stops_without_next_batch(input_dir, client_factory, condition):
    plan = create_plan(input_dir)
    calls = []

    def handler(request):
        calls.append(request)
        if condition == "http_error":
            return httpx.Response(429, json={"code": 429, "message": "Too many requests"})
        records = [{"nccKeywordId": f"kwd-example-{i}"} for i in range(100)]
        if condition == "partial":
            records.pop()
        elif condition == "missing_ids":
            records = [{"unexpected": True} for _ in range(100)]
        else:
            records[0]["status"] = "ERROR"
        return httpx.Response(200, json=records)

    client = client_factory(handler)
    result = execute(plan, client, max_batches=10)
    assert result["state"] == "stopped"
    assert result["next_offset"] == 0
    assert result["batches"][0]["outcome"] == "review_required"
    assert len(calls) == 1
    with pytest.raises(ValueError, match="replay"):
        execute(plan, client)
    assert len(calls) == 1


def test_timeout_is_recorded_as_unknown_and_never_retried(input_dir, client_factory):
    plan = create_plan(input_dir)
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("Synthetic timeout after sending", request=request)

    client = client_factory(handler)
    result = execute(plan, client, max_batches=10)
    assert result["state"] == "stopped"
    assert result["batches"][0]["outcome"] == "unknown"
    status = bulk.get_keyword_batch_status(plan["plan_id"])
    assert status["batches"][0]["outcome"] == "unknown"
    with pytest.raises(ValueError, match="replay"):
        execute(plan, client)
    assert len(calls) == 1


def test_cancellation_after_send_still_prevents_replay(input_dir, client_factory):
    plan = create_plan(input_dir)
    calls = []

    class Cancelled(BaseException):
        pass

    def handler(request):
        calls.append(request)
        raise Cancelled()

    client = client_factory(handler)
    with pytest.raises(Cancelled):
        execute(plan, client, max_batches=10)
    assert bulk.get_keyword_batch_status(plan["plan_id"])["state"] == "stopped"
    with pytest.raises(ValueError, match="replay"):
        execute(plan, client)
    assert len(calls) == 1


def test_cache_failure_stops_and_preserves_already_received_body(input_dir, client_factory, monkeypatch):
    plan = create_plan(input_dir)
    calls = []

    def handler(request):
        calls.append(request)
        return success_response(request)

    def cannot_save(*args, **kwargs):
        raise OSError("Synthetic disk failure")

    monkeypatch.setattr("naver_searchad_mcp.client._save_body_to_file", cannot_save)
    result = execute(plan, client_factory(handler), max_batches=10)
    assert result["state"] == "stopped"
    assert result["batches"][0]["meta"]["cache_error"]
    assert len(result["batches"][0]["body"]) == 100
    assert len(calls) == 1


def test_overlapping_execution_is_rejected_and_status_reports_running(input_dir, client_factory):
    plan = create_plan(input_dir, 1)

    def handler(request):
        assert bulk.get_keyword_batch_status(plan["plan_id"])["state"] == "executing"
        with pytest.raises(ValueError, match="already executing"):
            execute(plan, client)
        return success_response(request)

    client = client_factory(handler)
    assert execute(plan, client)["state"] == "completed"
