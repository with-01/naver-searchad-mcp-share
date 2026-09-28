---
title: 파일로 대량 키워드 등록·입찰가 수정
description: 서버 JSON 파일의 계획 검증, 명시적 배치 실행, 응답 유실 조회와 중단 처리
---

# 파일로 대량 키워드 처리

대량 입력은 MCP 서버에 있는 JSON 파일로 준비하고, 대화에는 파일명·검토 요약·결과 참조만 전달합니다. 2만 개 키워드를 채팅에 붙여 넣거나 모델이 전체 파일을 다시 출력하게 하지 마세요.

## 1. 운영자가 입력 파일 준비

서버 실행 환경의 `NAVER_SEARCHAD_INPUT_DIR`를 입력 허용 폴더의 절대 경로로 설정합니다. 네이버 API 키 3개도 서버 환경에 있어야 합니다. API 파일 업로드용 `NAVER_SEARCHAD_UPLOAD_DIR`와는 별도의 권한입니다.

`prepare_keyword_batch`는 이 폴더 안에 **이미 존재하는** `.json` 파일만 읽습니다. 파일은 UTF-8 JSON 객체 배열이고 비어 있으면 안 됩니다. 최대 크기는 16 MiB입니다. 폴더 밖 경로나 폴더 밖으로 이어지는 링크는 허용되지 않습니다.

원격 ChatGPT는 이 설정만으로 사용자 PC의 파일을 자동으로 읽지 못합니다. 운영자가 서버의 허용 폴더로 파일을 전달해야 합니다. 이 도구는 파일 업로드·파일 생성·임의 로컬 파일 조회 기능을 제공하지 않습니다.

## 2. 지원하는 파일 형식

아래 값과 ID는 **형식 예시**입니다. 입찰가 권장값이 아니며, 실제 계정에서 조회한 ID와 승인받은 값으로 바꿉니다. 작업 전에 해당 operation의 입력 스키마를 한 번 확인합니다.

### 키워드 등록: `keywords-create.json`

```json
[
  {
    "keyword": "예시 키워드 A",
    "bidAmt": 100,
    "useGroupBidAmt": false,
    "userLock": true
  },
  {
    "keyword": "예시 키워드 B",
    "bidAmt": 100,
    "useGroupBidAmt": false,
    "userLock": true
  }
]
```

등록 대상 광고그룹은 아래 query에 지정합니다. `keyword`는 공백뿐인 문자열일 수 없습니다. `userLock`을 포함한 상태 필드도 사용자가 원하는 설정인지 확인합니다.

`prepare_keyword_batch` 도구 인수:

```json
{
  "path": "keywords-create.json",
  "operation_key": "ncc-heroes-ncc:addUsingPOST_4",
  "query": {"nccAdgroupId": "grp-REPLACE_WITH_REAL_ID"}
}
```

### 키워드 입찰가 수정: `keywords-bids.json`

```json
[
  {
    "nccKeywordId": "nkw-REPLACE_WITH_REAL_ID_1",
    "nccAdgroupId": "grp-REPLACE_WITH_REAL_ID",
    "bidAmt": 200,
    "useGroupBidAmt": false
  },
  {
    "nccKeywordId": "nkw-REPLACE_WITH_REAL_ID_2",
    "nccAdgroupId": "grp-REPLACE_WITH_REAL_ID",
    "bidAmt": 200,
    "useGroupBidAmt": false
  }
]
```

수정 파일의 모든 항목은 위 네 필드가 필요하며, `nccKeywordId`는 파일 안에서 중복될 수 없습니다. 이 배치 기능은 입찰가 수정만 지원합니다.

`prepare_keyword_batch` 도구 인수:

```json
{
  "path": "keywords-bids.json",
  "operation_key": "ncc-heroes-ncc:modifyUsingPUT_9",
  "query": {"fields": "bidAmt"}
}
```

수정 query는 정확히 `{"fields":"bidAmt"}`를 사용합니다. 다른 필드 수정·삭제는 이 배치 기능에 포함하지 않습니다. 등록은 공식 한도 **100개**, 입찰가 수정은 **200개**씩 나누어 검증·실행합니다.

## 3. 준비 결과 검토

`prepare_keyword_batch`는 모든 배치의 입력을 검증하지만 **HTTP/API 요청은 보내지 않습니다.** 따라서 인증 정보의 유효성, 실제 계정의 대상 존재 여부, 업무 제약까지 검증된 것은 아닙니다.

