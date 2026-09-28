from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import json
from pathlib import Path
from typing import Any

HTTP_METHODS = {"get", "post", "put", "delete", "patch"}

SECTION_FILES = {
    "atower": "atower.json",
    "estimate": "estimate.json",
    "master-report": "master-report.json",
    "ncc-heroes-billing": "ncc-heroes-billing.json",
    "ncc-heroes-ncc": "ncc-heroes-ncc.json",
    "ncc-heroes-tool": "ncc-heroes-tool.json",
    "ncc-inspect-history": "ncc-inspect-history.json",
    "ncc-keywordstool": "ncc-keywordstool.json",
    "ncc-report": "ncc-report.json",
}

EXPECTED_ENDPOINT_COUNTS = {
    "atower": 4,
    "estimate": 10,
    "master-report": 5,
    "ncc-heroes-billing": 4,
    "ncc-heroes-ncc": 79,
    "ncc-heroes-tool": 14,
    "ncc-inspect-history": 2,
    "ncc-keywordstool": 1,
    "ncc-report": 8,
}

# The official operation descriptions define these per-request array limits.
KEYWORD_BATCH_LIMITS = {
    "ncc-heroes-ncc:addUsingPOST_4": 100,
    "ncc-heroes-ncc:modifyUsingPUT_9": 200,
}

# Preserve the public keys from the initial snapshot: upstream-generated
# operationIds can change or be reused for a different method/path.
LEGACY_OPERATION_KEYS = {
    ("GET", "/api/ncc/ad-extensions/{adExtensionId}"): "getByIdUsingGET",
    ("GET", "/api/ncc/ad-extensions{?ownerId}"): "getByOwnerIdUsingGET",
    ("GET", "/api/ncc/adgroups/{adgroupId}"): "getUsingGET_16",
    ("PUT", "/api/ncc/adgroups/{adgroupId}"): "modifyUsingPUT_11",
    ("PUT", "/api/ncc/adgroups/{adgroupId}{?fields}"): "modifyUsingPUT_10",
    ("GET", "/api/ncc/adgroups{?ids}"): "getGroupsUsingGET",
    ("GET", "/api/ncc/ads/{adId}"): "getUsingGET_10",
    ("GET", "/api/ncc/ads{?ids}"): "getUsingGET_11",
    ("GET", "/api/ncc/ads{?nccAdgroupId}"): "getByAdgroupIdUsingGET",
    ("GET", "/api/ncc/campaigns/{campaignId}"): "getUsingGET_13",
    ("GET", "/api/ncc/channels"): "getUsingGET_18",
    ("GET", "/api/ncc/channels/{businessChannelId}"): "getUsingGET_17",
    ("GET", "/api/ncc/channels{?channelTp}"): "getUsingGET_20",
    ("GET", "/api/ncc/channels{?ids}"): "getUsingGET_19",
    ("GET", "/api/ncc/keywords/{nccKeywordId}"): "getUsingGET_14",
    ("GET", "/api/ncc/keywords{?nccAdgroupId,baseSearchId,recordSize,selector}"): "getByAdgroupIdUsingGET_1",
    ("GET", "/api/ncc/targets{?ownerId,types}"): "getByOwnerIdUsingGET_1",
}


# 공식 swagger spec 에서 "type: ref" 또는 type 누락으로 차단되는 파라미터에 대한 수동 schema override.
# 공식 spec 사본은 무수정. 로딩 단계에서만 parameters 에 merge 한다.
# 각 항목에 _reason 을 남겨 근거 추적 가능하게 한다.
# 키: (operation_key, in, name)
MANUAL_PARAM_OVERRIDES: dict[tuple[str, str, str], dict[str, Any]] = {
    ("ncc-report:getReportJobByReportJobIdUsingGET", "path", "reportJobId"): {
        "type": "integer",
        "format": "int64",
        "_reason": (
            "Official ncc-report.json #/definitions/ReportJobResponse/properties/reportJobId "
            "declares integer/int64. The GET response references ReportJobResponse."
        ),
    },
    ("ncc-report:deleteReportJobByReportJobIdUsingDELETE", "path", "reportJobId"): {
        "type": "integer",
        "format": "int64",
        "_reason": (
            "Official ncc-report.json #/definitions/ReportJobResponse/properties/reportJobId "
            "declares integer/int64; DELETE identifies the same /stat-reports/{reportJobId} resource."
        ),
    },
}


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def official_spec_dir() -> Path:
    packaged = Path(__file__).resolve().parent / "data" / "official-spec"
    if packaged.is_dir():
        return packaged
    return project_root() / "docs" / "official-spec"


