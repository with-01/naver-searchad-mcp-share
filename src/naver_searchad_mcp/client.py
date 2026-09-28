from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass, field
import json
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from .auth import NaverSearchAdCredentials, build_headers
from .spec import Operation
from .validation import validate_operation_input

BASE_URL = "https://api.searchad.naver.com"
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
CONFIRM_ACTION = "NAVER_SEARCHAD_WRITE"

# 응답 byte size 가 이 값을 초과하면 자동으로 임시 파일에 저장 후 메타만 반환.
# save_response_to_file 은 서버 응답 캐시 안의 JSON 파일명만 허용.
AUTO_SAVE_THRESHOLD_BYTES = 50_000

# Each server process owns its cache. MCP callers cannot read unrelated files.
_RESPONSE_CACHE = tempfile.TemporaryDirectory(prefix="naver-searchad-")
_SAVED_RESPONSES: set[Path] = set()

# 응답 객체가 실패 상태인지 판단할 때 사용하는 status / inspectStatus 값.
_FAILURE_STATUS_VALUES = {"ERROR", "BLOCKED", "INVALID", "REJECTED", "FAILED"}
_FAILURE_INSPECT_VALUES = {"REJECTED", "BLOCKED"}

# 1Password `op run` can conceal secret-looking values in stdout. Because MCP
# stdio uses stdout for JSON-RPC frames, unquoted conceal markers can corrupt the
# protocol. Redact account identifiers before FastMCP serializes tool results.
_REDACTED = "[REDACTED]"
_SENSITIVE_RESPONSE_KEYS = {"customerId"}

# Some official Swagger exports include an internal gateway prefix (`/api`) while

# Keep validation/spec parity against the official files, but normalize the path
# at request time so the signed URI and actual HTTP request stay identical.
PUBLIC_PATH_SECTION_PREFIXES = {
    "atower": ("/api/ad-accounts", "/api/manager-accounts"),
    "ncc-heroes-billing": ("/api/billing",),
    "ncc-heroes-ncc": ("/api/ncc",),
    "ncc-heroes-tool": ("/api/tool",),
    "ncc-inspect-history": ("/api/ncc",),
    "ncc-report": ("/api/stat-reports", "/api/stats"),
}


class WriteConfirmationRequired(PermissionError):
    pass


class UnsupportedOfficialOperation(RuntimeError):
    pass


@dataclass(frozen=True)
class ApiResponse:
    status_code: int
    headers: dict[str, str]
    body: Any
    meta: dict[str, Any] | None = None
    failures: list[dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "status_code": self.status_code,
            "headers": self.headers,
            "body": self.body,
        }
        if self.meta is not None:
            out["meta"] = self.meta
        if self.failures is not None:
            out["failures"] = self.failures
        return out


