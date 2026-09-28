# Hermes에서 계속 사용하기

서버는 일반 stdio MCP이므로 Hermes에서도 사용할 수 있습니다. 아래는 개인 경로와 비밀값이 없는 예시입니다. 설치된 Hermes 버전의 설정 형식에 맞춰 기존 항목에 합치고, 기존 설정은 먼저 백업하세요.

```yaml
mcp_servers:
  naver_searchad:
    command: /absolute/path/.venv/bin/naver-searchad-mcp
    args: []
    timeout: 180
    connect_timeout: 60
```

Hermes 실행 환경에 네이버 환경변수 3개를 전달합니다. 1Password를 쓴다면 실행 명령을 다음으로 바꿉니다.

```yaml
mcp_servers:
  naver_searchad:
    command: op
    args:
      - run
      - --no-masking
      - --env-file
      - /absolute/path/naver-searchad.op.env
      - --
      - /absolute/path/.venv/bin/naver-searchad-mcp
    timeout: 180
    connect_timeout: 60
```

`--no-masking`은 MCP stdio 출력이 치환되어 JSON이 손상되는 것을 방지합니다. 파일에는 `op://...` 참조만 넣으세요. [1Password 공식 설명](https://www.1password.dev/cli/reference/commands/run)

기본적으로 쓰기는 차단됩니다. 필요할 때만 마지막 서버 인수로 `--allow-writes`를 추가하고 서버를 재시작합니다. 채널의 도구 허용 목록이나 `no_mcp` 설정은 별도로 확인해야 하며, 서버를 등록했다고 모든 채널에서 자동 활성화되지는 않습니다.

변경 후 Hermes가 제공하는 재로드 또는 재시작 기능을 사용하고 `get_usage_guide`부터 확인합니다. Hermes 자체 설치·채널 설정·기존 키 저장 위치를 바꾸는 절차는 이 패키지에 포함하지 않습니다.