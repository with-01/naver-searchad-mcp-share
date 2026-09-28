---
name: naver-searchad-usage
description: 네이버 검색광고 MCP로 캠페인, 광고그룹, 키워드, 소재, 실적을 조회하거나 변경할 때 사용하는 도구 호출 가이드. 공식 operation 검색, 입력 스키마 확인, 쓰기 권한, 큰 응답 처리와 항목별 결과 점검을 안내한다.
when_to_use: naver-searchad MCP를 이용한 네이버 검색광고 API 작업 시 참조한다.
version: 2.1
---

# Naver SearchAd MCP 사용설명서

어떤 MCP 클라이언트에서도 `get_usage_guide(topic)`로 이 설명서를 읽을 수 있습니다. Claude나 Codex가 저장소의 스킬 파일을 자동으로 설치했다고 가정하지 마세요. 별도 스킬 설치는 MCP 사용의 필수 조건이 아닙니다.

## 기본 흐름

1. `search_operations(query)` 또는 `list_operations(tag=...)`로 대상 API를 찾습니다. 기본 25개씩 반환하므로 `next_offset`이 있으면 다음 페이지를 읽습니다.
2. `get_operation_schema(operation_key)`로 메서드, 필수 입력, 타입, 설명을 확인합니다. 기본 `view="input"`을 사용하고 같은 작업의 스키마는 재사용합니다. 응답·원본 명세가 필요할 때만 `view="full"`을 요청합니다.
3. GET은 `execute_read_operation`, 변경은 `execute_operation`을 사용합니다.
4. HTTP 상태, 원본 항목 상태, 오류 메시지를 확인하고 확인된 결과만 보고합니다.

모든 실행은 서버가 제공한 `operation_key`를 사용합니다. 예전 `_1`, `_2` 접미사나 기억한 enum·입찰가·한도를 그대로 적용하지 마세요. 공식 명세와 계정별 API 제약을 확인합니다.

대량 키워드 등록·입찰가 수정은 서버의 JSON 파일을 `prepare_keyword_batch`로 검증한 뒤 `execute_keyword_batch`로 명시한 범위만 실행합니다. 2만 개 항목을 대화에 붙여 넣거나 도구 인수로 반복 전송하지 마세요. 파일은 운영자가 `NAVER_SEARCHAD_INPUT_DIR` 안에 준비해야 합니다. 원격 ChatGPT 연결만으로 사용자 PC의 파일을 자동으로 읽을 수는 없습니다. [대량 키워드 안내](references/bulk-keywords.md)

## 쓰기와 데이터 경계

- 기본적으로 GET만 실행됩니다. 운영자가 `--allow-writes` 또는 `NAVER_SEARCHAD_ALLOW_WRITES=1`로 활성화해야 변경 요청을 실행할 수 있습니다.
- POST/PUT/PATCH/DELETE에는 `confirm_action="NAVER_SEARCHAD_WRITE"`도 필요합니다. 이 값은 사용자 승인 사실을 증명하지 않습니다. 이미 받은 명확한 변경 지시의 범위 안에서 실행하고, 대상·금액·범위가 불명확하면 먼저 확인하세요.
- 네이버 자격증명은 서버 환경에서 읽습니다. 비밀키를 도구 인수나 대화에 넣지 마세요.
- 응답의 `customerId`는 마스킹됩니다. 다른 광고 데이터가 모두 익명화되는 것은 아닙니다.
- 큰 응답은 임시 저장 후 `meta.saved_to`를 반환합니다. `read_saved_response`는 이 서버 프로세스가 저장한 파일만 읽습니다.
- 저장된 목록은 기본 20개, 최대 100개·본문 20,000바이트 범위에서 읽습니다. 필요한 `fields`를 선택하고 `next_offset`으로 이어 읽습니다. 실패 필터는 페이지 선택 전에 적용됩니다.
- `execute_operation(response_mode="summary")`는 작은 결과도 저장하고 메타데이터를 반환합니다. 실패 미리보기는 최대 5개이며, 전체 항목은 반환된 body 또는 저장된 응답에 보존됩니다.
- `save_response_to_file`에는 `campaigns.json` 같은 파일명만 허용합니다. 폴더·절대 경로·덮어쓰기는 지원하지 않습니다.
- 업로드는 기본 차단이고 `NAVER_SEARCHAD_UPLOAD_DIR`로 허용한 디렉터리만 사용합니다.
- 대량 입력 파일 권한은 별도의 `NAVER_SEARCHAD_INPUT_DIR`로 지정합니다. 계획과 결과 참조는 현재 서버 프로세스에서만 유지됩니다.

## 챕터

| topic | 내용 |
|---|---|
| [tools-cheatsheet](references/tools-cheatsheet.md) | 도구별 역할 |
| [workflow-patterns](references/workflow-patterns.md) | 조회·변경·보고서 흐름 |
| [bulk-keywords](references/bulk-keywords.md) | JSON 파일로 대량 등록·입찰가 수정 |
| [sections-tags-map](references/sections-tags-map.md) | section과 tag 구분 |
| [large-response](references/large-response.md) | 임시 저장과 부분 조회 |
| [write-safety](references/write-safety.md) | 쓰기 권한과 변경 결과 확인 |
| [enums-reference](references/enums-reference.md) | enum·한도 확인 방법 |
| [response-shapes](references/response-shapes.md) | body·meta·failures 해석 |
| [pitfalls](references/pitfalls.md) | 자주 생기는 오류 |
| [manual-overrides](references/manual-overrides.md) | 명세 보정의 근거와 한계 |

`validate_official_spec`은 패키지에 포함된 명세와 내부 등록 목록의 정합성 검사입니다. 실제 API 연결이나 모든 endpoint의 사용 가능성을 검증하지 않습니다.