@dataclass(frozen=True)
class Operation:
    section: str
    operation_key: str
    operation_id: str
    method: str
    path: str
    summary: str | None = None
    description: str | None = None
    tags: tuple[str, ...] = ()
    parameters: tuple[dict[str, Any], ...] = ()
    request_body: dict[str, Any] | None = None
    responses: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, include_raw: bool = False) -> dict[str, Any]:
        data = {
            "section": self.section,
            "operation_key": self.operation_key,
            "operationId": self.operation_id,
            "method": self.method,
            "path": self.path,
            "summary": self.summary,
            "description": self.description,
            "tags": list(self.tags),
            "parameters": list(self.parameters),
            "requestBody": self.request_body,
            "responses": self.responses,
        }
        if include_raw:
            data["raw"] = self.raw
        return data


class SpecRegistryError(RuntimeError):
    pass


class OperationNotFound(SpecRegistryError):
    pass


class SpecRegistry:
    def __init__(self, spec_dir: Path | None = None):
        self.spec_dir = spec_dir or official_spec_dir()
        self.documents: dict[str, dict[str, Any]] = {}
        self.operations: dict[str, Operation] = {}
        self._load()

    def _load(self) -> None:
        operation_id_seen: dict[str, int] = {}
        for section, filename in SECTION_FILES.items():
            path = self.spec_dir / filename
            if not path.exists():
                raise SpecRegistryError(f"Missing official spec file: {path}")
            doc = json.loads(path.read_text(encoding="utf-8"))
            self.documents[section] = doc
            for api_path, path_item in (doc.get("paths") or {}).items():
                if not isinstance(path_item, dict):
                    continue
                for method_lower, op_spec in path_item.items():
                    if method_lower.lower() not in HTTP_METHODS:
                        continue
                    if not isinstance(op_spec, dict):
                        raise SpecRegistryError(f"Invalid operation spec for {section} {method_lower} {api_path}")
                    operation_id = op_spec.get("operationId") or op_spec.get("summary")
                    if not operation_id:
                        raise SpecRegistryError(f"Missing operationId for {section} {method_lower.upper()} {api_path}")
                    operation_id_seen[operation_id] = operation_id_seen.get(operation_id, 0) + 1
                    public_id = operation_id
                    if section == "ncc-heroes-ncc":
                        public_id = LEGACY_OPERATION_KEYS.get((method_lower.upper(), api_path), operation_id)
                    operation_key = f"{section}:{public_id}"
                    if operation_key in self.operations:
                        # Same operationId can appear multiple times in a section in old Swagger exports.
                        # Use method+path suffix to disambiguate without losing official operationId.
                        suffix = _stable_suffix(method_lower, api_path)
                        operation_key = f"{section}:{operation_id}:{suffix}"
                    raw_params = op_spec.get("parameters") or []
                    overridden = _apply_manual_param_overrides(operation_key, raw_params)
                    params = tuple(_normalize_parameters(overridden, operation_key))
                    raw_tags = op_spec.get("tags") or []
                    tags = tuple(str(tag) for tag in raw_tags)
                    operation = Operation(
                        section=section,
                        operation_key=operation_key,
                        operation_id=str(operation_id),
                        method=method_lower.upper(),
                        path=str(api_path),
                        summary=op_spec.get("summary"),
                        description=op_spec.get("description"),
                        tags=tags,
                        parameters=params,
                        request_body=_extract_request_body({**op_spec, "parameters": params}),
                        responses=op_spec.get("responses") or {},
                        raw=op_spec,
                    )
                    self.operations[operation_key] = operation

    def list_sections(self) -> list[dict[str, Any]]:
        return [
            {
                "section": section,
                "file": SECTION_FILES[section],
                "title": (self.documents[section].get("info") or {}).get("title"),
                "version": (self.documents[section].get("info") or {}).get("version"),
                "endpoint_count": sum(1 for op in self.operations.values() if op.section == section),
            }
            for section in SECTION_FILES
        ]

    def list_operations(
        self,
        section: str | None = None,
        tag: str | None = None,
    ) -> list[dict[str, Any]]:
        if section is not None and section not in SECTION_FILES:
            raise SpecRegistryError(f"Unknown section: {section}")
        operations = list(self.operations.values())
        if section is not None:
            operations = [op for op in operations if op.section == section]
        if tag is not None:
            operations = [op for op in operations if tag in op.tags]
        operations.sort(key=lambda op: (op.section, op.path, op.method, op.operation_key))
        return [
            {
                "section": op.section,
                "operation_key": op.operation_key,
                "operationId": op.operation_id,
                "method": op.method,
                "path": op.path,
                "summary": op.summary,
                "tags": list(op.tags),
            }
            for op in operations
        ]

    def list_tags(self) -> list[dict[str, Any]]:
        """공식 swagger tags(도메인별 섹터, 예: Campaign/Adgroup/AdKeyword) 목록.

        사용자 25개 공식 섹터 + swagger 에만 있는 추가 tags 모두 포함.
        각 tag 의 ops 수와 소속 section JSON 파일 함께 반환.
        """
        tag_to_ops: dict[str, list[Operation]] = {}
        for op in self.operations.values():
            for tag in op.tags:
                tag_to_ops.setdefault(tag, []).append(op)
        return [
            {
                "tag": tag,
                "operation_count": len(ops),
                "sections": sorted({op.section for op in ops}),
            }
            for tag, ops in sorted(tag_to_ops.items())
        ]

    def search_operations(self, query: str) -> list[dict[str, Any]]:
        """operationId / summary / description / path / tags 부분 문자열 검색.

        대소문자 무시, 빈 query 는 빈 결과.
        """
        if not query or not query.strip():
            return []
        q = query.lower().strip()
        matched: list[Operation] = []
        for op in self.operations.values():
            parts = [
                op.operation_id or "",
                op.summary or "",
                op.description or "",
                op.path,
            ] + list(op.tags)
            haystack = " ".join(parts).lower()
            if q in haystack:
                matched.append(op)
        matched.sort(key=lambda op: (op.section, op.path, op.method, op.operation_key))
        return [
            {
                "section": op.section,
                "operation_key": op.operation_key,
                "operationId": op.operation_id,
                "method": op.method,
                "path": op.path,
                "summary": op.summary,
                "tags": list(op.tags),
            }
            for op in matched
        ]

    def get_operation(self, operation_key: str) -> Operation:
        try:
            return self.operations[operation_key]
        except KeyError as exc:
            raise OperationNotFound(f"Unknown official operation_key: {operation_key}") from exc

    def get_operation_schema(
        self, operation_key: str, include_raw: bool = True, *, view: str = "full"
    ) -> dict[str, Any]:
        if view not in {"input", "full"}:
            raise ValueError("view must be 'input' or 'full'")
        operation = self.get_operation(operation_key)
        result = operation.to_dict(include_raw=include_raw and view == "full")
        if view == "input":
            result.pop("responses")
        definitions = self.documents[operation.section].get("definitions") or {}
        included: dict[str, Any] = {}

        def collect_refs(value: Any) -> None:
            if isinstance(value, dict):
                ref = value.get("$ref", "")
                if isinstance(ref, str) and ref.startswith("#/definitions/"):
                    name = ref[len("#/definitions/"):]
                    if name not in included and name in definitions:
                        included[name] = definitions[name]
                        collect_refs(definitions[name])
                for child in value.values():
                    collect_refs(child)
            elif isinstance(value, list):
                for child in value:
                    collect_refs(child)

        collect_refs(result)
        if included:
            result["definitions"] = included
        return result

    def validate_official_spec(self) -> dict[str, Any]:
        section_counts = {section: 0 for section in SECTION_FILES}
        problems: list[str] = []
        for key, op in self.operations.items():
            section_counts[op.section] += 1
            if not op.method or op.method.lower() not in HTTP_METHODS:
                problems.append(f"{key}: invalid method {op.method}")
            if not op.path.startswith("/"):
                problems.append(f"{key}: path does not start with /: {op.path}")
            if not op.operation_id:
                problems.append(f"{key}: missing operationId")
            for param in op.parameters:
                if "name" not in param:
                    problems.append(f"{key}: parameter missing name")
                if "in" not in param:
                    problems.append(f"{key}: parameter {param.get('name')} missing in")
        for section, expected in EXPECTED_ENDPOINT_COUNTS.items():
            actual = section_counts.get(section, 0)
            if actual != expected:
                problems.append(f"{section}: expected {expected} endpoints, got {actual}")
        return {
            "ok": not problems,
            "total_operations": len(self.operations),
            "section_counts": section_counts,
            "expected_counts": EXPECTED_ENDPOINT_COUNTS,
            "problems": problems,
        }


