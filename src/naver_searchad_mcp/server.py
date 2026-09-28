from __future__ import annotations

import argparse
import json
import os
from typing import Annotated, Any

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from .client import NaverSearchAdClient, WRITE_METHODS, read_saved_response as _read_saved_response
from .errors import get_error_code as lookup_error_code
from .errors import search_error_codes as lookup_error_messages
from .spec import get_registry
from .usage_guide import get_chapter as _get_usage_chapter

READ_LOCAL = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
READ_API = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=True)
WRITE_API = ToolAnnotations(
    readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True
)
_allow_writes = False

mcp = FastMCP(
    "naver-searchad",
    instructions=(
        "네이버 검색광고 공식 API MCP.\n"
        "list_tags / search_operations → get_operation_schema → execute_read_operation 순으로 조회.\n"
        "모든 API 호출은 공식 operation_key 기반이며 임의 URL 호출은 지원하지 않습니다.\n"
        "조회는 GET 전용 execute_read_operation, 변경은 execute_operation을 사용합니다.\n"
        "변경은 기본 비활성입니다. 운영자가 --allow-writes 또는 "
        "NAVER_SEARCHAD_ALLOW_WRITES=1로 활성화해야 합니다.\n"
        "변경 전 대상 계정, 대상 ID, 변경 값과 비용 영향을 사용자에게 설명하고 승인을 받으세요. "
        "POST/PUT/PATCH/DELETE는 confirm_action='NAVER_SEARCHAD_WRITE'도 필요합니다. "
        "이 문자열은 실수 방지 장치이며 사용자 승인이나 인증을 대신하지 않습니다.\n"
        "자격증명은 서버 환경변수 NAVER_SEARCHAD_CUSTOMER_ID / "
        "NAVER_SEARCHAD_ACCESS_LICENSE / NAVER_SEARCHAD_SECRET_KEY로 설정합니다. "
        "대화나 도구 인수로 비밀키를 받지 마세요.\n"
        "큰 응답은 서버에 보관되며 read_saved_response로 후속 조회합니다. "
        "사용 방법은 get_usage_guide로 확인하세요.\n"
        "API 응답의 status_code, 오류 본문 및 개별 항목 실패를 확인하세요. "
        "저장된 공식 문서의 스냅샷 일치 검증은 현재 운영 API의 동작 보증이 아닙니다."
    ),
    stateless_http=True,
    json_response=True,
)


@mcp.tool(annotations=READ_LOCAL)
def list_sections() -> dict[str, Any]:
    """번들된 공식 Swagger JSON 파일 단위 section 목록. 도메인 분류는 list_tags 사용."""
    return {"sections": get_registry().list_sections()}


@mcp.tool(annotations=READ_LOCAL)
def list_operations(section: str | None = None, tag: str | None = None) -> dict[str, Any]:
    """공식 operation 목록. section(예: ncc-report), tag(예: Campaign)로 필터링."""
    return {"operations": get_registry().list_operations(section=section, tag=tag)}


@mcp.tool(annotations=READ_LOCAL)
def list_tags() -> dict[str, Any]:
    """공식 Swagger의 도메인 tag 목록과 각 tag의 operation 수/소속 section 반환."""
    return {"tags": get_registry().list_tags()}


@mcp.tool(annotations=READ_LOCAL)
def search_operations(query: str) -> dict[str, Any]:
    """operationId/summary/description/path/tags 부분 검색. 예: campaign, 키워드, bid."""
    return {"operations": get_registry().search_operations(query)}


@mcp.tool(annotations=READ_LOCAL)
def get_operation_schema(operation_key: str) -> dict[str, Any]:
    """단일 operation의 parameters/requestBody/responses/raw 및 수동 보정 근거 반환."""
    return get_registry().get_operation_schema(operation_key, include_raw=True)


@mcp.tool(annotations=READ_LOCAL)
def validate_official_spec() -> dict[str, Any]:
    """내부 registry와 번들된 공식 spec 스냅샷의 일치 여부 검증. 실시간 API 검증은 아님."""
    return get_registry().validate_official_spec()


@mcp.tool(annotations=READ_LOCAL)
def get_error_code(code: str) -> dict[str, Any]:
    """네이버 에러 코드(예: 1001)의 공식 한국어/영어 메시지 조회."""
    return lookup_error_code(code)


