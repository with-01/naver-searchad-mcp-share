# Claude·Codex·ChatGPT 연결

이 예시는 [README 설치](../README.md#설치)에서 `uv` 설치와 `uvx ... --help` 확인을 마친 상태를 전제로 합니다. 소스 ZIP이나 Git 복제는 필요하지 않습니다. 클라이언트가 `uvx`로 GitHub Release의 Wheel을 자동 다운로드·실행합니다. 네이버 API 키는 각자의 개인 설정에 넣습니다.

Windows와 WSL 중 서버를 실행할 환경 하나를 정하고 그 환경의 `uvx`와 자격증명을 사용합니다. 데스크톱 앱이 `uvx`를 찾지 못하면 Windows PowerShell의 `(Get-Command uvx).Source` 또는 macOS/Linux의 `command -v uvx`로 확인한 절대 경로를 `command`에 넣습니다. JSON의 Windows 경로는 역슬래시를 `\\`로 표기합니다.

## 1. 기본 설정: 본인의 API 키를 로컬 파일에 입력

**1Password 없이 사용할 수 있습니다.** 아래 Claude Desktop·Claude Code·Codex 예제의 `env`에 본인의 네이버 API 키를 평문으로 입력하면 클라이언트가 서버 환경에 전달합니다. 필요한 값은 `NAVER_SEARCHAD_CUSTOMER_ID`, `NAVER_SEARCHAD_ACCESS_LICENSE`, `NAVER_SEARCHAD_SECRET_KEY`입니다.

`examples`의 원본은 placeholder를 유지합니다. 실제 값은 개인 클라이언트 설정 또는 `*.local.json`, `*.local.toml`, `*.local.ps1`처럼 이름을 바꾼 사본에만 넣으세요. 이 로컬 사본과 `.env`는 Git에서 제외하지만, 이미 추적되는 예시 파일에 키를 넣으면 보호되지 않습니다. 키를 채운 파일은 커밋·공유하지 않습니다.

서버는 `.env`를 자동으로 읽지 않습니다. 클라이언트 설정의 `env`나 서버 실행 환경으로 전달해야 합니다. API 키를 ChatGPT·Claude 대화에 붙여 넣을 필요는 없습니다.

## 2. Claude Desktop

Settings → Developer → Edit Config에서 기존 `mcpServers` 객체에 [claude-desktop.json](../examples/claude-desktop.json)의 항목을 합칩니다. `command="uvx"`와 `args`의 Python 버전·Wheel URL·서버 명령을 유지하고 다른 서버 설정도 보존합니다. **개인 컴퓨터의 Claude 설정 파일에서만** `env`의 `YOUR_CUSTOMER_ID`, `YOUR_ACCESS_LICENSE`, `YOUR_SECRET_KEY`를 실제 값으로 바꿉니다. `${VAR}`를 자동 치환한다고 가정하지 마세요.

실제 값은 개인 Claude 설정 파일에 평문으로 저장됩니다. 저장 후 Claude Desktop을 완전히 다시 시작하고 `get_usage_guide`를 호출합니다. [MCP 공식 로컬 서버 연결 안내](https://modelcontextprotocol.io/docs/develop/connect-local-servers)

## 3. Claude Code

[claude-code.json](../examples/claude-code.json)의 내용을 개인 설정 폴더의 `claude-code.local.json`에 저장하고 `env`의 `YOUR_*`를 본인 값으로 바꿉니다. `command="uvx"`와 `args`는 그대로 사용합니다. 아래 PowerShell 명령에서 개인 파일의 경로를 지정해 사용자 범위로 등록합니다.

```powershell
claude mcp add-json --scope user naver-searchad (Get-Content -LiteralPath 'C:\Users\YOUR_NAME\.config\claude-code.local.json' -Raw)
claude mcp get naver-searchad
```

macOS/Linux에서는 다음처럼 등록할 수 있습니다. 필요할 때만 `command`를 `uvx`의 절대 경로로 바꿉니다.

```sh
claude mcp add-json --scope user naver-searchad "$(cat /absolute/path/claude-code.local.json)"
claude mcp get naver-searchad
```

입력한 키는 개인 Claude Code 설정에도 저장됩니다. 프로젝트 공유 설정으로 복사하지 마세요. Claude Code 안에서 `/mcp`로 연결을 확인합니다. 등록 성공은 연결 성공과 다를 수 있습니다. [Claude Code 공식 MCP 문서](https://code.claude.com/docs/en/mcp)

## 4. Codex

개인 `~/.codex/config.toml`에 [codex.toml](../examples/codex.toml)의 항목을 합칩니다. `command="uvx"`와 `args`를 유지하고, `[mcp_servers.naver-searchad.env]`의 `YOUR_*`를 본인 API 키로 바꿉니다. 다른 설정은 보존합니다. 실제 키가 든 설정은 개인 파일에만 보관하고, 프로젝트의 `.codex/config.toml`로 공유하지 마세요.

Codex를 다시 시작한 뒤 `codex mcp list` 또는 `/mcp`로 확인합니다. 이 설정 파일이 ChatGPT 웹에 자동 적용되지는 않습니다. [OpenAI 공식 MCP 문서](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)

## 5. ChatGPT 웹: 개인 Secure MCP Tunnel

각 사용자가 자신의 서버와 Tunnel을 운영합니다. API 키를 넣은 서버 하나를 지인들과 공동 연결하면 그 서버의 광고 계정을 함께 사용하게 되므로 이 배포 방식에서는 공유하지 않습니다.

1. [Platform Tunnel 설정](https://platform.openai.com/settings/organization/tunnels)에서 Tunnel을 만들고 대상 ChatGPT 워크스페이스를 연결합니다. 생성에는 Tunnels Read + Manage, 사용에는 Read + Use 권한이 필요합니다.
2. 같은 화면 또는 [공식 tunnel-client 릴리스](https://github.com/openai/tunnel-client/releases/latest)에서 실행 파일을 준비합니다. `tunnel-client help quickstart`로 해당 버전의 사용법을 확인합니다.
3. 서버 실행 환경에 네이버 변수 3개를 설정합니다. Windows에서는 [server-env.ps1.example](../examples/server-env.ps1.example)을 `server-env.local.ps1`으로 복사해 본인 값을 평문으로 넣고, 같은 PowerShell에서 `. 'C:\absolute\path\server-env.local.ps1'`로 읽을 수 있습니다. Tunnel 실행 환경에는 본인의 `CONTROL_PLANE_API_KEY`도 설정합니다. 별도 비밀 저장소는 필수가 아닙니다.
4. 본인 `tunnel_id`를 넣고 `uvx` 실행 명령으로 stdio 프로필을 만듭니다.

```sh
tunnel-client init --sample sample_mcp_stdio_local --profile naver-searchad --tunnel-id YOUR_TUNNEL_ID --mcp-command "uvx --python 3.12 --from https://github.com/with-01/naver-searchad-mcp-share/releases/download/v0.3.0/naver_searchad_mcp-0.3.0-py3-none-any.whl naver-searchad-mcp"
tunnel-client doctor --profile naver-searchad --explain
tunnel-client run --profile naver-searchad
```

위 명령은 Tunnel 실행 환경에서 `uvx`가 PATH에 있는 경우의 예시입니다. 공식 `--mcp-command`는 실행 명령과 인수를 문자열로 받습니다. 수동 설치를 사용한다면 해당 값에 설치된 서버 실행 명령을 넣어도 됩니다. Tunnel 프로세스가 서버를 실행할 수 있어야 하며, 실행을 유지해야 도구를 사용할 수 있습니다. [OpenAI Secure MCP Tunnel 공식 안내](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)

ChatGPT에서 Settings → Security and login → Developer mode를 켠 뒤, Plugins의 추가 버튼에서 **Connection: Tunnel**을 선택하고 본인의 Tunnel을 연결합니다. 계정·워크스페이스 정책에 따라 메뉴와 권한이 제한될 수 있습니다. 도구 목록을 확인하고 새 대화에서 `get_usage_guide`, `validate_official_spec`부터 실행하세요. [OpenAI 연결·검증 안내](https://developers.openai.com/plugins/deploy/connect-chatgpt)

로컬 HTTP가 필요하면 별도 터미널에서 다음과 같이 시작할 수 있습니다.

```sh
uvx --python 3.12 --from https://github.com/with-01/naver-searchad-mcp-share/releases/download/v0.3.0/naver_searchad_mcp-0.3.0-py3-none-any.whl naver-searchad-mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

주소는 `http://127.0.0.1:8000/mcp`입니다. Tunnel 설정에서 stdio 명령 대신 이 HTTP 주소를 지정할 수 있습니다. 본 서버의 HTTP는 loopback 전용이며 사용자 인증 서버가 아닙니다. 공용 HTTPS로 별도 운영하려면 앞단에 외부 인증 게이트웨이를 구성해야 하며, 인증 없는 포트 포워딩이나 공개 터널로 노출하지 않습니다. 네이버 API 키는 서버 환경에만 두고 ChatGPT의 프롬프트나 MCP 접속용 인증 값으로 보내지 않습니다.

## 6. 쓰기와 첫 연결 점검

모든 예시는 기본 읽기 모드입니다. 쓰기가 필요하면 클라이언트 설정의 **기존 `args` 배열을 유지한 채 마지막 `"naver-searchad-mcp"` 뒤에 `"--allow-writes"`를 추가**하고 재시작합니다. `--python`, `--from`, Wheel URL은 제거하지 마세요. 서버 실행 환경의 `NAVER_SEARCHAD_ALLOW_WRITES=1`도 같은 역할입니다. 각 쓰기 호출은 추가로 `confirm_action="NAVER_SEARCHAD_WRITE"`를 요구합니다.

연결 후 다음 순서로 확인합니다.

1. `get_usage_guide()`와 `validate_official_spec()` — 자격증명 없이 메타데이터 확인.
2. `search_operations("campaign")`, `get_operation_schema(...)` — 사용할 GET 선택.
3. 본인 계정의 GET을 `execute_read_operation`으로 실행 — 실제 네이버 인증 확인.

1번만 성공했다면 API 키나 광고 계정 권한까지 검증된 것은 아닙니다. 로컬 연결, 네이버 연결, ChatGPT/Claude 대화에서의 호출을 구분해서 점검하세요.

## 7. 선택 사항: 기존 1Password 사용자

위 기본 설정에는 1Password가 필요하지 않습니다. 기존에 서버를 수동 설치하고 1Password를 사용한다면 [claude-desktop-1password.json](../examples/claude-desktop-1password.json) 또는 [codex-1password.toml](../examples/codex-1password.toml)의 수동 설치용 경로 예시를 사용할 수 있습니다.

개인 설정 폴더에 [naver-searchad.op.env.example](../examples/naver-searchad.op.env.example)을 복사하고 본인의 vault/item/field 참조로 바꿉니다. 이 **1Password 참조 파일에만** `op://...` 값을 넣습니다. 일반 `env` 설정에는 본인의 실제 API 키를 넣습니다.

```sh
op run --no-masking --env-file /absolute/path/naver-searchad.op.env -- /absolute/path/.venv/bin/naver-searchad-mcp
```

`op run`의 출력 치환이 MCP stdio의 JSON을 변경하지 않도록 `--no-masking`을 사용합니다. 이 옵션은 마스킹을 끄므로 환경변수 값을 출력하지 마세요. [1Password 공식 옵션 설명](https://www.1password.dev/cli/reference/commands/run)