def _stable_suffix(method: str, path: str) -> str:
    safe = path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
    safe = safe.replace("?", "query_").replace(",", "_").replace("-", "_")
    return f"{method.lower()}_{safe or 'root'}"


def _normalize_parameters(parameters: list[Any], operation_key: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for param in parameters:
        if not isinstance(param, dict):
            raise SpecRegistryError(f"Invalid parameter entry: {param!r}")
        copied = dict(param)
        if operation_key in {
            "ncc-report:getSingleEntityStatUsingGET",
            "ncc-report:getBulkEntityStatUsingGET",
        } and copied.get("in") == "query" and copied.get("name") == "fields":
            # The official description requires a JSON array string. Its enum
            # describes individual metrics, not the entire serialized string.
            copied["x-json-array-item-enum"] = copied.pop("enum")
        if operation_key in {
            "ncc-heroes-ncc:modifyUsingPUT_8",
            "ncc-heroes-ncc:modifyUsingPUT_9",
        } and copied.get("in") == "query" and copied.get("name") == "fields":
            # The descriptions and official Python sample use unquoted field
            # names. These four enum entries incorrectly include quote marks.
            field_names = {f"'{name}'": name for name in ("userLock", "bidAmt", "links", "inspect")}
            copied["enum"] = [field_names.get(value, value) for value in copied.get("enum", [])]
            copied["_manual_override_reason"] = "Official keyword update descriptions and Python example use unquoted fields names."
        if operation_key in KEYWORD_BATCH_LIMITS and copied.get("in") == "body":
            copied["schema"] = {**copied["schema"], "maxItems": KEYWORD_BATCH_LIMITS[operation_key]}
            copied["_manual_override_reason"] = "Maximum array length is stated in the official operation description."
        normalized.append(copied)
    return normalized


def _apply_manual_param_overrides(operation_key: str, parameters: list[Any]) -> list[Any]:
    """공식 spec 의 ambiguous 파라미터에 수동 schema override 를 merge 한다.

    공식 spec 자체는 손대지 않고 메모리상 parameter dict 만 수정한다.
    override 가 없는 op 는 원본 그대로 통과.
    """
    has_any = any(
        (operation_key, p.get("in"), p.get("name")) in MANUAL_PARAM_OVERRIDES
        for p in parameters
        if isinstance(p, dict)
    )
    if not has_any:
        return parameters
    out: list[Any] = []
    for param in parameters:
        if not isinstance(param, dict):
            out.append(param)
            continue
        key = (operation_key, param.get("in"), param.get("name"))
        override = MANUAL_PARAM_OVERRIDES.get(key)
        if override:
            merged = dict(param)
            merged.update({k: v for k, v in override.items() if k != "_reason"})
            merged["_manual_override_reason"] = override.get("_reason", "")
            out.append(merged)
        else:
            out.append(param)
    return out


def _extract_request_body(op_spec: dict[str, Any]) -> dict[str, Any] | None:
    # Official files are Swagger 2 style, where body parameters live in parameters.
    body_params = [p for p in (op_spec.get("parameters") or []) if isinstance(p, dict) and p.get("in") == "body"]
    if body_params:
        return body_params[0].get("schema") or body_params[0]
    return op_spec.get("requestBody")


@lru_cache(maxsize=1)
def get_registry() -> SpecRegistry:
    return SpecRegistry()


def list_sections() -> list[dict[str, Any]]:
    return get_registry().list_sections()


def list_operations(section: str | None = None, tag: str | None = None) -> list[dict[str, Any]]:
    return get_registry().list_operations(section=section, tag=tag)


def list_tags() -> list[dict[str, Any]]:
    return get_registry().list_tags()


def search_operations(query: str) -> list[dict[str, Any]]:
    return get_registry().search_operations(query)


def get_operation_schema(operation_key: str, include_raw: bool = True) -> dict[str, Any]:
    return get_registry().get_operation_schema(operation_key, include_raw=include_raw)


def validate_official_spec() -> dict[str, Any]:
    return get_registry().validate_official_spec()
