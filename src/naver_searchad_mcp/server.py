from __future__ import annotations

import argparse
import json
import os
from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import CallToolResult, TextContent, ToolAnnotations

from .client import NaverSearchAdClient, WRITE_METHODS, read_saved_response as _read_saved_response
from . import bulk
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
        "대량 키워드 등록/입찰가 수정은 JSON 파일을 prepare_keyword_batch로 검증하고 "
        "승인한 계획을 execute_keyword_batch로 실행하세요. 전체 파일을 대화로 읽거나 재작성하지 마세요. "
        "동일 작업의 스키마는 재사용하고 결과는 필요한 필드/실패 페이지만 조회하세요. "
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


def _operation_page(operations: list[dict[str, Any]], offset: int, limit: int) -> dict[str, Any]:
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a non-negative integer")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")
    page = operations[offset:offset + limit]
    next_offset = offset + len(page)
    return {
        "operations": page,
        "total": len(operations),
        "returned": len(page),
        "next_offset": next_offset if next_offset < len(operations) else None,
    }


@mcp.tool(annotations=READ_LOCAL)
def list_operations(
    section: str | None = None,
    tag: str | None = None,
    offset: int = 0,
    limit: int = 25,
) -> dict[str, Any]:
    """공식 operation 목록. section/tag 필터, 기본 25개·최대 100개씩 반환.

    필요한 영역만 조회. next_offset이 있으면 offset에 전달해 다음 페이지 조회.
    """
    return _operation_page(get_registry().list_operations(section=section, tag=tag), offset, limit)


@mcp.tool(annotations=READ_LOCAL)
def list_tags() -> dict[str, Any]:
    """공식 Swagger의 도메인 tag 목록과 각 tag의 operation 수/소속 section 반환."""
    return {"tags": get_registry().list_tags()}


@mcp.tool(annotations=READ_LOCAL)
def search_operations(query: str, offset: int = 0, limit: int = 25) -> dict[str, Any]:
    """operationId/summary/description/path/tags 검색. 기본 25개·최대 100개씩 반환.

    예: campaign, 키워드, bid. next_offset을 offset에 전달해 다음 페이지 조회.
    """
    return _operation_page(get_registry().search_operations(query), offset, limit)


@mcp.tool(annotations=READ_LOCAL)
def get_operation_schema(operation_key: str, view: Literal["input", "full"] = "input") -> dict[str, Any]:
    """기본 input은 호출에 필요한 입력·제약·참조 정의만 반환.

    응답 스키마나 원본 명세가 필요할 때 view='full' 사용. 동일 작업의 스키마는 재사용.
    """
    return get_registry().get_operation_schema(operation_key, view=view)


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
    response_mode: str = "auto",
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
            response_mode=response_mode,
        )
        payload = response.to_dict()
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, separators=(",", ":")))],
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
    response_mode: Literal["auto", "summary"] = "auto",
) -> Annotated[CallToolResult, dict[str, Any]]:
    """공식 operation_key로 API 실행. 광고 변경/삭제 및 비용에 영향을 줄 수 있음.

    서버에서 쓰기가 활성화되어야 POST/PUT/PATCH/DELETE 가능.
    변경 대상/내용을 설명하고 사용자 승인을 받은 후
    confirm_action='NAVER_SEARCHAD_WRITE'를 전달. 조회는 execute_read_operation 권장.
    save_response_to_file은 서버 응답 저장소 내의 새 JSON 파일에만 저장.
    response_mode='summary'는 작은 결과도 파일에 보관하고 요약만 반환.
    HTTP 오류는 isError=true와 함께 네이버 오류 본문을 반환.
    """
    return _execute(
        operation_key,
        path_params=path_params,
        query=query,
        body=body,
        confirm_action=confirm_action,
        save_response_to_file=save_response_to_file,
        response_mode=response_mode,
    )


@mcp.tool(annotations=READ_LOCAL)
def prepare_keyword_batch(path: str, operation_key: str, query: dict[str, Any]) -> dict[str, Any]:
    """허용된 서버 폴더의 JSON 배열을 검증해 등록/입찰가 수정 계획 생성. API 호출 없음.

    NAVER_SEARCHAD_INPUT_DIR 설정 필요. 등록: addUsingPOST_4 + nccAdgroupId 쿼리.
    수정: modifyUsingPUT_9 + fields=bidAmt. 전체 operation_key는 ncc-heroes-ncc: 접두사 포함.
    파일 전체를 대화로 출력하지 말고 파일명만 전달. 결과의 범위/금액을 사용자와 확인.
    """
    return bulk.prepare_keyword_batch(path, operation_key, query)


@mcp.tool(annotations=WRITE_API)
def execute_keyword_batch(
    plan_id: str, sha256: str, start_offset: int, confirm_action: str, max_batches: int = 1,
) -> Annotated[CallToolResult, dict[str, Any]]:
    """검토한 파일 계획의 다음 범위만 실행. 등록100/수정200개씩, 기본1회·최대10회.

    사용자 승인과 쓰기 활성화 필요. start_offset은 준비/실행 응답의 next_offset.
    오류·시간초과·불명확한 결과에서 중단하며 재시도하지 않음. 중단 시 네이버 결과를 대조.
    """
    if not (_allow_writes or os.getenv("NAVER_SEARCHAD_ALLOW_WRITES") == "1"):
        raise PermissionError("API writes are disabled. Enable --allow-writes or NAVER_SEARCHAD_ALLOW_WRITES=1.")
    client = NaverSearchAdClient()
    try:
        payload = bulk.execute_keyword_batch(plan_id, sha256, start_offset, confirm_action,
                                             max_batches=max_batches, client=client)
        return CallToolResult(
            content=[TextContent(type="text", text=json.dumps(payload, ensure_ascii=False, separators=(",", ":")))],
            structuredContent=payload, isError=payload["state"] == "stopped",
        )
    finally:
        client.close()


@mcp.tool(annotations=READ_LOCAL)
def get_keyword_batch_status(plan_id: str, offset: int = 0) -> dict[str, Any]:
    """계획 진행상태·저장된 결과 참조 조회. 실행 응답이 끊겨도 재실행 전에 확인. 결과20회씩."""
    return bulk.get_keyword_batch_status(plan_id, offset)


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
    collection_key: str | None = None,
) -> dict[str, Any]:
    """서버가 저장한 응답 조회. meta.saved_to의 경로 사용. 임의 로컬 파일 조회 불가.

    list 응답은 slice_start/slice_end로 범위를 지정하고 fields로 필드를 선택.
    실패 필터 후 페이지 적용. 기본20개, 최대100개/20KB. next_offset으로 계속 조회.
    collection_key는 객체 안의 목록 선택. fields로 필요한 필드만 선택.
    """
    return _read_saved_response(
        path, slice_start=slice_start, slice_end=slice_end, fields=fields, only_failures=only_failures,
        collection_key=collection_key,
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
