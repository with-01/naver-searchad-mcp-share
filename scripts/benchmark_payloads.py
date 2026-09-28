"""Synthetic offline payload comparison against v0.2.0; never calls Naver.

Run from a source checkout after installing the optional measurement dependency:
  python -m pip install tiktoken
  python scripts/benchmark_payloads.py
Counts are one JSON representation with o200k_base, not billed conversation tokens.
"""
from __future__ import annotations

import importlib.util
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import httpx
import tiktoken

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from naver_searchad_mcp import bulk
from naver_searchad_mcp.auth import NaverSearchAdCredentials
from naver_searchad_mcp.client import CONFIRM_ACTION, NaverSearchAdClient, _build_api_response
from naver_searchad_mcp.server import get_operation_schema

logging.getLogger("httpx").setLevel(logging.WARNING)

BASELINE = "ea03195b9db6a34f2e67e2431dc28013d7171a48"
ENCODER = tiktoken.get_encoding("o200k_base")


def tokens(value):
    return len(ENCODER.encode(json.dumps(value, ensure_ascii=False, separators=(",", ":"))))


def measure(old, new):
    return {"before": old, "after": new, "reduction_percent": round((1 - new / old) * 100, 2)}


def main():
    with tempfile.TemporaryDirectory(prefix="searchad-benchmark-") as directory:
        work = Path(directory)
        legacy_path = work / "legacy_client.py"
        legacy_path.write_bytes(subprocess.check_output(
            ["git", "show", f"{BASELINE}:src/naver_searchad_mcp/client.py"], cwd=ROOT,
        ))
        spec = importlib.util.spec_from_file_location("naver_searchad_mcp._legacy_client", legacy_path)
        legacy = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = legacy
        spec.loader.exec_module(legacy)
        os.environ.update({"NAVER_SEARCHAD_INPUT_DIR": directory,
                           "NAVER_SEARCHAD_CUSTOMER_ID": "synthetic-account",
                           "NAVER_SEARCHAD_ACCESS_LICENSE": "synthetic-license",
                           "NAVER_SEARCHAD_SECRET_KEY": "synthetic-secret"})
        report = {"tokenizer": "o200k_base", "items": 20000,
                  "scope": "tool arguments/results, one compact JSON representation; excludes conversation history, schemas and host billing behavior",
                  "baseline_commit": BASELINE}
        for action, operation, query in (
            ("register", bulk.CREATE_KEYWORDS, {"nccAdgroupId": "grp-example"}),
            ("update_bids", bulk.UPDATE_BIDS, {"fields": "bidAmt"}),
        ):
            rows = [{"keyword": f"테스트키워드{i:05d}", "bidAmt": 100, "useGroupBidAmt": False}
                    if action == "register" else
                    {"nccKeywordId": f"nkw-example-{i:05d}", "nccAdgroupId": "grp-example",
                     "bidAmt": 100, "useGroupBidAmt": False} for i in range(20000)]
            filename = f"{action}.json"
            (work / filename).write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            old_input = old_output = 0
            batch_size = bulk.KEYWORD_BATCH_LIMITS[operation]
            for start in range(0, len(rows), batch_size):
                batch = rows[start:start + batch_size]
                old_input += tokens({"operation_key": operation, "query": query, "body": batch,
                                     "confirm_action": CONFIRM_ACTION})
                response_body = [dict(row, nccKeywordId=f"nkw-example-{start+i:05d}", status="ELIGIBLE")
                                 for i, row in enumerate(batch)]
                old_output += tokens(legacy._build_api_response(
                    status_code=200, response_headers={}, raw_body=response_body,
                    save_response_to_file=None).to_dict())
            sent = []

            def handler(request):
                batch = json.loads(request.content)
                start = sum(sent)
                sent.append(len(batch))
                return httpx.Response(200, json=[dict(row, nccKeywordId=f"nkw-example-{start+i:05d}", status="ELIGIBLE")
                                                for i, row in enumerate(batch)])

            prepare_args = {"path": filename, "operation_key": operation, "query": query}
            plan = bulk.prepare_keyword_batch(**prepare_args)
            new_input, new_output = tokens(prepare_args), tokens(plan)
            calls = 1
            with httpx.Client(transport=httpx.MockTransport(handler)) as transport:
                client = NaverSearchAdClient(NaverSearchAdCredentials.from_env(), http_client=transport)
                offset = 0
                while offset < len(rows):
                    args = {"plan_id": plan["plan_id"], "sha256": plan["sha256"], "start_offset": offset,
                            "confirm_action": CONFIRM_ACTION, "max_batches": 10}
                    result = bulk.execute_keyword_batch(**args, client=client)
                    assert result["state"] in {"ready", "completed"}, result
                    new_input += tokens(args)
                    new_output += tokens(result)
                    offset = result["next_offset"]
                    calls += 1
            assert sum(sent) == len(rows) and max(sent) == batch_size
            report[action] = {"input_tokens": measure(old_input, new_input),
                              "output_tokens": measure(old_output, new_output),
                              "mcp_calls": {"before": len(sent), "after": calls}, "http_requests": len(sent)}
        failures = [{"nccKeywordId": f"nkw-{i:05d}", "status": "ERROR", "message": "오류 내용"} for i in range(20000)]
        kwargs = dict(status_code=200, response_headers={}, raw_body=failures, save_response_to_file=None)
        report["failure_response_20000"] = measure(tokens(legacy._build_api_response(**kwargs).to_dict()),
                                                   tokens(_build_api_response(**kwargs).to_dict()))
        report["bid_input_schema"] = measure(tokens(get_operation_schema(bulk.UPDATE_BIDS, view="full")),
                                              tokens(get_operation_schema(bulk.UPDATE_BIDS)))
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