@mcp.tool(annotations=READ_LOCAL)
def search_error_codes(message_substring: str) -> dict[str, Any]:
    """한국어/영어 오류 메시지 부분 문자열로 공식 에러 코드 역검색."""
    return {"results": lookup_error_messages(message_substring)}


def _execute(
    operation_key: str,
    *,
    path_params: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    body: Any = None,
    confirm_action: str | None = None,
    save_response_to_file: str | None = None,
    read_only: bool = False,
) -> CallToolResult:
    operation = get_registry().get_operation(operation_key)
    if read_only and operation.method != "GET":
        raise ValueError("execute_read_operation accepts GET operations only")
    if operation.method in WRITE_METHODS and not (
        _allow_writes or os.getenv("NAVER_SEARCHAD_ALLOW_WRITES") == "1"
    ):
        raise PermissionError(
            "API writes are disabled. The server operator must enable --allow-writes "
            "or NAVER_SEARCHAD_ALLOW_WRITES=1."
        )
    client = NaverSearchAdClient()
    try:
        response = client.execute_operation(
            operation,
            path_params=path_params,
            query=query,
            body=body,
            confirm_action=confirm_action,
            save_response_to_file=save_response_to_file,
        )
        payload = response.to_dict()
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))],
            structuredContent=payload,
            isError=response.status_code >= 400,
        )
    finally:
        client.close()


@mcp.tool(annotations=READ_API)
def execute_read_operation(
    operation_key: str,
    path_params: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
) -> Annotated[CallToolResult, dict[str, Any]]:
    """GET 전용 검색광고 조회. 먼저 get_operation_schema로 필수 입력을 확인.

    응답은 status_code/headers/body를 포함. 큰 응답은 서버에 저장되며
    meta.saved_to를 read_saved_response에 전달해 필요한 부분을 조회.
    HTTP 오류는 isError=true와 함께 네이버 오류 본문을 반환.
    """
    return _execute(operation_key, path_params=path_params, query=query, read_only=True)


@mcp.tool(annotations=WRITE_API)
def execute_operation(
    operation_key: str,
    path_params: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    body: Any = None,
    confirm_action: str | None = None,
    save_response_to_file: str | None = None,
) -> Annotated[CallToolResult, dict[str, Any]]:
    """공식 operation_key로 API 실행. 광고 변경/삭제 및 비용에 영향을 줄 수 있음.

    서버에서 쓰기가 활성화되어야 POST/PUT/PATCH/DELETE 가능.
    변경 대상/내용을 설명하고 사용자 승인을 받은 후
    confirm_action='NAVER_SEARCHAD_WRITE'를 전달. 조회는 execute_read_operation 권장.
    save_response_to_file은 서버 응답 저장소 내의 새 JSON 파일에만 저장.
    HTTP 오류는 isError=true와 함께 네이버 오류 본문을 반환.
    """
    return _execute(
        operation_key,
        path_params=path_params,
        query=query,
        body=body,
        confirm_action=confirm_action,
        save_response_to_file=save_response_to_file,
    )


@mcp.tool(annotations=READ_LOCAL)
def get_usage_guide(topic: str | None = None) -> dict[str, Any]:
    """번들된 사용설명서 조회. None/index/skill은 목차, 챕터 이름은 해당 본문 반환.

    예: tools-cheatsheet, workflow-patterns, large-response, write-safety.
    모든 MCP 클라이언트에서 이 도구로 같은 안내를 조회할 수 있음.
    """
    return _get_usage_chapter(topic)


@mcp.tool(annotations=READ_LOCAL)
def read_saved_response(
    path: str,
    slice_start: int = 0,
    slice_end: int | None = None,
    fields: list[str] | None = None,
    only_failures: bool = False,
) -> dict[str, Any]:
    """서버가 저장한 응답 조회. meta.saved_to의 경로 사용. 임의 로컬 파일 조회 불가.

    list 응답은 slice_start/slice_end로 범위를 지정하고 fields로 필드를 선택.
    only_failures=true는 실패 상태 항목만 반환. 범위를 좁혀 큰 응답을 나누어 조회.
    """
    return _read_saved_response(
        path, slice_start=slice_start, slice_end=slice_end, fields=fields, only_failures=only_failures
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Naver SearchAd MCP server")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    parser.add_argument("--host", choices=("127.0.0.1", "localhost", "::1"), default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--allow-writes", action="store_true", help="Enable API changes with per-call confirmation")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    global _allow_writes
    _allow_writes = args.allow_writes
    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
