from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
import re
from urllib.parse import quote

from .spec import Operation, SpecRegistryError, get_registry

PATH_PARAM_RE = re.compile(r"\{([^{}?][^{}]*)\}")
QUERY_TEMPLATE_RE = re.compile(r"\{\?([^{}]+)\}")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$"
)
INT32_MIN = -(2 ** 31)
INT32_MAX = 2 ** 31 - 1
INT64_MIN = -(2 ** 63)
INT64_MAX = 2 ** 63 - 1


class ValidationError(ValueError):
    """Raised when MCP input does not match the official Naver schema."""

    def __init__(self, field_path: str, message: str):
        self.field_path = field_path
        self.message = message
        super().__init__(f"{field_path}: {message}")


class AmbiguousOfficialTypeError(ValidationError):
    """Raised when official docs have an ambiguous type such as `type: ref`."""


@dataclass(frozen=True)
class PreparedOperationInput:
    path: str
    query: dict[str, Any]
    body: Any


def validate_operation_input(
    operation: Operation,
    *,
    path_params: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    body: Any = None,
) -> PreparedOperationInput:
    path_params = path_params or {}
    query = query or {}
    if not isinstance(path_params, dict):
        raise ValidationError("path_params", "must be an object")
    if not isinstance(query, dict):
        raise ValidationError("query", "must be an object")

    path = _prepare_path(operation, path_params)
    query_out = _validate_parameters(operation, query)
    body_out = _validate_body(operation, body)
    return PreparedOperationInput(path=path, query=query_out, body=body_out)


def _prepare_path(operation: Operation, path_params: dict[str, Any]) -> str:
    path = _strip_query_template(operation.path)
    official_path_names = {m.group(1) for m in PATH_PARAM_RE.finditer(path)}
    path_param_specs = {p["name"]: p for p in operation.parameters if p.get("in") == "path"}

    for name in official_path_names:
        if name not in path_params:
            raise ValidationError(f"path_params.{name}", "required path parameter is missing")
        spec = path_param_specs.get(name, {"name": name, "type": "string", "required": True})
        value = _validate_schema_value(path_params[name], _parameter_to_schema(spec), f"path_params.{name}")
        path = path.replace("{" + name + "}", _path_value_to_string(value, f"path_params.{name}"))

    extra = set(path_params) - official_path_names
    if extra:
        raise ValidationError("path_params", f"unknown path parameter(s): {sorted(extra)}")
    return path


def _validate_parameters(operation: Operation, query: dict[str, Any]) -> dict[str, Any]:
    query_specs = {p["name"]: p for p in operation.parameters if p.get("in") == "query"}
    query_template_names = set()
    for match in QUERY_TEMPLATE_RE.finditer(operation.path):
        query_template_names.update(part.strip() for part in match.group(1).split(",") if part.strip())

    allowed = set(query_specs) | query_template_names
    unknown = set(query) - allowed
    if unknown:
        raise ValidationError("query", f"unknown query parameter(s): {sorted(unknown)}")

    validated: dict[str, Any] = {}
    for name, spec in query_specs.items():
        if spec.get("required") and name not in query:
            raise ValidationError(f"query.{name}", "required query parameter is missing")
        if name in query:
            validated[name] = _validate_schema_value(query[name], _parameter_to_schema(spec), f"query.{name}")

    # URI-template query params sometimes appear in the path but not in parameters.
    # Treat them as official-but-schema-missing: allow strings only and do not coerce.
    for name in sorted(query_template_names - set(query_specs)):
        if name in query:
            if not isinstance(query[name], str):
                raise ValidationError(f"query.{name}", "official docs omit schema; only string is accepted safely")
            validated[name] = query[name]
    return validated


