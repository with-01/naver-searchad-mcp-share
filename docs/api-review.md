# Naver SearchAd API 검토

검토일: 2026-09-28. 실제 광고 계정에 API 요청을 보내지 않았으며, 아래 결과는 공식 자료 대조와 로컬 검증·모의 HTTP 테스트 범위에 해당합니다.

## 공식 자료와 기준 버전

- [사용자가 지정한 공식 가이드](https://naver.github.io/searchad-apidoc/#/guides)
- [가이드·호출 예제의 실제 한국어 원문 JSON](https://github.com/naver/searchad-apidoc/blob/ed3174a5079b2df3230f6a19f0ac8f4dd5f448d8/assets/i18n/markdown-ko-KR.json): `#/guides`, `#/samples` 항목
- [공식 문서 사이트 설정](https://github.com/naver/searchad-apidoc/blob/ed3174a5079b2df3230f6a19f0ac8f4dd5f448d8/app/config.js): 9개 명세 파일과 공개 경로에서 `/api`를 제거하는 규칙
- [광고 관리 명세](https://github.com/naver/searchad-apidoc/blob/ed3174a5079b2df3230f6a19f0ac8f4dd5f448d8/assets/json/ncc-heroes-ncc.json)
- [통계 명세](https://github.com/naver/searchad-apidoc/blob/ed3174a5079b2df3230f6a19f0ac8f4dd5f448d8/assets/json/ncc-report.json)
- [마스터 보고서 명세](https://github.com/naver/searchad-apidoc/blob/ed3174a5079b2df3230f6a19f0ac8f4dd5f448d8/assets/json/master-report.json)
- [공식 Python 서명 구현](https://github.com/naver/searchad-apidoc/blob/0aa7a7650b71c6103a0a6df5100d559415815149/python-sample/examples/signaturehelper.py), [호출 예제](https://github.com/naver/searchad-apidoc/blob/0aa7a7650b71c6103a0a6df5100d559415815149/python-sample/examples/ad_management_sample.py)
- [공식 오류 코드](https://github.com/naver/searchad-apidoc/blob/0aa7a7650b71c6103a0a6df5100d559415815149/NaverSA_API_Error_Code_MAP.md)

배포본의 명세는 `gh-pages` 커밋 `ed3174a5079b2df3230f6a19f0ac8f4dd5f448d8`에 고정했습니다. 서명 예제와 오류 코드는 `master` 커밋 `0aa7a7650b71c6103a0a6df5100d559415815149`에 고정했습니다. `docs/official-spec/SOURCE.json`에는 각 파일의 원본 URL과 SHA-256이 있습니다. 검토 도구는 이 스냅샷과의 일치 여부를 검사하며, 실행할 때마다 최신 공식 자료를 조회하는 기능은 아닙니다.

## 확인하고 수정한 API 문제

| 항목 | 확인된 문제 | 배포본 조치 |
| --- | --- | --- |
| 통계 `fields` | 공식 예제의 JSON 배열 문자열을 문자열 전체의 enum 값으로 잘못 검사하여 정상 요청을 차단 | 단일·복수 개체 통계 모두 JSON 배열 문자열의 각 지표를 검사하고 원래 문자열을 전송 |
| 키워드 수정 `fields` | 원문 enum 안에 붙은 작은따옴표를 전송 값으로 취급하여 정상 `bidAmt` 등을 거부 | 단건·일괄 키워드 수정의 `userLock`, `bidAmt`, `links`, `inspect` 네 값만 공식 설명과 호출 예제에 맞게 보정. 다른 enum은 변경하지 않음 |
| 키워드 일괄 요청 크기 | 공식 설명의 최대 등록 100개·수정 200개 제한이 배열 스키마에는 빠져 있어 초과 요청을 허용 | 해당 두 작업의 유효 스키마에 `maxItems` 반영. 초과 입력은 HTTP 전송 전에 거부 |
| 최신 명세 | 기존 9개 중 3개가 공식 현행 파일과 달랐음 | 공식 파일을 그대로 갱신. 총 126개에서 127개 작업으로 변경 |
| 새 필드·값 | `aiAdsOptIn`, `purchaseRor`, 광고·광고그룹·확장소재의 일부 신규 enum 등이 누락 | 갱신된 정의와 검증에 반영. 마스터 보고서에서 제거된 `Account` 값도 현행 명세 반영 |
| 신규 조회 | 긴 키워드 목록을 본문으로 보내는 ManagedKeyword POST가 누락 | 공식 명세의 새 작업 등록. 현재 쓰기 확인 정책은 HTTP 메서드 기준이므로 이 POST 조회도 확인 대상 |
| 작업 식별자 | 공식 자동 생성 operationId가 17곳에서 변경·재사용됨. 그대로 바꾸면 기존 키가 다른 경로를 가리킬 수 있음 | 기존 공개 `operation_key`의 메서드·경로를 유지하고 `operationId`에는 현재 공식 값을 표시 |
| 모델에 제공되는 스키마 | 요청·응답 스키마에 참조만 있고 실제 객체 정의는 없어 외부 모델이 본문 필드를 확인하기 어려움 | 필요한 중첩 `definitions`를 함께 반환 |
| 설치 후 명세 탐색 | 소스 저장소의 `docs` 경로에 의존 | 패키지에 포함된 `data/official-spec`를 우선 사용 |

기존 126개 `operation_key` 모두 갱신 전과 동일한 HTTP 메서드·경로를 가리키는 것을 비교했습니다. 명세·입력 검증·스냅샷 무결성 관련 회귀 테스트를 통과했습니다. 그 밖의 패키징·보안 테스트 결과는 배포 검증 결과를 함께 확인해야 합니다.

키워드 요청 보정의 근거는 [일괄 수정 설명의 200개 제한](https://github.com/naver/searchad-apidoc/blob/ed3174a5079b2df3230f6a19f0ac8f4dd5f448d8/assets/json/ncc-heroes-ncc.json#L2687), [등록 설명의 100개 제한](https://github.com/naver/searchad-apidoc/blob/ed3174a5079b2df3230f6a19f0ac8f4dd5f448d8/assets/json/ncc-heroes-ncc.json#L2903), [따옴표 없는 `bidAmt`를 보내는 공식 Python 예제](https://github.com/naver/searchad-apidoc/blob/0aa7a7650b71c6103a0a6df5100d559415815149/python-sample/examples/ad_management_sample.py#L130)입니다. 원문 JSON과 `raw` 스키마는 보정하지 않으며, 실제 검증에 쓰는 파라미터 및 `requestBody`에만 반영합니다.

## 인증·호출 규칙

공식 가이드의 서비스 주소는 `https://api.searchad.naver.com`입니다. 라이선스·고객 ID·밀리초 시각·서명을 각각 정해진 `X-*` 헤더에 넣고, 시각·메서드·요청 경로로 HMAC-SHA256 서명을 생성한 뒤 Base64로 인코딩하는 현재 인증 구현은 공식 Python 예제와 일치합니다. 쿼리 문자열은 서명 경로에 포함하지 않는 공식 예제를 따릅니다.

공식 사이트 자체가 명세의 `/api` 접두사를 공개 경로에서 제거합니다. 현재 클라이언트도 해당 경로를 서명과 HTTP 요청 양쪽에서 동일하게 처리합니다.

오류 코드 자료에는 요청 과다를 나타내는 `429`가 있습니다. 확인한 가이드·호출 예제에는 모든 계정에 적용되는 고정 초당 요청 수가 명시되어 있지 않아 임의 수치를 공식 제한으로 기재하지 않았습니다. 쓰기 요청의 자동 재시도는 중복 변경을 일으킬 수 있으므로 실제 완료 여부를 모르는 실패를 무조건 재시도해서는 안 됩니다.

## 남은 검증 범위

- 공식 스키마와 로컬 테스트의 일치는 127개 작업의 실계정 호출 성공을 의미하지 않습니다. 계정 권한, 인증키 유효성, 상품별 제약, 실제 요금·예산 효과는 확인하지 않았습니다.
- `modifyBidWeightUsingPUT`의 `codes`는 공식 원문에서 여전히 `type: ref`이며 배열 원소 타입과 전송 형식이 없습니다. 기존 문자열 배열·CSV 추정 보정을 제거했습니다. `codes`를 지정한 호출은 배열·문자열·숫자 어느 형태든 HTTP 요청 전에 차단하며, 공식 타입이 확인될 때까지 사용을 허용하지 않습니다. 다른 공식 배열 인수가 `multi`라고 해서 이 인수의 형식을 추정하지 않습니다. 명세 검토 결과에도 이 미확인 항목 1건을 표시합니다.
- `reportJobId`의 정수형 보정은 개인 계정의 실사용 값 대신 공식 `ReportJobResponse.properties.reportJobId`의 `integer/int64` 선언을 근거로 설명합니다. 테스트에는 합성 ID만 사용합니다.
- 공식 설명문에만 있는 조건은 일반 스키마 검증이 모두 강제하지 않습니다. 예를 들어 캠페인·확장소재 기간은 한국 자정에 해당하는 UTC 시각 제약이 설명문에 있으므로, 날짜 설정 시 해당 설명을 함께 따라야 합니다.
- 명세 파일 갱신만으로 미래 호환성이 보장되지는 않습니다. 다음 갱신에도 필드·enum뿐 아니라 operationId 재사용과 기존 공개 키의 메서드·경로를 함께 비교해야 합니다.
- 원본 Hermes 설치 및 `/home/with/naver-searchad-mcp`는 변경하지 않았습니다. 검토 테스트에서는 실제 광고 API를 호출하지 않았습니다. GitHub 배포는 이 검토와 별도 단계로 진행합니다.

## 배포 보안 보완

- 광고 변경은 기본 차단이며 운영자의 쓰기 활성화와 호출별 확인 문자열을 함께 요구합니다. 확인 문자열 자체가 사용자 승인 증명은 아닙니다.
- 응답 저장은 서버 전용 임시 폴더의 새 JSON 파일로 제한합니다. 이 프로세스가 생성한 파일만 읽으며, 임의 경로·심볼릭 링크 이탈·덮어쓰기를 차단합니다.
- 업로드는 운영자가 지정한 폴더 안에서만 허용합니다. 사용설명서 조회는 알려진 챕터 이름만 받습니다.
- HTTP 실행은 loopback 주소로 제한하고 Origin 검사를 유지합니다. 계정별 인증과 격리가 필요한 공용 서비스로 배포하지 않습니다.
- API 변경 후 로컬 저장이 실패해도 원래 응답을 보존합니다. 204 또는 JSON이 아닌 본문도 처리하여 완료된 광고 변경을 응답 해석 오류로 오인하지 않도록 했습니다.
- Git 업로드 전 Gitleaks 8.30.1로 배포 파일을 검사했습니다. 비밀값은 발견되지 않았으며, 검사는 비밀정보가 절대로 없다는 보증은 아닙니다.
