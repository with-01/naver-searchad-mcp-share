---
title: 작업 흐름별 도구 조합
description: 캠페인 조회, 일괄 변경, 보고서, 오류 처리의 기본 순서
---

# 작업 흐름

## 캠페인·광고그룹·키워드 조회

1. `list_operations(tag="Campaign")` 또는 `search_operations("keyword")`로 후보를 찾습니다.
2. `get_operation_schema`의 기본 `view="input"`에서 전체 목록과 특정 ID 조회를 구분합니다. `ids`가 필수인 operation을 전체 조회용으로 쓰지 마세요. 목록·검색의 `next_offset`이 있으면 다음 페이지를 확인합니다.
3. 서버가 반환한 정확한 키와 필요한 query/path 값으로 `execute_read_operation`을 호출합니다.
4. 저장된 큰 응답은 `read_saved_response`로 필요한 필드만 기본 20개씩 나눠 읽습니다. 일부만 읽었다면 보고서에도 범위를 명시합니다.

## 등록·수정·삭제

1. 기존 상태와 변경 대상 ID를 GET으로 확인합니다.
2. 사용자가 승인한 변경 범위를 기준으로 적용할 필드, 금액, 대상 수를 정리합니다. 누락된 필수 정보만 확인합니다.
3. 변경 operation의 스키마에서 필수 필드, enum, 일괄 처리 한도를 확인합니다. 변경할 필요가 없는 필드는 임의로 만들지 않습니다.
4. 쓰기가 활성화된 서버에서 `execute_operation(..., confirm_action="NAVER_SEARCHAD_WRITE")`을 호출합니다.
5. 항목별 결과와 오류를 확인합니다. 통신이 끊겼다면 성공 여부부터 조회하고, 중복 생성 가능성이 있는 요청을 바로 재시도하지 않습니다.
6. 가능한 경우 GET으로 실제 반영 상태를 확인합니다.

계정 잔액 조회가 필요한 예산·집행 검토에는 `list_operations(tag="Bizmoney")`로 적절한 GET을 선택합니다. 모든 변경에 잔액 조회가 필요한 것은 아닙니다.

## 대량 키워드 등록·입찰가 수정

운영자가 `NAVER_SEARCHAD_INPUT_DIR` 안에 JSON 파일을 준비합니다. `prepare_keyword_batch`로 전체 입력을 HTTP 없이 검증하고, 계획 요약을 검토한 뒤 `execute_keyword_batch`로 다음 범위만 실행합니다. 응답을 잃으면 재실행 전에 `get_keyword_batch_status`를 조회합니다. 스키마와 전체 항목을 대화로 반복 전송하지 않습니다. 정확한 파일·도구 입력 예시는 [bulk-keywords](bulk-keywords.md)를 확인하세요.

## 성과 보고서

`list_operations(tag="Stat")` 또는 `list_operations(tag="StatReport")`에서 목적에 맞는 API를 찾습니다. 날짜 범위, 집계 단위, 필드, ID 입력 형태를 스키마 설명으로 확인합니다. 비동기 보고서 생성이 POST이면 기본 읽기 모드에서 차단되므로 같은 쓰기 활성화 절차가 필요합니다.

기간을 나누어 조회할 때 중복·누락을 확인합니다. 클릭률·평균 클릭비용 같은 비율은 필요한 분자와 분모를 합산해서 계산하며, 반환된 비율을 무조건 더하거나 단순 평균하지 않습니다. 누락되거나 조회하지 않은 기간을 0으로 보고하지 마세요.

## 오류

타입 오류는 입력을 고친 뒤 재요청합니다. 네이버 오류는 HTTP 상태, body의 오류 코드·메시지와 `get_error_code`를 함께 확인합니다. 인증 오류를 해결하려고 비밀키 출력이나 공유를 요청하지 않습니다.
