# Claude·Codex·ChatGPT 연결

이 예시는 [README 설치](../README.md#설치)를 완료한 상태를 전제로 합니다. 경로의 `YOUR_NAME`과 설치 위치는 본인 환경에 맞게 바꾸세요. Windows와 WSL 중 클라이언트가 서버를 실행할 환경 하나를 정하고, 그 환경의 Python·실행 파일·자격증명을 사용합니다.

## 1. 자격증명 전달

필수 환경변수는 `NAVER_SEARCHAD_CUSTOMER_ID`, `NAVER_SEARCHAD_ACCESS_LICENSE`, `NAVER_SEARCHAD_SECRET_KEY`입니다. 자신의 광고 계정 정보를 서버 프로세스 환경에 전달합니다. 비밀키를 채팅에 붙여 넣거나 프로젝트 설정 파일에 커밋하지 마세요.

Windows에서 현재 PowerShell 세션에 값을 입력하려면 아래처럼 입력창을 이용할 수 있습니다. 입력한 값은 명령 기록에 직접 남기지 않고, 자식 프로세스에서 사용할 수 있도록 현재 프로세스 환경에만 저장합니다.

```powershell
$names = @('NAVER_SEARCHAD_CUSTOMER_ID', 'NAVER_SEARCHAD_ACCESS_LICENSE', 'NAVER_SEARCHAD_SECRET_KEY')
foreach ($name in $names) {
    $secret = Read-Host $name -AsSecureString
    $plain = [System.Net.NetworkCredential]::new('', $secret).Password
    [Environment]::SetEnvironmentVariable($name, $plain, 'Process')
    $plain = $null
}
```

이후 같은 터미널에서 Claude Code, Codex 또는 서버를 실행합니다. 이미 실행 중인 데스크톱 앱에는 새 환경변수가 자동 전달되지 않으며, 앱마다 환경 상속 방식이 다를 수 있습니다. Claude Desktop은 아래의 명시적 `env` 설정 또는 1Password 방식을 사용합니다. 서버는 `.env` 파일을 자동 로드하지 않습니다.

### 선택: 1Password

개인 설정 폴더에 [naver-searchad.op.env.example](../examples/naver-searchad.op.env.example)을 복사하고 본인의 vault/item/field **참조**로 바꿉니다. 평문 키를 넣지 않습니다.

```sh
op run --no-masking --env-file /absolute/path/naver-searchad.op.env -- /absolute/path/.venv/bin/naver-searchad-mcp
```

`op run`은 기본적으로 stdout/stderr의 비밀값을 치환합니다. MCP stdio의 JSON이 변경되는 것을 막기 위해 `--no-masking`을 사용합니다. 이 옵션은 출력 마스킹을 끄므로 로그나 명령으로 환경변수를 출력하지 마세요. [1Password 공식 옵션 설명](https://www.1password.dev/cli/reference/commands/run)

## 2. Claude Desktop

Settings → Developer → Edit Config에서 기존 `mcpServers` 객체에 [claude-desktop.json](../examples/claude-desktop.json)의 항목을 합칩니다. 다른 서버 설정은 보존합니다. macOS/Linux에서는 실행 파일 경로를 `.venv/bin/naver-searchad-mcp`로 바꿉니다. **개인 컴퓨터의 Claude 설정 파일에서만** `env`의 `YOUR_CUSTOMER_ID`, `YOUR_ACCESS_LICENSE`, `YOUR_SECRET_KEY`를 실제 값으로 바꿉니다. `${VAR}`를 자동 치환한다고 가정하지 마세요.

이 방식은 실제 값이 개인 Claude 설정 파일에 평문으로 저장됩니다. 그 파일을 커밋하거나 지인에게 전달하지 말고, 저장소의 예시에는 placeholder를 그대로 유지합니다. 평문 설정을 피하려면 다음 1Password 방식을 사용하세요.

1Password 사용자는 [claude-desktop-1password.json](../examples/claude-desktop-1password.json)의 절대 경로를 수정해 사용할 수 있습니다. 저장 후 Claude Desktop을 완전히 다시 시작하고 `get_usage_guide`를 호출합니다. [MCP 공식 로컬 서버 연결 안내](https://modelcontextprotocol.io/docs/develop/connect-local-servers)

## 3. Claude Code

자격증명을 전달한 터미널에서 등록합니다. 아래는 Windows 예시입니다.

```powershell
claude mcp add --transport stdio --scope user naver-searchad -- 'C:\Users\YOUR_NAME\naver-searchad-mcp-share\.venv\Scripts\naver-searchad-mcp.exe'
claude mcp get naver-searchad
```

macOS/Linux에서는 마지막 인수를 설치된 실행 파일의 절대 경로로 바꾸세요. 1Password를 쓴다면 `--` 뒤에 `op run --no-masking --env-file ... -- ...` 실행 명령을 넣습니다. Claude Code 안에서 `/mcp`로 연결을 확인합니다. 등록 성공은 연결 성공과 다를 수 있습니다. [Claude Code 공식 MCP 문서](https://code.claude.com/docs/en/mcp)

## 4. Codex

개인 `~/.codex/config.toml`에 [codex.toml](../examples/codex.toml)의 항목을 합칩니다. `command`는 설치된 실행 파일의 절대 경로이고, `env_vars`는 Codex 환경에서 전달할 변수명입니다. 1Password 사용자는 [codex-1password.toml](../examples/codex-1password.toml)을 사용합니다.

Codex를 다시 시작한 뒤 `codex mcp list` 또는 `/mcp`로 확인합니다. 이 설정 파일이 ChatGPT 웹에 자동 적용되지는 않습니다. [OpenAI 공식 MCP 문서](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)

## 5. ChatGPT 웹: 개인 Secure MCP Tunnel

각 사용자가 자신의 서버와 Tunnel을 운영합니다. API 키를 넣은 서버 하나를 지인들과 공동 연결하면 그 서버의 광고 계정을 함께 사용하게 되므로 이 배포 방식에서는 공유하지 않습니다.

1. [Platform Tunnel 설정](https://platform.openai.com/settings/organization/tunnels)에서 Tunnel을 만들고 대상 ChatGPT 워크스페이스를 연결합니다. 생성에는 Tunnels Read + Manage, 사용에는 Read + Use 권한이 필요합니다.
2. 같은 화면 또는 [공식 tunnel-client 릴리스](https://github.com/openai/tunnel-client/releases/latest)에서 실행 파일을 준비합니다. `tunnel-client help quickstart`로 해당 버전의 사용법을 확인합니다.
3. 서버 환경에 네이버 변수 3개, Tunnel 실행 환경에 `CONTROL_PLANE_API_KEY`를 비밀 저장소로 전달합니다. 키를 아래 명령에 직접 넣지 않습니다.
4. 설치된 서버의 경로와 본인 `tunnel_id`를 넣어 stdio 프로필을 만듭니다.

```sh
tunnel-client init --sample sample_mcp_stdio_local --profile naver-searchad --tunnel-id YOUR_TUNNEL_ID --mcp-command "naver-searchad-mcp"
tunnel-client doctor --profile naver-searchad --explain
tunnel-client run --profile naver-searchad
```

위 명령은 가상환경을 활성화해 `naver-searchad-mcp`가 PATH에 있는 상태의 예시입니다. Tunnel 프로세스가 서버를 실행할 수 있어야 하며, 실행을 유지해야 도구를 사용할 수 있습니다. [OpenAI Secure MCP Tunnel 공식 안내](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)

ChatGPT에서 Settings → Security and login → Developer mode를 켠 뒤, Plugins의 추가 버튼에서 **Connection: Tunnel**을 선택하고 본인의 Tunnel을 연결합니다. 계정·워크스페이스 정책에 따라 메뉴와 권한이 제한될 수 있습니다. 도구 목록을 확인하고 새 대화에서 `get_usage_guide`, `validate_official_spec`부터 실행하세요. [OpenAI 연결·검증 안내](https://developers.openai.com/plugins/deploy/connect-chatgpt)

로컬 HTTP가 필요하면 별도 터미널에서 다음과 같이 시작할 수 있습니다.

```sh
naver-searchad-mcp --transport streamable-http --host 127.0.0.1 --port 8000
```

주소는 `http://127.0.0.1:8000/mcp`입니다. Tunnel 설정에서 stdio 명령 대신 이 HTTP 주소를 지정할 수 있습니다. 본 서버의 HTTP는 loopback 전용이며 사용자 인증 서버가 아닙니다. 공용 호스트·포트 포워딩·공개 터널로 노출하는 구성은 제공하지 않습니다.

## 6. 쓰기와 첫 연결 점검

모든 예시는 기본 읽기 모드입니다. 쓰기가 필요하면 MCP 실행 명령의 **서버 인수**에 `--allow-writes`를 추가하고 재시작합니다. 1Password에서는 마지막 서버 실행 파일 뒤에 붙입니다. 환경변수 `NAVER_SEARCHAD_ALLOW_WRITES=1`도 같은 역할입니다. 각 쓰기 호출은 추가로 `confirm_action="NAVER_SEARCHAD_WRITE"`를 요구합니다.

연결 후 다음 순서로 확인합니다.

1. `get_usage_guide()`와 `validate_official_spec()` — 자격증명 없이 메타데이터 확인.
2. `search_operations("campaign")`, `get_operation_schema(...)` — 사용할 GET 선택.
3. 본인 계정의 GET을 `execute_read_operation`으로 실행 — 실제 네이버 인증 확인.

1번만 성공했다면 API 키나 광고 계정 권한까지 검증된 것은 아닙니다. 로컬 연결, 네이버 연결, ChatGPT/Claude 대화에서의 호출을 구분해서 점검하세요.