class NaverSearchAdClient:
    def __init__(
        self,
        credentials: NaverSearchAdCredentials | None = None,
        *,
        base_url: str = BASE_URL,
        http_client: httpx.Client | None = None,
    ):
        self.credentials = credentials or NaverSearchAdCredentials.from_env()
        self.base_url = base_url.rstrip("/")
        self.http_client = http_client or httpx.Client(timeout=120)
        self._owns_client = http_client is None

    def close(self) -> None:
        if self._owns_client:
            self.http_client.close()

    def execute_operation(
        self,
        operation: Operation,
        *,
        path_params: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        body: Any = None,
        confirm_action: str | None = None,
        save_response_to_file: str | None = None,
    ) -> ApiResponse:
        """공식 op 호출.

        save_response_to_file:
          - None (기본): 응답이 작으면 그대로 본문 노출. 50KB 초과면 자동으로
            임시 파일에 저장하고 본문 자리는 None, meta.saved_to 에 경로.
          - JSON 파일명: 서버 캐시에 저장. body=None, meta.saved_to=서버 경로.
        실패 항목(상태가 ERROR/REJECTED/...) 이 있으면 body 노출 여부와 무관하게
        failures 배열에 풀 본문이 함께 노출되어 클라이언트가 확인 가능.
        """
        if operation.method in WRITE_METHODS and confirm_action != CONFIRM_ACTION:
            raise WriteConfirmationRequired(
                f"{operation.method} {operation.operation_key} requires confirm_action={CONFIRM_ACTION!r}"
            )

        prepared = validate_operation_input(operation, path_params=path_params, query=query, body=body)
        if save_response_to_file is not None:
            _response_target(save_response_to_file)
        request_path = resolve_public_api_path(operation.section, prepared.path)
        is_multipart = _is_multipart(operation)
        headers = build_headers(
            self.credentials,
            method=operation.method,
            uri=request_path,
            content_type=None if is_multipart else "application/json; charset=UTF-8",
        )

        with ExitStack() as stack:
            request_kwargs: dict[str, Any] = {"headers": headers}
            if is_multipart:
                data, files = _prepare_multipart(operation, prepared.body, stack)
                if data:
                    request_kwargs["data"] = data
                if files:
                    request_kwargs["files"] = files
            elif prepared.body is not None:
                request_kwargs["json"] = prepared.body

            serialized_query = _serialize_query_collection_format(operation, prepared.query)
            response = self.http_client.request(
                operation.method,
                self.base_url + request_path,
                params=serialized_query or None,
                **request_kwargs,
            )

        raw_body = _redact_sensitive_response_values(_decode_response_body(response))
        return _build_api_response(
            status_code=response.status_code,
            response_headers=dict(response.headers),
            raw_body=raw_body,
            save_response_to_file=save_response_to_file,
        )