def _validate_body(operation: Operation, body: Any) -> Any:
    body_params = [p for p in operation.parameters if p.get("in") == "body"]
    form_params = [p for p in operation.parameters if p.get("in") == "formData"]

    if body_params:
        spec = body_params[0]
        if body is None:
            if spec.get("required"):
                raise ValidationError("body", "required request body is missing")
            return None
        return _validate_schema_value(body, spec.get("schema") or spec, "body", operation.section)

    if form_params:
        if body is None:
            if any(p.get("required") for p in form_params):
                raise ValidationError("body", "required formData body is missing")
            return None
        if not isinstance(body, dict):
            raise ValidationError("body", "formData operation body must be an object")
        out: dict[str, Any] = {}
        for spec in form_params:
            name = spec["name"]
            if spec.get("required") and name not in body:
                raise ValidationError(f"body.{name}", "required formData field is missing")
            if name in body:
                out[name] = _validate_schema_value(body[name], _parameter_to_schema(spec), f"body.{name}")
        unknown = set(body) - {p["name"] for p in form_params}
        if unknown:
            raise ValidationError("body", f"unknown formData field(s): {sorted(unknown)}")
        return out

    if body is not None:
        raise ValidationError("body", "operation does not define a request body")
    return None


def _parameter_to_schema(param: dict[str, Any]) -> dict[str, Any]:
    schema = dict(param.get("schema") or {})
    for key in ("type", "format", "items", "enum", "required", "collectionFormat", "x-json-array-item-enum"):
        if key in param and key not in schema:
            schema[key] = param[key]
    return schema


def _validate_schema_value(value: Any, schema: dict[str, Any], field_path: str, section: str | None = None) -> Any:
    schema = _resolve_ref(schema, section) if section else schema
    if not isinstance(schema, dict):
        raise ValidationError(field_path, "official schema is invalid")

    if "$ref" in schema:
        schema = _resolve_ref(schema, section)

    # nullable: type 결정 이전에 None 통과 처리.
    if value is None and schema.get("nullable") is True:
        return None

    # allOf: sub schemas 합쳐서 단일 object schema 로 변환.
    if "allOf" in schema and "type" not in schema and "properties" not in schema:
        schema = _merge_all_of(schema["allOf"], schema, section)

    # oneOf / anyOf: Swagger 2 에선 거의 등장 X. 등장 시 안전하게 차단.
    if "oneOf" in schema or "anyOf" in schema:
        raise AmbiguousOfficialTypeError(
            field_path, "official docs use oneOf/anyOf which is not supported safely"
        )

    typ = schema.get("type")
    if typ == "ref":
        raise AmbiguousOfficialTypeError(field_path, "official docs declare ambiguous type 'ref'; user decision required")
    enum = schema.get("enum")
    if enum is not None and value not in enum:
        raise ValidationError(field_path, f"must be one of official enum values: {enum}")

    if typ is None:
        # Some object definitions omit `type` but have properties.
        if "properties" in schema:
            typ = "object"
        elif "items" in schema:
            typ = "array"
        else:
            # Official schema lacks a type. Do not guess.
            raise AmbiguousOfficialTypeError(field_path, "official docs omit type; user decision required")

    if typ == "string":
        if not isinstance(value, str):
            raise ValidationError(field_path, f"must be string, got {type(value).__name__}")
        _check_string_constraints(value, schema, field_path)
        return value
    if typ == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValidationError(field_path, f"must be integer, got {type(value).__name__}")
        _check_integer_constraints(value, schema, field_path)
        return value
    if typ == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValidationError(field_path, f"must be number, got {type(value).__name__}")
        _check_number_constraints(value, schema, field_path)
        return value
    if typ == "boolean":
        if not isinstance(value, bool):
            raise ValidationError(field_path, f"must be boolean, got {type(value).__name__}")
        return value
    if typ == "array":
        if not isinstance(value, list):
            raise ValidationError(field_path, f"must be array, got {type(value).__name__}")
        _check_array_size(value, schema, field_path)
        item_schema = schema.get("items")
        if item_schema:
            return [_validate_schema_value(item, item_schema, f"{field_path}[{idx}]", section) for idx, item in enumerate(value)]
        return value
    if typ == "object":
        if not isinstance(value, dict):
            raise ValidationError(field_path, f"must be object, got {type(value).__name__}")
        properties = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        for name in required:
            if name not in value:
                raise ValidationError(f"{field_path}.{name}", "required field is missing")
        out = dict(value)
        # default 자동 주입: value 에 없는 property 중 schema 에 default 가 있으면 채움.
        for name, prop_schema in properties.items():
            if name in value:
                continue
            if isinstance(prop_schema, dict) and "default" in prop_schema:
                out[name] = prop_schema["default"]
        unknown = set(value) - set(properties)
        # An object schema with no declared properties (for example JsonNode)
        # is intentionally free-form. Keep structured object schemas strict.
        additional = schema.get("additionalProperties", "properties" not in schema)
        if unknown:
            if additional is True:
                pass  # 임의 field 허용
            elif isinstance(additional, dict):
                # additionalProperties 가 schema 객체 — unknown field 들을 그 schema 로 검증
                for name in unknown:
                    out[name] = _validate_schema_value(
                        value[name], additional, f"{field_path}.{name}", section
                    )
            else:
                raise ValidationError(field_path, f"unknown object field(s): {sorted(unknown)}")
        for name, prop_schema in properties.items():
            if name in value:
                out[name] = _validate_schema_value(value[name], prop_schema, f"{field_path}.{name}", section)
        return out
    if typ == "file":
        # MCP cannot safely validate file binary here. Require string path/identifier only.
        if not isinstance(value, str):
            raise ValidationError(field_path, f"file field must be string path/identifier, got {type(value).__name__}")
        return value

    raise AmbiguousOfficialTypeError(field_path, f"unsupported official type {typ!r}; user decision required")


