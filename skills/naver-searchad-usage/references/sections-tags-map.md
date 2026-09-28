---
title: section과 tag 찾기
description: 공식 JSON 파일 구분과 API 도메인 분류를 이용한 탐색
---

# section과 tag

`section`은 포함된 공식 JSON 명세의 파일 구분이고, `tag`는 캠페인·키워드 등 API 도메인 분류입니다. 정확한 operation 수와 tag 구성은 `list_sections`, `list_tags`로 확인합니다.

| section | 주로 찾는 기능 |
|---|---|
| `ncc-heroes-ncc` | 캠페인, 광고그룹, 키워드, 소재, 타겟팅 |
| `ncc-heroes-tool` | IP 제외 등 도구 |
| `estimate` | 추정 API |
| `ncc-report` | 성과와 보고서 작업 |
| `master-report` | 마스터 보고서 |
| `atower` | 광고·관리 계정 |
| `ncc-heroes-billing` | 비즈머니 |
| `ncc-inspect-history` | 검수 이력 |
| `ncc-keywordstool` | 연관 키워드 |

업무 이름으로 찾을 때는 `list_operations(tag="Campaign")` 같은 tag 필터가 편리합니다. tag가 불확실하면 `search_operations`를 사용합니다. 명세에 항목이 있다고 모든 계정에서 호출할 수 있는 것은 아닙니다.

일부 공식 명세 경로에는 내부용 `/api` 접두사가 있습니다. 클라이언트가 지원하는 section과 경로에 한해 공개 API 경로로 바꾼 뒤 그 경로로 서명합니다. 호출자는 URL이나 메서드를 직접 만들지 않고 `operation_key`를 전달합니다.