반환된 `plan_id`, `sha256`을 보관하고 다음 요약을 검토합니다.

- `account_suffix`: 서버에 설정된 고객 ID의 마지막 네 자리
- `item_count`, `batch_size`, `batch_count`: 총 항목과 호출 단위
- `group_count`, `group_sample`: 대상 광고그룹 요약
- `bid_range`, `use_group_bid_count`, `sample`: 금액·그룹 입찰가 사용·일부 항목

계획은 **계정·operation·query·입력 데이터의 메모리 스냅샷**에 묶이고 `sha256`으로 확인합니다. 준비 이후 원본 파일을 편집해도 이미 만든 계획은 바뀌지 않습니다. 바뀐 파일을 쓰려면 새 계획을 만들고 다시 검토합니다. 이 digest는 사용자 승인이나 로그인 증명을 대신하지 않습니다.

## 4. 승인한 다음 범위만 실행

운영자가 `--allow-writes` 또는 `NAVER_SEARCHAD_ALLOW_WRITES=1`을 활성화하고, 실행 호출에도 `confirm_action="NAVER_SEARCHAD_WRITE"`를 지정해야 합니다. 사용자가 승인한 대상·금액·수량 범위 안에서 실행합니다.

`execute_keyword_batch` 첫 호출 인수:

```json
{
  "plan_id": "REPLACE_WITH_RETURNED_PLAN_ID",
  "sha256": "REPLACE_WITH_RETURNED_SHA256",
  "start_offset": 0,
  "confirm_action": "NAVER_SEARCHAD_WRITE",
  "max_batches": 1
}
```

`max_batches`는 기본 1, 허용 범위 1~10입니다. 한 번의 도구 호출에서 그 수만큼의 API 배치를 순서대로 실행합니다. 10을 지정하면 등록은 최대 1,000개, 입찰가 수정은 최대 2,000개까지 진행하므로 승인 범위와 실행 시간을 고려합니다. 백그라운드 실행이나 남은 전체 작업의 자동 실행은 하지 않습니다.

결과의 `state`가 `ready`이면 다음 호출의 `start_offset`에 **반환된 `next_offset`**을 그대로 넣습니다. 항목 수를 추정해서 증가시키거나 이전 offset을 재사용하지 마세요. `completed`이면 그 계획은 끝났습니다. 실행 시 계정이 준비 당시와 다르거나 digest·offset이 맞지 않으면 차단됩니다.

각 배치 결과는 `summary` 모드로 저장됩니다. `batches[*].meta.saved_to`로 필요한 필드·실패 페이지만 읽습니다. 실패 미리보기는 최대 5개이고, 전체 항목은 저장된 응답에 보존됩니다. 응답 수와 키워드 ID 수가 맞아도 실제 광고 집행·검수 성공을 뜻하지는 않습니다.

## 5. 응답 유실·오류·재시작

실행 응답을 받지 못했다면 **같은 실행을 다시 보내기 전에** `get_keyword_batch_status`를 호출합니다.

```json
{
  "plan_id": "REPLACE_WITH_RETURNED_PLAN_ID",
  "offset": 0
}
```

이 도구는 기록된 배치 결과를 20개씩 반환합니다. `next_result_offset`은 다음 **결과 기록 페이지**를 읽는 `offset`이고, `next_offset`은 다음 **입력 항목 실행 위치**입니다. 두 값을 혼동하지 마세요. `state="executing"`이면 기존 실행이 끝날 때까지 기다립니다.

HTTP 오류, 감지된 항목 실패, 결과 수·키워드 ID 수 불일치, 저장 실패, 통신 중단 등에서는 계획이 `stopped`로 멈추며 자동 재시도하지 않습니다. `outcome="unknown"` 또는 `review_required`가 있으면 저장된 응답과 네이버의 현재 상태를 대조합니다. 중단된 계획을 자동 재개할 수는 없습니다. 확인을 마친 뒤 필요한 미처리 항목만 새 계획으로 준비하고 승인 범위를 다시 확인합니다.

계획과 결과 참조는 **서버 프로세스가 살아 있는 동안만** 유지됩니다. 서버를 재시작하면 status 조회로 이전 실행을 복구할 수 없습니다. 이 경우 네이버 계정에서 실제 반영 여부를 먼저 확인하고, 원본 파일 전체를 다시 실행하지 마세요.
