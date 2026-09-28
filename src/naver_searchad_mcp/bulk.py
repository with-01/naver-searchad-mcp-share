"""File-backed keyword requests. No retries or background jobs."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from .auth import NaverSearchAdCredentials
from .client import CONFIRM_ACTION, NaverSearchAdClient, WriteConfirmationRequired
from .spec import KEYWORD_BATCH_LIMITS, get_registry
from .validation import validate_operation_input

INPUT_BYTE_LIMIT = 16 * 1024 * 1024
CREATE_KEYWORDS = "ncc-heroes-ncc:addUsingPOST_4"
UPDATE_BIDS = "ncc-heroes-ncc:modifyUsingPUT_9"


@dataclass
class KeywordPlan:
    operation_key: str
    query: dict[str, Any]
    items: list[dict[str, Any]]
    account: str
    digest: str
    next_offset: int = 0
    state: str = "ready"
    results: list[dict[str, Any]] = field(default_factory=list)
    lock: Any = field(default_factory=Lock)


_PLANS: dict[str, KeywordPlan] = {}


def prepare_keyword_batch(path: str, operation_key: str, query: dict[str, Any]) -> dict[str, Any]:
    """Load an operator-approved JSON array and validate every batch without HTTP."""
    if operation_key not in KEYWORD_BATCH_LIMITS:
        raise ValueError("Only keyword creation and bulk bid updates support file batches")
    if operation_key == UPDATE_BIDS and query != {"fields": "bidAmt"}:
        raise ValueError("Bulk bid updates require query={\"fields\":\"bidAmt\"}")
    root = os.getenv("NAVER_SEARCHAD_INPUT_DIR")
    if not root:
        raise PermissionError("File batches require operator-configured NAVER_SEARCHAD_INPUT_DIR")
    allowed = Path(root).expanduser().resolve()
    candidate = Path(path).expanduser()
    candidate = (candidate if candidate.is_absolute() else allowed / candidate).resolve()
    if not candidate.is_relative_to(allowed):
        raise PermissionError("Input must be inside NAVER_SEARCHAD_INPUT_DIR")
    if candidate.suffix.lower() != ".json" or not candidate.is_file():
        raise ValueError("Input must be a JSON file containing an array of keyword objects")
    with candidate.open("rb") as stream:
        raw = stream.read(INPUT_BYTE_LIMIT + 1)
    if len(raw) > INPUT_BYTE_LIMIT:
        raise ValueError("Input JSON exceeds the 16 MiB file limit")
    items = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(items, list) or not items or not all(isinstance(item, dict) for item in items):
        raise ValueError("Input must be a nonempty JSON array of keyword objects")
    if operation_key == CREATE_KEYWORDS:
        for index, item in enumerate(items):
            if not isinstance(item.get("keyword"), str) or not item["keyword"].strip():
                raise ValueError(f"body[{index}].keyword must be a nonempty string")
    if operation_key == UPDATE_BIDS:
        seen = set()
        for index, item in enumerate(items):
            for key in ("nccKeywordId", "nccAdgroupId", "bidAmt", "useGroupBidAmt"):
                if key not in item:
                    raise ValueError(f"body[{index}].{key} is required for bulk bid updates")
            keyword_id = item["nccKeywordId"]
            if not isinstance(keyword_id, str) or not keyword_id or keyword_id in seen:
                raise ValueError(f"body[{index}].nccKeywordId must be a unique nonempty string")
            seen.add(keyword_id)
    operation = get_registry().get_operation(operation_key)
    batch_size = KEYWORD_BATCH_LIMITS[operation_key]
    for offset in range(0, len(items), batch_size):
        validate_operation_input(operation, query=query, body=items[offset:offset + batch_size])
    # Bind the reviewed snapshot to the account, operation, query and exact data.
    # Later edits to the input file cannot change the approved plan.
    account = NaverSearchAdCredentials.from_env().customer_id
    snapshot = json.dumps([account, operation_key, query, items], ensure_ascii=False, sort_keys=True)
    digest = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()
    plan_id = uuid4().hex
    _PLANS[plan_id] = KeywordPlan(operation_key, dict(query), items, account, digest)
    bids = [item["bidAmt"] for item in items if isinstance(item.get("bidAmt"), (int, float))]
    group_ids = {item.get("nccAdgroupId") for item in items if item.get("nccAdgroupId")}
    if query.get("nccAdgroupId"):
        group_ids.add(query["nccAdgroupId"])
    return {
        "plan_id": plan_id, "sha256": digest, "operation_key": operation_key,
        "account_suffix": account[-4:], "item_count": len(items), "batch_size": batch_size,
        "batch_count": (len(items) + batch_size - 1) // batch_size,
        "group_count": len(group_ids), "group_sample": sorted(group_ids)[:3],
        "bid_range": [min(bids), max(bids)] if bids else None,
        "use_group_bid_count": sum(item.get("useGroupBidAmt") is True for item in items),
        "sample": [{key: value for key, value in item.items()
                    if key in {"keyword", "nccKeywordId", "nccAdgroupId", "bidAmt", "useGroupBidAmt"}
                    and len(json.dumps(value, ensure_ascii=False)) <= 200} for item in items[:3]],
        "state": "ready", "next_offset": 0,
        "notice": "Review targets and cost impact before execution. Validation makes no API calls. Plans expire at server restart.",
    }


def execute_keyword_batch(
    plan_id: str, sha256: str, start_offset: int, confirm_action: str,
    *, max_batches: int = 1, client: NaverSearchAdClient,
) -> dict[str, Any]:
    """Execute the next explicit range once, then stop on errors or ambiguity."""
    if confirm_action != CONFIRM_ACTION:
        raise WriteConfirmationRequired(f"requires confirm_action={CONFIRM_ACTION!r}")
    if not 1 <= max_batches <= 10:
        raise ValueError("max_batches must be between 1 and 10")
    plan = _PLANS.get(plan_id)
    if plan is None or plan.digest != sha256:
        raise ValueError("Unknown plan or sha256 does not match the reviewed snapshot")
    if client.credentials.customer_id != plan.account:
        raise PermissionError("The current account differs from the reviewed plan")
    if not plan.lock.acquire(blocking=False):
        raise ValueError("This plan is already executing")
    try:
        if plan.state != "ready" or start_offset != plan.next_offset:
            raise ValueError("Plan is stopped/completed or start_offset is stale; do not replay writes")
        operation = get_registry().get_operation(plan.operation_key)
        batch_size = KEYWORD_BATCH_LIMITS[plan.operation_key]
        results = []
        for _ in range(max_batches):
            start = plan.next_offset
            end = min(start + batch_size, len(plan.items))
            # A tool cancellation or unexpected exception must never make an
            # already sent request eligible for an automatic replay.
            plan.state = "stopped"
            try:
                response = client.execute_operation(
                    operation, query=plan.query, body=plan.items[start:end],
                    confirm_action=confirm_action, response_mode="summary",
                )
            except Exception:
                results.append({"start_offset": start, "end_offset": end,
                                "outcome": "unknown", "message": "Request interrupted; reconcile with Naver before any retry."})
                plan.results.append(results[-1])
                break
            meta = response.meta or {}
            entry = {"start_offset": start, "end_offset": end, "status_code": response.status_code,
                     "meta": meta, "failures": response.failures}
            # Cache failure fallback retains the original response for inspection.
            if response.body is not None:
                entry["body"] = response.body
            results.append(entry)
            plan.results.append(entry)
            if (not 200 <= response.status_code < 300 or meta.get("fail_count")
                    or meta.get("cache_error") or meta.get("item_count") != end - start
                    or meta.get("keyword_id_count") != end - start):
                entry["outcome"] = "review_required"
                break
            entry["outcome"] = "response_received"
            plan.next_offset = end
            plan.state = "completed" if end == len(plan.items) else "ready"
            if plan.state == "completed":
                break
        return {"plan_id": plan_id, "state": plan.state, "item_count": len(plan.items),
                "next_offset": plan.next_offset, "batches": results,
                "notice": "Counts describe received responses, not guaranteed advertising success. Inspect saved results; stopped plans cannot be resumed automatically."}
    finally:
        plan.lock.release()


def get_keyword_batch_status(plan_id: str, offset: int = 0) -> dict[str, Any]:
    """Recover progress/result references if the caller lost an execution reply."""
    if offset < 0:
        raise ValueError("offset must be nonnegative")
    plan = _PLANS.get(plan_id)
    if plan is None:
        raise ValueError("Unknown plan; plans expire at server restart")
    if not plan.lock.acquire(blocking=False):
        return {"plan_id": plan_id, "state": "executing", "notice": "Wait for the active call; do not replay it."}
    try:
        page = plan.results[offset:offset + 20]
        end = offset + len(page)
        return {"plan_id": plan_id, "state": plan.state, "item_count": len(plan.items),
                "next_offset": plan.next_offset, "batches": page, "total_batches": len(plan.results),
                "next_result_offset": end if end < len(plan.results) else None}
    finally:
        plan.lock.release()
