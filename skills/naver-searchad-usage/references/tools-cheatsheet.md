---
title: MCP 도구 빠른 참조
description: API 탐색, 스키마 확인, 실행, 응답 조회와 사용설명서 도구의 역할
---

# MCP 도구 빠른 참조

| 도구 | 역할 |
|---|---|
| `list_sections` | 포함된 공식 JSON 명세의 구분 목록 |
| `list_tags` | 도메인별 tag와 해당 operation 목록 정보 |
| `list_operations(section?, tag?, offset=0, limit=25)` | section/tag 필터; 기본 25개, 최대 100개 |
| `search_operations(query, offset=0, limit=25)` | 이름·설명·경로·tag 검색; 같은 페이지 규칙 |
| `get_operation_schema(operation_key, view="input")` | 기본은 입력·제약·참조 정의; `full`은 응답·원본도 포함 |
| `validate_official_spec` | 포함된 명세와 내부 등록 목록 정합성 검사 |
| `get_error_code(code)` | 공식 오류 코드 설명 조회 |
| `search_error_codes(message_substring)` | 오류 메시지로 코드 검색 |
| `execute_read_operation` | GET 전용 API 실행 |
| `execute_operation` | API 실행; 기본 GET만 허용, 쓰기는 별도 활성화 필요 |
| `prepare_keyword_batch(path, operation_key, query)` | 허용된 JSON 파일을 HTTP 호출 없이 검증하고 계획 생성 |
| `execute_keyword_batch(plan_id, sha256, start_offset, confirm_action, max_batches=1)` | 검토한 계획의 다음 범위를 1~10배치 실행 |
| `get_keyword_batch_status(plan_id, offset=0)` | 진행 상태와 결과 참조 조회; 결과 기록 20배치씩 |
| `read_saved_response` | 이 프로세스가 저장한 응답 부분 조회 |
| `get_usage_guide(topic?)` | 인덱스 또는 사용설명서 챕터 조회 |

실행 도구의 `operation_key`, `path_params`, `query`를 해당 스키마에 맞춥니다. 본문이 필요한 operation에는 `execute_operation`의 `body`를 사용합니다. 모든 쓰기는 운영자의 시작 설정과 `confirm_action="NAVER_SEARCHAD_WRITE"`가 모두 필요합니다. GET 전용 도구에 POST를 전달하면 실행되지 않습니다.

목록·검색의 `next_offset`을 다음 호출의 `offset`에 전달합니다. 동일 작업에서 입력 스키마 전체를 반복 조회하지 마세요. `view="full"`은 응답 스키마나 원본을 확인할 때만 사용합니다.

`execute_operation(response_mode="summary")`는 작은 결과도 저장하고 메타데이터를 반환합니다. `auto`가 기본이며 50,000바이트 초과 시 자동 저장합니다. 이 두 옵션과 `save_response_to_file`은 `execute_operation`에만 있고, GET 전용 도구의 인수는 `operation_key`, `path_params`, `query`입니다.

`save_response_to_file="campaigns.json"`은 서버 임시 저장소 안의 새 파일 이름입니다. 응답의 `meta.saved_to`를 그대로 `read_saved_response(path=...)`에 전달합니다. `slice_start`, `slice_end`, `fields`, `only_failures`, `collection_key`로 필요한 부분을 선택합니다. 목록은 실패 필터를 먼저 적용한 뒤 기본 20개, 최대 100개·본문 20,000바이트까지 반환합니다. 다음 페이지는 반환된 `next_offset`을 사용합니다.

대량 계획은 `NAVER_SEARCHAD_INPUT_DIR` 안의 기존 JSON 파일만 읽습니다. 상세 입력과 실행·중단·응답 유실 처리 예시는 `get_usage_guide(topic="bulk-keywords")`를 확인하세요.

입력 타입은 네트워크 요청 전에 검사하지만, 스키마 통과가 네이버 업무 규칙 통과를 뜻하지는 않습니다. `get_error_code` 결과만으로 실제 실패 원인을 단정하지 말고 현재 응답과 함께 해석하세요.
