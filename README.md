# Naver SearchAd MCP

네이버 검색광고 공식 API를 Claude, Codex, ChatGPT에서 사용할 수 있게 연결하는 Python MCP 서버입니다. Hermes나 특정 모델에 종속되지 않습니다. 지인별로 설치하고 **각자의 네이버 광고 계정 API 키**를 사용합니다.

| 사용 환경 | 연결 방식 |
|---|---|
| Claude Desktop / Claude Code / Codex | 로컬 `stdio` |
| ChatGPT 웹 | 로컬 서버 + OpenAI Secure MCP Tunnel |
| 로컬 HTTP 지원 MCP 클라이언트 | `http://127.0.0.1:8000/mcp` |

ChatGPT 웹 연결에는 해당 계정의 개발자 모드와 Tunnel 권한 설정이 필요합니다. 아래 문서는 연결 절차이며, 각 사용자의 계정에서 실제 연결을 검증해야 합니다. 공개 서버용 OAuth나 사용자별 자격증명 분리 기능은 포함하지 않습니다.

## 설치

Python 3.11 이상과 Git이 필요합니다. 비공개 GitHub 저장소 초대를 수락한 뒤 복제합니다. GitHub 로그인은 SSH 또는 Git Credential Manager를 사용하고, 토큰을 URL에 넣지 마세요.

```sh
git clone https://github.com/with-01/naver-searchad-mcp-share.git
cd naver-searchad-mcp-share
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\naver-searchad-mcp.exe --help
```

macOS / Linux / WSL:

```sh
.venv/bin/python -m pip install .
.venv/bin/naver-searchad-mcp --help
```

`uv`를 쓰면 `uv venv --python 3.11`과 `uv pip install .`로 대체할 수 있습니다. Wheel 배포본을 받았다면 위 `pip install .` 대신 `pip install /path/to/package.whl`을 사용합니다. 설치 후에는 원본 저장소의 작업 디렉터리에 의존하지 않습니다.

## API 키와 실행

[네이버 공식 시작 안내](https://github.com/naver/searchad-apidoc/blob/master/README.md)에 따라 검색광고 API 접근 정보를 준비하고, 서버 프로세스에 다음 환경변수를 전달합니다.

| 환경변수 | 값 |
|---|---|
| `NAVER_SEARCHAD_CUSTOMER_ID` | 본인의 고객 ID |
| `NAVER_SEARCHAD_ACCESS_LICENSE` | 본인의 액세스 라이선스/API 키 |
| `NAVER_SEARCHAD_SECRET_KEY` | 본인의 비밀키 |

1Password는 선택 사항입니다. 일반 환경변수를 사용해도 됩니다. 서버는 `.env`를 자동으로 읽지 않습니다. 클라이언트별 환경 전달 예시는 [연결 안내](docs/clients.md)에 있습니다. 실제 키, 광고 데이터, 개인 설정은 Git에 올리지 않습니다.

기본 실행은 `stdio`이며 광고 변경은 차단됩니다. 광고 등록·수정·삭제가 필요한 경우에만 서버 시작 옵션 `--allow-writes` 또는 환경변수 `NAVER_SEARCHAD_ALLOW_WRITES=1`을 설정합니다. 이후에도 쓰기 요청에는 `confirm_action="NAVER_SEARCHAD_WRITE"`가 필요합니다. 이 문자열은 사용자 로그인이나 승인 증명의 대체물이 아니므로, 클라이언트의 승인 정책도 유지하세요.

## 사용 순서

1. `get_usage_guide()`로 사용설명서를 확인합니다.
2. `search_operations` / `list_operations`로 API를 찾습니다.
3. `get_operation_schema`로 현재 입력 형식과 제약을 확인합니다.
4. GET은 `execute_read_operation`, 변경 요청은 `execute_operation`을 사용합니다.
5. HTTP 상태와 항목별 응답을 확인합니다. 실패 표시가 없다고 작업 성공이 모두 보장되지는 않습니다.

공식 API 명세 사본과 출처는 [docs/official-spec](docs/official-spec)에 포함됩니다. `validate_official_spec`은 포함된 명세의 내부 정합성을 점검하며, 네이버의 현재 서비스 상태나 계정별 API 접근을 보증하지 않습니다.

응답의 `customerId`는 마스킹되며, 큰 응답은 서버 전용 임시 저장소에 보관하고 `read_saved_response`로 나누어 읽습니다. 명시적 저장에는 `campaigns.json` 같은 **파일명만** 허용하며, 임의 경로 접근과 덮어쓰기는 차단됩니다. 이 프로세스가 생성한 파일만 읽을 수 있고, 재시작 후에는 이전 파일을 읽을 수 없습니다. 일반 종료 시 임시 파일이 정리되며 비정상 종료 시 잔여 파일이 남을 수 있습니다. 파일 업로드는 기본 차단이고, 운영자가 `NAVER_SEARCHAD_UPLOAD_DIR`로 허용한 디렉터리 안에서만 가능합니다.

응답 저장이 실패하면 body를 보존하고 `meta.cache_error`를 반환합니다. 로컬 저장 실패 때문에 완료된 광고 변경을 다시 실행하지 마세요. 공식 명세의 불명확한 `modifyBidWeightUsingPUT.codes`는 타입을 추측하지 않고 입력 시 차단합니다. [명세 보정 안내](skills/naver-searchad-usage/references/manual-overrides.md)

## 안내 문서

- [Claude·Codex·ChatGPT 연결](docs/clients.md)
- [GitHub 비공개 공유와 업데이트](docs/private-sharing.md)
- [공식 API 검토와 검증 범위](docs/api-review.md)
- [Hermes 설정 예시](docs/hermes-config.md)
- [모델이 읽는 사용설명서와 9개 챕터](skills/naver-searchad-usage/SKILL.md)

개발용 검증은 `python -m pip install ".[dev]"` 후 `python -m pytest`로 실행합니다. 테스트 통과와 실제 광고 계정에서의 성공은 별도로 확인해야 합니다.
