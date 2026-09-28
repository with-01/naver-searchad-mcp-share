---
title: 응답 구조 해석
description: status_code, body, meta와 failures를 구분해서 해석하는 방법
---

# 응답 구조

실행 결과의 기본 구조는 `status_code`, `headers`, `body`입니다. 필요하면 `meta`와 `failures`가 추가됩니다.

| 필드 | 해석 |
|---|---|
| `status_code` | 네이버 HTTP 응답 상태; 항목별 성공 판정과 별개 |
| `body` | 디코딩된 응답; `customerId`는 마스킹됨 |
| `meta.byte_size` | 서버가 계산한 응답 본문 크기 |
| `meta.item_count` | 목록 응답의 항목 수 등 메타데이터 |
| `meta.saved_to` | 서버가 저장한 파일의 조회용 경로 |
| `meta.cache_error` | API 응답 이후 로컬 저장 실패; body는 보존됨 |
| `failures` | 서버의 상태값 규칙으로 감지한 실패 항목 |

작은 응답은 body를 직접 읽습니다. 저장된 응답은 `body=null`과 `meta.saved_to`를 반환하므로, 원본 body가 없다고 빈 결과로 판단하지 말고 `read_saved_response`를 호출합니다.

HTTP 204처럼 본문이 없는 응답과 JSON으로 해석되지 않는 본문도 HTTP 상태와 함께 확인합니다. 로컬 저장 오류가 발생했거나 body가 예상 형식이 아니라고 변경 요청을 즉시 재실행하지 마세요.

`ok_count`, `fail_count`, `failures`는 서버가 알아보는 상태값에 따른 보조 분류입니다. `ok_count`가 실제 생성·수정 성공 수와 항상 같지는 않습니다. 실패 코드·메시지 또는 별도 검수 결과가 다른 필드에 있을 수 있습니다.

저장 여부에 관계없이 감지한 실패 항목이 함께 반환될 수 있습니다. 실패 항목도 많으면 응답 크기가 커질 수 있으므로 일정한 토큰 절감률을 보장하지 않습니다.

전달할 결과는 조회한 범위를 밝혀 요약합니다. 비밀키는 반환하거나 출력하지 않고, 광고 계정 데이터도 사용자가 요청한 범위에서만 활용합니다.