def _check_string_constraints(value: str, schema: dict[str, Any], field_path: str) -> None:
    """string 의 minLength / maxLength / pattern / format 검증."""
    if "x-json-array-item-enum" in schema:
        try:
            items = json.loads(value)
        except (ValueError, TypeError) as exc:
            raise ValidationError(field_path, "must be a JSON array string of statistic fields") from exc
        allowed = schema["x-json-array-item-enum"]
        if not isinstance(items, list) or not all(isinstance(item, str) and item in allowed for item in items):
            raise ValidationError(field_path, f"must be a JSON array string containing official statistic fields: {allowed}")
    min_len = schema.get("minLength")
    if min_len is not None and len(value) < min_len:
        raise ValidationError(field_path, f"length {len(value)} < minLength {min_len}")
    max_len = schema.get("maxLength")
    if max_len is not None and len(value) > max_len:
        raise ValidationError(field_path, f"length {len(value)} > maxLength {max_len}")
    pattern = schema.get("pattern")
    if pattern is not None:
        try:
            if not re.search(pattern, value):
                raise ValidationError(field_path, f"does not match pattern {pattern!r}")
        except re.error as exc:
            raise ValidationError(field_path, f"official pattern is invalid regex: {exc}") from exc
    fmt = schema.get("format")
    if fmt == "date":
        if not DATE_RE.match(value):
            raise ValidationError(field_path, f"must match date format YYYY-MM-DD, got {value!r}")
    elif fmt == "date-time":
        if not DATETIME_RE.match(value):
            raise ValidationError(field_path, f"must match RFC3339 date-time, got {value!r}")


def _check_integer_constraints(value: int, schema: dict[str, Any], field_path: str) -> None:
    """integer 의 format(int32/int64) / minimum / maximum 검증."""
    fmt = schema.get("format")
    if fmt == "int32" and not (INT32_MIN <= value <= INT32_MAX):
        raise ValidationError(field_path, f"value {value} out of int32 range")
    if fmt == "int64" and not (INT64_MIN <= value <= INT64_MAX):
        raise ValidationError(field_path, f"value {value} out of int64 range")
    minimum = schema.get("minimum")
    if minimum is not None:
        if schema.get("exclusiveMinimum") is True:
            if value <= minimum:
                raise ValidationError(field_path, f"{value} <= exclusiveMinimum {minimum}")
        elif value < minimum:
            raise ValidationError(field_path, f"{value} < minimum {minimum}")
    maximum = schema.get("maximum")
    if maximum is not None:
        if schema.get("exclusiveMaximum") is True:
            if value >= maximum:
                raise ValidationError(field_path, f"{value} >= exclusiveMaximum {maximum}")
        elif value > maximum:
            raise ValidationError(field_path, f"{value} > maximum {maximum}")


