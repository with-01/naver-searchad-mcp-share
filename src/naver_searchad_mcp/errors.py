from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from .spec import official_spec_dir


@lru_cache(maxsize=1)
def load_error_codes() -> dict[str, dict[str, Any]]:
    path = official_spec_dir() / "NaverSA_API_Error_Code_MAP.md"
    mapping: dict[str, dict[str, Any]] = {}
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("**") or line.startswith("---") or line.startswith("Code|") or line.startswith(":"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3:
            continue
        codes, korean, english = parts[0], parts[1], parts[2]
        for code in [c.strip() for c in codes.split(",") if c.strip()]:
            mapping[code] = {
                "code": code,
                "codes_cell": codes,
                "korean": korean,
                "english": english,
                "official_line": raw,
                "line_no": line_no,
            }
    return mapping


def get_error_code(code: str | int) -> dict[str, Any]:
    key = str(code)
    mapping = load_error_codes()
    if key not in mapping:
        return {"found": False, "code": key}
    return {"found": True, **mapping[key]}


def search_error_codes(message_substring: str) -> list[dict[str, Any]]:
    """에러 메시지(한국어 또는 영어) 부분 문자열로 코드 역검색.

    네이버 응답 본문 메시지에서 어떤 에러 코드인지 찾을 때 사용.
    같은 line 의 codes_cell(예: "1004,1005")은 한 번만 반환한다.
    """
    if not message_substring or not message_substring.strip():
        return []
    q = message_substring.lower().strip()
    mapping = load_error_codes()
    results: list[dict[str, Any]] = []
    seen_lines: set[int] = set()
    for entry in mapping.values():
        line_no = entry.get("line_no")
        if line_no in seen_lines:
            continue
        seen_lines.add(line_no)
        haystack = (entry.get("korean", "") + " " + entry.get("english", "")).lower()
        if q in haystack:
            results.append(entry)
    return results
