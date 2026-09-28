---
title: MCP 도구 빠른 참조
description: API 탐색, 스키마 확인, 실행, 응답 조회와 사용설명서 도구의 역할
---

# MCP 도구 빠른 참조

| 도구 | 역할 |
|---|---|
| `list_sections` | 포함된 공식 JSON 명세의 구분 목록 |
| `list_tags` | 도메인별 tag와 해당 operation 목록 정보 |
| `list_operations(section?, tag?)` | section/tag로 operation 필터 |
| `search_operations(query)` | 이름·설명·경로·tag로 operation 검색 |
| `get_operation_schema(operation_key)` | 요청·응답 스키마와 보정 메타데이터 조회 |
| `validate_official_spec` | 포함된 명세와 내부 등록 목록 정합성 검사 |
| `get_error_code(code)` | 공식 오류 코드 설명 조회 |
| `search_error_codes(message_substring)` | 오류 메시지로 코드 검색 |
| `execute_read_operation` | GET 전용 API 실행 |
| `execute_operation` | API 실행; 기본 GET만 허용, 쓰기는 별도 활성화 필요 |
| `read_saved_response` | 이 프로세스가 저장한 응답 부분 조회 |
| `get_usage_guide(topic?)` | 인덱스 또는 9개 사용설명서 챕터 조회 |

실행 도구의 `operation_key`, `path_params`, `query`를 해당 스키마에 맞춥니다. 본문이 필요한 operation에는 `execute_operation`의 `body`를 사용합니다. 모든 쓰기는 운영자의 시작 설정과 `confirm_action="NAVER_SEARCHAD_WRITE"`가 모두 필요합니다. GET 전용 도구에 POST를 전달하면 실행되지 않습니다.

`save_response_to_file="campaigns.json"`은 서버 임시 저장소 안의 새 파일 이름입니다. 응답의 `meta.saved_to`를 그대로 `read_saved_response(path=...)`에 전달합니다. `slice_start`, `slice_end`, `fields`, `only_failures`로 필요한 부분을 선택합니다.

입력 타입은 네트워크 요청 전에 검사하지만, 스키마 통과가 네이버 업무 규칙 통과를 뜻하지는 않습니다. `get_error_code` 결과만으로 실제 실패 원인을 단정하지 말고 현재 응답과 함께 해석하세요.