def _check_number_constraints(value: float, schema: dict[str, Any], field_path: str) -> None:
    """number 의 minimum / maximum 검증."""
    minimum = schema.get("minimum")
    if minimum is not None:
        if schema.get("exclusiveMinimum") is True:
            if value <= minimum:
                raise ValidationError(field_path, f"{value} <= exclusiveMinimum {minimum}")
        elif value < minimum:
            raise ValidationError(field_path, f"{value} < minimum {minimum}")
    maximum = schema.get("maximum")
    if maximum is not None:
        if schema.get("exclusiveMaximum") is True:
            if value >= maximum:
                raise ValidationError(field_path, f"{value} >= exclusiveMaximum {maximum}")
        elif value > maximum:
            raise ValidationError(field_path, f"{value} > maximum {maximum}")


def _check_array_size(value: list[Any], schema: dict[str, Any], field_path: str) -> None:
    """array 의 minItems / maxItems 검증."""
    lower = schema.get("minItems")
    if lower is not None and len(value) < lower:
        raise ValidationError(field_path, f"length {len(value)} < minItems {lower}")
    upper = schema.get("maxItems")
    if upper is not None and len(value) > upper:
        raise ValidationError(field_path, f"length {len(value)} > maxItems {upper}")


def _merge_all_of(all_of: list[Any], parent: dict[str, Any], section: str | None) -> dict[str, Any]:
    """allOf 의 sub schema 들을 합쳐서 하나의 object schema 로 만든다.

    Swagger 2 에서 allOf 는 거의 inheritance 로만 쓰이므로 properties / required 를 합치는 단순 merge.
    """
    merged_props: dict[str, Any] = {}
    merged_required: list[str] = []
    for sub in all_of:
        if not isinstance(sub, dict):
            continue
        if "$ref" in sub:
            sub = _resolve_ref(sub, section)
        for k, v in (sub.get("properties") or {}).items():
            merged_props[k] = v
        merged_required.extend(sub.get("required") or [])
    merged: dict[str, Any] = {
        "type": "object",
        "properties": merged_props,
        "required": list(dict.fromkeys(merged_required)),
    }
    # parent 의 추가 키 보존 (allOf 옆에 별도 properties 가 있을 수 있음)
    for k, v in parent.items():
        if k == "allOf":
            continue
        if k == "properties" and isinstance(v, dict):
            merged["properties"].update(v)
        elif k == "required" and isinstance(v, list):
            for r in v:
                if r not in merged["required"]:
                    merged["required"].append(r)
        elif k not in merged:
            merged[k] = v
    return merged


def _resolve_ref(schema: dict[str, Any], section: str | None) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not ref:
        return schema
    if not section:
        raise AmbiguousOfficialTypeError("schema", f"cannot resolve {ref} without section")
    if not ref.startswith("#/definitions/"):
        raise AmbiguousOfficialTypeError("schema", f"unsupported official ref format: {ref}")
    name = ref.split("/", 2)[-1]
    doc = get_registry().documents[section]
    definitions = doc.get("definitions") or {}
    if name not in definitions:
        raise SpecRegistryError(f"Official ref not found in {section}: {ref}")
    resolved = dict(definitions[name])
    if "type" not in resolved and "properties" in resolved:
        resolved["type"] = "object"
    return resolved


def _strip_query_template(path: str) -> str:
    return QUERY_TEMPLATE_RE.sub("", path)


def _path_value_to_string(value: Any, field_path: str) -> str:
    if isinstance(value, bool):
        raise ValidationError(field_path, "boolean path values are not supported")
    if not isinstance(value, (str, int)):
        raise ValidationError(field_path, "path value must be string or integer")
    return quote(str(value), safe="")
