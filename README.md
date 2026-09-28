# Naver SearchAd MCP

네이버 검색광고 공식 API를 Claude, Codex, ChatGPT에서 사용할 수 있게 연결하는 Python MCP 서버입니다. **`uvx`가 패키지를 자동으로 내려받아 실행**하며, 각자 자신의 네이버 광고 계정 API 키를 사용합니다. Hermes나 특정 모델에 종속되지 않습니다.

[클라이언트 설정 예시](docs/clients.md) · [GitHub 저장소](https://github.com/with-01/naver-searchad-mcp-share)

GitHub 로그인이나 초대, 소스 ZIP 다운로드, Git 복제는 필요하지 않습니다. 공개 대상은 코드이며 광고 계정이나 API 키는 공유하지 않습니다. 서버는 각자의 컴퓨터에서 실행되며 공동 호스팅 서비스는 제공하지 않습니다.

| 사용 환경 | 연결 방식 |
|---|---|
| Claude Desktop / Claude Code / Codex | 로컬 `stdio` |
| ChatGPT 웹 | 로컬 서버 + OpenAI Secure MCP Tunnel |
| 로컬 HTTP 지원 MCP 클라이언트 | `http://127.0.0.1:8000/mcp` |

ChatGPT 웹 연결에는 해당 계정의 개발자 모드와 Tunnel 권한 설정이 필요합니다. 아래 문서는 연결 절차이며, 각 사용자의 계정에서 실제 연결을 검증해야 합니다. 공개 서버용 OAuth나 사용자별 자격증명 분리 기능은 포함하지 않습니다.

## 설치

1. [uv 공식 설치 안내](https://docs.astral.sh/uv/getting-started/installation/)에 따라 `uv`를 한 번 설치합니다. `uvx`도 함께 제공됩니다. Windows에서는 `winget install --id=astral-sh.uv -e`를 사용할 수 있습니다.
2. 새 터미널에서 아래 명령으로 다운로드와 실행을 확인합니다. API 키 없이 도움말을 확인할 수 있습니다.

```sh
uvx --python 3.12 --from https://github.com/with-01/naver-searchad-mcp-share/releases/download/v0.3.0/naver_searchad_mcp-0.3.0-py3-none-any.whl naver-searchad-mcp --help
```

`uvx`가 GitHub Release의 Wheel과 의존성을 준비해 격리 환경에서 실행합니다. `--python 3.12`는 사용할 Python을 지정하며, 필요한 Python이 없으면 uv의 기본 설정에서 자동으로 내려받습니다. [uv 도구 실행](https://docs.astral.sh/uv/guides/tools/) · [Python 자동 준비](https://docs.astral.sh/uv/guides/install-python/)

3. [Claude·Codex 설정 예시](docs/clients.md)를 개인 설정에 넣고 API 키 세 개를 채웁니다. `command`는 `uvx`, `args`는 예시의 전체 배열을 사용합니다. 처음에는 다운로드 시간이 필요하므로 위 도움말 명령을 먼저 실행해 두세요.

데스크톱 앱이 `uvx`를 찾지 못하면 Windows PowerShell의 `(Get-Command uvx).Source` 또는 macOS/Linux의 `command -v uvx`로 경로를 확인하고, 그 절대 경로를 `command`에 넣습니다. 이 프로젝트는 PyPI에 게시하지 않으며, 예시처럼 **GitHub Wheel URL을 `--from`에 지정**합니다.

## API 키와 실행

[네이버 공식 시작 안내](https://github.com/naver/searchad-apidoc/blob/master/README.md)에 따라 검색광고 API 접근 정보를 준비하고, 서버 프로세스에 다음 환경변수를 전달합니다.

| 환경변수 | 값 |
|---|---|
| `NAVER_SEARCHAD_CUSTOMER_ID` | 본인의 고객 ID |
| `NAVER_SEARCHAD_ACCESS_LICENSE` | 본인의 액세스 라이선스/API 키 |
| `NAVER_SEARCHAD_SECRET_KEY` | 본인의 비밀키 |

**기본 설치는 각자의 API 키를 로컬 클라이언트 설정의 `env`에 평문으로 넣는 방식입니다. 1Password는 필요하지 않습니다.** Claude Desktop·Claude Code·Codex별 예시에서 `YOUR_*`를 본인 값으로 바꾸면 됩니다. 키를 채운 설정은 개인 컴퓨터에만 보관하고, 저장소의 원본 예시는 placeholder 상태로 유지합니다. [클라이언트별 설정 안내](docs/clients.md)

서버는 이 설정으로 전달된 환경변수를 읽으며 `.env`를 자동으로 읽지는 않습니다. ChatGPT 웹 연결에서도 네이버 키는 서버 환경에 설정하고 대화에 입력하지 않습니다. 실제 키, 광고 데이터, 개인 설정은 Git에 올리지 않습니다. 기존 1Password 사용자를 위한 예시는 선택 사항으로 남겨 두었습니다.

기본 실행은 `stdio`이며 광고 변경은 차단됩니다. 광고 등록·수정·삭제가 필요한 경우에만 서버 시작 옵션 `--allow-writes` 또는 환경변수 `NAVER_SEARCHAD_ALLOW_WRITES=1`을 설정합니다. 이후에도 쓰기 요청에는 `confirm_action="NAVER_SEARCHAD_WRITE"`가 필요합니다. 이 문자열은 사용자 로그인이나 승인 증명의 대체물이 아니므로, 클라이언트의 승인 정책도 유지하세요.

## 사용 순서

1. `get_usage_guide()`로 사용설명서를 확인합니다.
2. `search_operations` / `list_operations`로 API를 찾습니다.
3. `get_operation_schema`로 현재 입력 형식과 제약을 확인합니다.
4. GET은 `execute_read_operation`, 변경 요청은 `execute_operation`을 사용합니다.
5. HTTP 상태와 항목별 응답을 확인합니다. 실패 표시가 없다고 작업 성공이 모두 보장되지는 않습니다.

공식 API 명세 사본과 출처는 [docs/official-spec](docs/official-spec)에 포함됩니다. `validate_official_spec`은 포함된 명세의 내부 정합성을 점검하며, 네이버의 현재 서비스 상태나 계정별 API 접근을 보증하지 않습니다.

응답의 `customerId`는 마스킹되며, 큰 응답은 서버 전용 임시 저장소에 보관하고 `read_saved_response`로 나누어 읽습니다. 명시적 저장에는 `campaigns.json` 같은 **파일명만** 허용하며, 임의 경로 접근과 덮어쓰기는 차단됩니다. 이 프로세스가 생성한 파일만 읽을 수 있고, 재시작 후에는 이전 파일을 읽을 수 없습니다. 일반 종료 시 임시 파일이 정리되며 비정상 종료 시 잔여 파일이 남을 수 있습니다. 파일 업로드는 기본 차단이고, 운영자가 `NAVER_SEARCHAD_UPLOAD_DIR`로 허용한 디렉터리 안에서만 가능합니다.

## 대량 키워드와 토큰 사용

수만 개 키워드를 대화에 붙여 넣으면 입력 토큰부터 커집니다. 이미 준비된 JSON 파일을 서버의 `NAVER_SEARCHAD_INPUT_DIR` 폴더에 두고, `prepare_keyword_batch`로 검증한 뒤 사용자 승인 범위 안에서 `execute_keyword_batch`를 호출하세요. 등록은 100개, 입찰가 수정은 200개씩 보내며 한 도구 호출에서 최대 10회 처리합니다. 오류·시간초과·불명확한 응답이 있으면 멈추고 자동 재시도하지 않습니다. 응답이 끊겼다면 `get_keyword_batch_status`로 처리 위치를 먼저 확인합니다. [JSON 예시와 실행 순서](skills/naver-searchad-usage/references/bulk-keywords.md)

작은 API 결과도 `response_mode="summary"`로 보관할 수 있습니다. 실패 미리 보기는 최대 5개이고, 원문은 서버에 남습니다. 저장된 목록 조회는 기본 20개·최대 100개이며 본문은 20KB 이내입니다. `next_offset`과 필요한 `fields`로 이어서 조회하세요. 스키마는 입력 부분만 기본 제공하며 `view="full"`로 전체를 확인합니다.

2만 건 합성 데이터의 도구 JSON을 비교했을 때 입력 토큰 추정은 등록 약 99.6%, 입찰가 수정 약 99.9% 감소했습니다. **이미 만들어진 파일을 재사용한 조건**이며 실제 ChatGPT/Claude 청구량이나 전체 대화 절감률은 아닙니다. [측정 조건과 재현 방법](docs/token-efficiency.md)

응답 저장이 실패하면 body를 보존하고 `meta.cache_error`를 반환합니다. 로컬 저장 실패 때문에 완료된 광고 변경을 다시 실행하지 마세요. 공식 명세의 불명확한 `modifyBidWeightUsingPUT.codes`는 타입을 추측하지 않고 입력 시 차단합니다. [명세 보정 안내](skills/naver-searchad-usage/references/manual-overrides.md)

## 안내 문서

- [Claude·Codex·ChatGPT 연결](docs/clients.md)
- [공개 코드 공유와 업데이트](docs/private-sharing.md)
- [공식 API 검토와 검증 범위](docs/api-review.md)
- [Hermes 설정 예시](docs/hermes-config.md)
- [모델이 읽는 사용설명서](skills/naver-searchad-usage/SKILL.md)

개발용 검증은 `python -m pip install ".[dev]"` 후 `python -m pytest`로 실행합니다. 테스트 통과와 실제 광고 계정에서의 성공은 별도로 확인해야 합니다.

## 선택: 소스로 수동 설치

소스를 수정하거나 수동으로 설치하려면 [소스 ZIP](https://github.com/with-01/naver-searchad-mcp-share/releases/latest/download/naver-searchad-mcp.zip)을 사용합니다. Python 3.11 이상을 준비하고 압축 안의 `naver-searchad-mcp` 폴더에서 다음을 실행합니다.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install .
.\.venv\Scripts\naver-searchad-mcp.exe --help
```

macOS/Linux에서는 `python3 -m venv .venv` 후 `.venv/bin/python -m pip install .`을 실행합니다. 이 방식의 MCP 설정에는 `uvx` 대신 설치된 `.venv`의 `naver-searchad-mcp` 실행 파일 절대 경로와 `args=[]`를 사용합니다. Git으로 관리하려면 `git clone https://github.com/with-01/naver-searchad-mcp-share.git`으로 복제할 수도 있습니다.
