# 공개 코드 공유와 업데이트

배포 저장소는 공개된 [with-01/naver-searchad-mcp-share](https://github.com/with-01/naver-searchad-mcp-share)입니다. 지인에게 [README](../README.md)와 [클라이언트 설정 안내](clients.md)를 전달하면 됩니다. 기본 사용 방식은 **`uvx` 자동 다운로드·실행**이며, GitHub 로그인·초대·소스 ZIP 다운로드·Git 복제는 필요하지 않습니다.

## 처음 사용

1. [uv 공식 설치 안내](https://docs.astral.sh/uv/getting-started/installation/)에 따라 `uv`를 한 번 설치합니다. `uvx`도 포함됩니다.
2. 새 터미널에서 다음 명령으로 패키지 다운로드와 도움말 실행을 확인합니다.

```sh
uvx --python 3.12 --from https://github.com/with-01/naver-searchad-mcp-share/releases/download/v0.3.0/naver_searchad_mcp-0.3.0-py3-none-any.whl naver-searchad-mcp --help
```

3. [클라이언트 예시](clients.md)의 `command: uvx`와 전체 `args`를 개인 Claude/Codex 설정에 넣고 본인의 네이버 API 키 세 개를 채웁니다.
4. 클라이언트를 다시 시작하고 `get_usage_guide`를 호출합니다.

Wheel과 의존성은 uv가 격리 환경에 준비합니다. 필요한 Python 3.12도 uv의 기본 설정에서 자동으로 준비합니다. 이 프로젝트는 PyPI에 게시하지 않으며, 설정은 위 GitHub Release의 **Wheel URL**을 지정합니다. 처음 한 번은 다운로드 시간이 필요합니다. [uv 도구 실행 안내](https://docs.astral.sh/uv/guides/tools/)

앱에서 `uvx`를 찾지 못하면 Windows PowerShell의 `(Get-Command uvx).Source` 또는 macOS/Linux의 `command -v uvx`로 확인한 절대 경로를 `command`에 넣습니다.

## 각자 자신의 광고 계정 연결

1Password는 필요하지 않습니다. 각자가 자신의 네이버 API 키를 로컬 Claude/Codex 설정의 `env`에 평문으로 넣습니다. 저장소의 `examples` 원본은 그대로 두고, 개인 설정 파일 또는 `claude-code.local.json`, `codex.local.toml`, `server-env.local.ps1` 같은 사본에만 실제 값을 넣습니다.

이 사본 이름과 `.env` 파일은 `.gitignore`에서 제외합니다. 키를 채운 파일은 커밋하거나 다른 사람에게 전달하지 않습니다. 이미 추적되는 예시 원본에 키를 넣으면 `.gitignore`가 보호하지 못합니다. 공개 저장소에는 코드·설치 예시만 올리고, 실제 키·광고 데이터·개인 설정은 포함하지 않습니다.

**코드 공개는 광고 계정 공개가 아닙니다.** `uvx`는 자신의 컴퓨터에서 MCP 서버를 실행합니다. Wheel URL은 패키지 다운로드 주소이며 호스팅형 MCP 접속 주소가 아닙니다. ChatGPT 웹 사용자는 자신의 서버와 Tunnel 등 연결 경로를 준비하고 네이버 API 키를 서버 환경에 설정합니다. API 키를 채팅에 붙여 넣거나 다른 사람의 MCP 서버·Tunnel을 함께 사용하지 마세요.

## 업데이트

기본 예시는 서버 패키지를 `v0.3.0`으로 고정합니다. 새 버전을 적용할 때는 Release의 변경 내용을 확인하고, 개인 MCP 설정의 `--from` 다음 Wheel URL을 새 버전 URL로 바꾼 뒤 클라이언트를 재시작합니다. API 키와 다른 개인 설정은 유지합니다. `uvx`가 지정된 버전의 패키지를 준비하므로 ZIP을 다시 내려받거나 가상환경을 직접 만들 필요는 없습니다.

## 선택: 수동 설치와 개발

소스를 수정하거나 직접 설치하려면 [소스 ZIP](https://github.com/with-01/naver-searchad-mcp-share/releases/latest/download/naver-searchad-mcp.zip)을 받아 압축 안의 `naver-searchad-mcp` 폴더에서 [README 수동 설치](../README.md#선택-소스로-수동-설치)를 진행합니다. 이 방식은 Python 3.11 이상이 필요합니다. Git을 사용하는 사람은 `git clone https://github.com/with-01/naver-searchad-mcp-share.git`으로 복제할 수 있습니다.

수동 설치에서는 MCP의 `command`를 설치된 실행 파일의 절대 경로로, `args`를 서버 인수만 포함하는 배열로 바꿉니다. 소스를 직접 수정하지 않은 Git 사용자는 `git pull --ff-only` 후 가상환경의 `python -m pip install .`로 업데이트할 수 있습니다. 유지관리자는 `python -m pip wheel --no-deps . --wheel-dir dist`로 Wheel을 만듭니다.

## 배포 파일 관리

배포 전에 변경 내용과 ZIP·Wheel의 포함 파일을 확인합니다. `.gitignore`는 과거 커밋이나 별도로 만든 압축파일에서 비밀값을 제거하지 않습니다. 실제 키가 공개되었다면 해당 키를 폐기·재발급합니다. GitHub Release에는 소스·실행에 필요한 패키지와 문서만 첨부하고, 개인 설정·환경 파일·광고 결과는 포함하지 않습니다.