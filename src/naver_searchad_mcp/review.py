from __future__ import annotations

from pathlib import Path
import hashlib
import json
from typing import Any

from .client import CONFIRM_ACTION, WRITE_METHODS
from .spec import EXPECTED_ENDPOINT_COUNTS, get_registry, project_root

FORBIDDEN_TRUNCATION_PATTERNS = [
    "truncate(",
    "truncated",
    "max_items",
    "max_results",
    "summarize(",
    "token saving",
    "token-saving",
]


def verify_snapshot_files(spec_dir: Path) -> dict[str, Any]:
    """Check the bundled bytes against the pinned official-source manifest."""
    source = json.loads((spec_dir / "SOURCE.json").read_text(encoding="utf-8"))
    files = source.get("files") or {}
    problems = []
    if not files:
        problems.append("Official source manifest has no file checksums")
    for name, entry in files.items():
        path = spec_dir / name
        if not path.is_file():
            problems.append(f"Missing pinned official file: {name}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            problems.append(f"Official snapshot checksum mismatch: {name}")
    return {"ok": not problems, "verified_files": len(files), "sources": source["official_sources"], "problems": problems}


def run_official_parity_review() -> dict[str, Any]:
    registry = get_registry()
    spec_result = registry.validate_official_spec()
    problems: list[str] = list(spec_result["problems"])
    warnings: list[str] = []
    snapshot = verify_snapshot_files(registry.spec_dir)
    problems.extend(snapshot["problems"])

    # Verify counts explicitly.
    for section, expected in EXPECTED_ENDPOINT_COUNTS.items():
        actual = spec_result["section_counts"].get(section)
        if actual != expected:
            problems.append(f"{section}: endpoint count mismatch expected={expected} actual={actual}")

    # Verify every operation preserves core official fields and has inspectable types.
    ambiguous_types: list[dict[str, str]] = []
    for key, operation in registry.operations.items():
        if not operation.operation_id:
            problems.append(f"{key}: missing official operationId")
        if not operation.path.startswith("/"):
            problems.append(f"{key}: invalid official path {operation.path}")
        if operation.method in WRITE_METHODS and CONFIRM_ACTION != "NAVER_SEARCHAD_WRITE":
            problems.append(f"{key}: write confirmation constant changed")
        for param in operation.parameters:
            name = param.get("name", "<missing>")
            typ = param.get("type") or (param.get("schema") or {}).get("type")
            if param.get("in") != "body" and typ in (None, "ref"):
                ambiguous_types.append(
                    {
                        "operation_key": key,
                        "parameter": name,
                        "in": str(param.get("in")),
                        "type": str(typ),
                        "status": "blocked_until_official_type_is_verified",
                    }
                )

    truncation_hits = scan_for_forbidden_truncation_patterns()
    for hit in truncation_hits:
        problems.append(f"Forbidden truncation/token-saving pattern found: {hit}")

    return {
        "ok": not problems,
        "spec": spec_result,
        "snapshot": snapshot,
        "problems": problems,
        "warnings": warnings,
        "ambiguous_official_types": ambiguous_types,
        "notes": [
            "Parity verifies the bundled pinned snapshot; it does not check the latest upstream release.",
            "Ambiguous official parameter types are intentionally blocked at runtime instead of guessed.",
            "No convenience tools are included in this initial version by user request.",
            "No real POST/PUT/PATCH/DELETE calls were made during review.",
        ],
    }


def scan_for_forbidden_truncation_patterns() -> list[str]:
    root = project_root() / "src" / "naver_searchad_mcp"
    hits: list[str] = []
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), start=1):
            lower = line.lower()
            for pattern in FORBIDDEN_TRUNCATION_PATTERNS:
                if pattern in lower:
                    # Allow this review module to name the forbidden patterns.
                    if path.name == "review.py":
                        continue
                    hits.append(f"{path.relative_to(project_root())}:{lineno}: {line.strip()}")
    return hits


def main() -> None:
    import json
    import sys

    result = run_official_parity_review()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["ok"]:
        sys.exit(1)