def _redact_sensitive_response_values(value: Any) -> Any:
    """Return response data safe for MCP stdio JSON-RPC serialization."""
    if isinstance(value, dict):
        return {
            key: _REDACTED if key in _SENSITIVE_RESPONSE_KEYS else _redact_sensitive_response_values(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_sensitive_response_values(item) for item in value]
    return value


def resolve_public_api_path(section: str, path: str) -> str:
    """Map official Swagger paths to Naver's public SearchAd API paths.

    Several official Swagger exports carry an internal `/api` gateway prefix,
    but the public service URL (`https://api.searchad.naver.com`) and official
    samples use the same paths without that prefix. This must be applied before
    both signing and sending the request.
    """
    for prefix in PUBLIC_PATH_SECTION_PREFIXES.get(section, ()):  # exact section allowlist only
        if path == prefix or path.startswith(prefix + "/"):
            return path.removeprefix("/api")
    return path


def _is_failure_item(item: Any) -> bool:
    """응답 객체 1개가 실패 상태인지 판단."""
    if not isinstance(item, dict):
        return False
    status = item.get("status")
    inspect = item.get("inspectStatus")
    if isinstance(status, str) and status.upper() in _FAILURE_STATUS_VALUES:
        return True
    if isinstance(inspect, str) and inspect.upper() in _FAILURE_INSPECT_VALUES:
        return True
    return False


def _analyze_response_body(body: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """응답 body 를 분석해 (meta, failures) 반환.

    meta: byte_size, item_count, ok_count, fail_count
    failures: [{"index": int, "item": <원본 객체>}, ...]
    """
    try:
        body_text = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
    except (TypeError, ValueError):
        body_text = str(body)
    byte_size = len(body_text.encode("utf-8"))

    meta: dict[str, Any] = {"byte_size": byte_size}
    failures: list[dict[str, Any]] = []

    if isinstance(body, list):
        meta["item_count"] = len(body)
        ok = 0
        fail = 0
        for idx, item in enumerate(body):
            if _is_failure_item(item):
                fail += 1
                failures.append({"index": idx, "item": item})
            else:
                ok += 1
        meta["ok_count"] = ok
        meta["fail_count"] = fail
    elif isinstance(body, dict):
        meta["item_count"] = 1
        if _is_failure_item(body):
            meta["ok_count"] = 0
            meta["fail_count"] = 1
            failures.append({"index": 0, "item": body})
        else:
            meta["ok_count"] = 1
            meta["fail_count"] = 0
    else:
        meta["item_count"] = None
        meta["ok_count"] = None
        meta["fail_count"] = None

    return meta, failures


def _response_target(filename: str) -> Path:
    """Accept a new JSON filename inside the process-owned cache only."""
    reserved = {"CON", "PRN", "AUX", "NUL"} | {
        prefix + digit for prefix in ("COM", "LPT") for digit in "123456789¹²³"
    }
    if (
        not filename
        or any(ord(char) < 32 or char in '<>:"/\\|?*' for char in filename)
        or filename != filename.strip()
        or filename.split(".", 1)[0].upper() in reserved
        or Path(filename).suffix.lower() != ".json"
    ):
        raise ValueError("save_response_to_file must be a JSON filename, e.g. campaigns.json; paths are not allowed")
    target = Path(_RESPONSE_CACHE.name) / filename
    if target.exists() or target.is_symlink():
        raise FileExistsError("Saved response already exists; choose a new filename")
    return target


def _save_body_to_file(body: Any, save_path: str | None) -> str:
    """Save only inside the private response cache, without overwriting files."""
    if save_path is not None:
        target = _response_target(save_path)
        with target.open("x", encoding="utf-8") as stream:
            json.dump(body, stream, ensure_ascii=False, indent=2)
    else:
        fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=_RESPONSE_CACHE.name)
        target = Path(tmp_path)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(body, stream, ensure_ascii=False, indent=2)
    _SAVED_RESPONSES.add(target)
    return str(target)


def _build_api_response(
    *,
    status_code: int,
    response_headers: dict[str, str],
    raw_body: Any,
    save_response_to_file: str | None,
) -> ApiResponse:
    """raw_body 를 분석해 임계값/사용자 명시 따라 메타 모드 또는 본문 모드로 ApiResponse 생성."""
    meta, failures = _analyze_response_body(raw_body)
    byte_size = meta.get("byte_size", 0)

    explicit_path = bool(save_response_to_file)
    auto_save = (
        save_response_to_file is None
        and isinstance(byte_size, int)
        and byte_size > AUTO_SAVE_THRESHOLD_BYTES
        and status_code < 400
    )
    need_save = explicit_path or auto_save

    body_returned: Any
    if need_save:
        try:
            path = _save_body_to_file(raw_body, save_response_to_file if explicit_path else None)
        except (OSError, ValueError):
            # An API change may already have succeeded. Never hide its result
            # behind a local storage failure that could encourage a duplicate write.
            body_returned = raw_body
            meta["cache_error"] = "Could not save response; full body returned. Do not repeat the API request just to save it."
        else:
            meta["saved_to"] = path
            meta["auto_saved"] = not explicit_path
            body_returned = None
    else:
        body_returned = raw_body
        # 작은 성공 응답 + 실패 0건이면 meta 노출 생략 (기존 응답 형식 유지)
        if not failures:
            meta = None

    return ApiResponse(
        status_code=status_code,
        headers=response_headers,
        body=body_returned,
        meta=meta,
        failures=failures if failures else None,
    )


def read_saved_response(
    path: str,
    *,
    slice_start: int = 0,
    slice_end: int | None = None,
    fields: list[str] | None = None,
    only_failures: bool = False,
) -> dict[str, Any]:
    """저장된 응답 파일에서 일부만 꺼내 반환 (큰 응답 후속 조회).

    list 응답: slice_start/slice_end 로 범위 지정, fields 로 객체에서 일부 필드만,
    only_failures=True 면 실패 항목만 필터.
    dict / str 응답: slice 는 무시되고 fields 만 적용.
    """
    candidate = Path(path)
    if (
        candidate not in _SAVED_RESPONSES
        or candidate.is_symlink()
        or candidate.resolve().parent != Path(_RESPONSE_CACHE.name).resolve()
    ):
        raise PermissionError("Only response files saved by this server process may be read")
    abs_path = str(candidate)
    with candidate.open(encoding="utf-8") as f:
        body = json.load(f)

    if isinstance(body, list):
        total = len(body)
        items = body[slice_start:slice_end]
        if only_failures:
            items = [it for it in items if _is_failure_item(it)]
        if fields:
            items = [
                {k: v for k, v in it.items() if k in fields} if isinstance(it, dict) else it
                for it in items
            ]
        return {
            "path": abs_path,
            "total_items": total,
            "returned_items": len(items),
            "slice_start": slice_start,
            "slice_end": slice_end if slice_end is not None else total,
            "body": items,
        }
    if isinstance(body, dict):
        if fields:
            body = {k: v for k, v in body.items() if k in fields}
        return {"path": abs_path, "body": body}
    return {"path": abs_path, "body": body}


def _decode_response_body(response: httpx.Response) -> Any:
    if not response.content:
        return None
    try:
        return response.json()
    except (ValueError, UnicodeError):
        return response.text


def encode_query_for_display(query: dict[str, Any]) -> str:
    return urlencode(query, doseq=True)


_COLLECTION_SEPARATORS = {
    "csv": ",",
    "ssv": " ",
    "tsv": "\t",
    "pipes": "|",
}


def _serialize_query_collection_format(operation: Operation, query: dict[str, Any]) -> dict[str, Any]:
    """Swagger 2 collectionFormat 에 따라 query array 를 직렬화.

    csv/ssv/tsv/pipes 면 join, 미지정은 Swagger 2 기본값 csv. multi 는 list 유지.
    """
    if not query:
        return query
    out = dict(query)
    for param in operation.parameters:
        if param.get("in") != "query":
            continue
        name = param.get("name")
        if name not in out:
            continue
        value = out[name]
        if not isinstance(value, list):
            continue
        fmt = param.get("collectionFormat", "csv")
        sep = _COLLECTION_SEPARATORS.get(fmt) if fmt else None
        if sep is not None:
            out[name] = sep.join(str(item) for item in value)
        # else: multi → list 유지, httpx 가 ?name=a&name=b 로 직렬화
    return out


def _is_multipart(operation: Operation) -> bool:
    consumes = operation.raw.get("consumes") or []
    return "multipart/form-data" in consumes or any(
        p.get("in") == "formData" or p.get("type") == "file" for p in operation.parameters
    )


def _prepare_multipart(
    operation: Operation,
    body: Any,
    stack: ExitStack,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if body is None:
        body = {}
    if not isinstance(body, dict):
        raise UnsupportedOfficialOperation(f"multipart operation {operation.operation_key} requires object body")

    data: dict[str, Any] = {}
    files: dict[str, Any] = {}
    for param in operation.parameters:
        if param.get("in") != "formData":
            continue
        name = param["name"]
        if name not in body:
            continue
        value = body[name]
        if param.get("type") == "file":
            if not isinstance(value, str):
                raise UnsupportedOfficialOperation(f"multipart file field {name!r} must be a local file path string")
            upload_root = os.environ.get("NAVER_SEARCHAD_UPLOAD_DIR")
            if not upload_root:
                raise PermissionError("File uploads require NAVER_SEARCHAD_UPLOAD_DIR to be configured by the server operator")
            allowed_root = Path(upload_root).expanduser().resolve()
            file_path = Path(value).expanduser().resolve()
            if not file_path.is_relative_to(allowed_root):
                raise PermissionError("Upload file must be inside NAVER_SEARCHAD_UPLOAD_DIR")
            if not file_path.is_file():
                raise UnsupportedOfficialOperation(f"multipart file field {name!r} path does not exist or is not a file")
            fp = stack.enter_context(file_path.open("rb"))
            files[name] = (file_path.name, fp, "application/octet-stream")
        else:
            data[name] = value
    return data, files
