---
title: 큰 응답과 임시 저장
description: 자동 저장, 파일명 제한, 저장된 응답의 부분 조회와 보존 범위
---

# 큰 응답 처리

기본 `auto` 모드에서는 응답 본문이 50,000바이트를 초과하면 서버 전용 임시 디렉터리에 자동 저장하고 `body=null`, `meta.saved_to`를 반환합니다. `execute_operation`에 `response_mode="summary"`를 지정하면 작은 결과도 저장합니다. `summary`는 메타데이터와 제한된 실패 미리보기를 반환하는 방식이며, 원본 본문을 모델이 요약해서 대체하지 않습니다. 파일명을 지정하려면 `save_response_to_file="campaigns.json"`처럼 새 JSON 파일명을 전달합니다.

API 응답을 받은 뒤 임시 저장에 실패하면 body를 유지하고 `meta.cache_error`로 알립니다. 이는 네이버의 변경 요청이 실패했다는 뜻이 아닙니다. 반환 결과를 확인하고 같은 쓰기를 다시 실행하지 마세요.

허용되지 않는 입력은 절대 경로, 하위 디렉터리, `..` 경로, 기존 파일 덮어쓰기입니다. 저장 파일은 서버가 관리하며, 같은 프로세스가 생성·등록한 파일만 `read_saved_response`로 읽을 수 있습니다.

```python
# 앞선 실행 응답에서 반환된 실제 경로를 그대로 사용합니다.
read_saved_response(
    path=result["meta"]["saved_to"],
    slice_start=0,
    slice_end=20,
    fields=["nccKeywordId", "keyword", "bidAmt", "status"],
)
```

위 코드는 도구 호출 순서의 예시입니다. `slice_end`는 포함하지 않는 목록 끝 인덱스입니다. 목록은 기본 20개, 최대 100개이고, 선택된 항목 본문은 20,000바이트 이내로 제한됩니다. 크기 제한으로 요청 수보다 적게 반환될 수 있으므로 다음 호출은 실제 `next_offset`을 `slice_start`에 넣습니다.

`only_failures=True`는 실패로 분류한 항목을 **먼저 필터링한 뒤** 페이지를 적용합니다. 이때 `slice_start`와 `next_offset`은 필터 결과 기준이며, `total_items`는 원래 목록 수, `matching_items`는 필터와 일치한 수입니다. 실패 필터와 `fields`를 유지하면서 다음 페이지를 읽으세요.

`fields`에는 필요한 필드만 선택합니다. 객체 안 목록은 `collection_key`로 해당 필드를 지정합니다. 첫 항목 자체가 너무 크면 항목을 건너뛰지 않고 `requires_fields=true`를 반환하므로, 필드를 줄여 같은 위치에서 다시 읽습니다. 큰 객체도 `fields` 또는 `collection_key`가 필요합니다. 문자열 본문은 기본 2,000자, 최대 4,000자씩 조회합니다.

실행 응답의 `failures`는 최대 5개 미리보기입니다. 저장 모드에서는 주요 필드만 미리 보고 긴 필드가 빠질 수 있지만, 전체 실패 항목은 저장된 본문에 보존됩니다. `meta.more_failures`와 `meta.fail_count`를 확인하고 `read_saved_response(only_failures=True)`로 후속 조회합니다. 빈 실패 결과가 업무상 실패가 전혀 없다는 증거는 아닙니다.

저장된 응답에도 `customerId` 마스킹이 적용됩니다. 다른 광고 데이터가 포함될 수 있으므로 공유 파일로 취급하지 마세요. 서버가 정상 종료되면 임시 저장소가 정리됩니다. 재시작하면 이전 파일 조회는 불가능하며, 비정상 종료 시 OS 임시 폴더에 잔여 파일이 남을 수 있습니다. 영구 보관 기능이나 임의 파일 읽기 도구가 아닙니다.
