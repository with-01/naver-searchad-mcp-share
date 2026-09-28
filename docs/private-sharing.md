# 지인에게 비공개 공유

배포 대상은 독립된 **Private** 저장소 `with-01/naver-searchad-mcp-share`입니다. 공유할 것은 소스 코드와 설치 안내이며, 네이버 API 키·1Password 데이터·실제 광고 데이터·개인 MCP 설정은 포함하지 않습니다.

## 저장소 업로드

아래는 저장소가 아직 없을 때 소유자가 배포 폴더에서 실행하는 절차입니다. 기존 저장소가 있다면 생성 명령을 반복하지 말고 `git remote -v`로 대상을 확인합니다.

```sh
git init -b main
git add .
git diff --cached --stat
git diff --cached
git commit -m "Prepare portable Naver SearchAd MCP"
gh repo create with-01/naver-searchad-mcp-share --private --source . --remote origin --push
gh repo view with-01/naver-searchad-mcp-share --json nameWithOwner,visibility,url
```

커밋 전에 staged diff에서 키, 환경 파일, 고객 ID, 광고 결과, 로컬 사용자 경로가 없는지 확인합니다. `.gitignore`는 이미 추적된 파일이나 과거 커밋의 비밀값을 지우지 않습니다. 실제 키가 올라갔다면 삭제 커밋만으로 해결하지 말고 해당 키를 폐기·재발급합니다. 이 저장소를 공개 PyPI에 올릴 필요는 없습니다.

## 지인 초대

GitHub 저장소의 Settings → Collaborators → Add people에서 지인의 GitHub 계정을 초대합니다. 수락 후 README의 clone·설치 순서로 진행하고, 각자가 자기 광고 계정 API 키를 준비합니다. [GitHub 공식 초대 안내](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/inviting-collaborators-to-a-personal-repository)

**개인 계정 소유의 private 저장소는 collaborator에게 쓰기 권한도 부여합니다.** 다운로드 전용 Read 권한을 따로 주려면 GitHub 조직 저장소의 권한 구조를 사용하세요. 초대를 취소해도 이미 받은 로컬 사본은 남습니다. [GitHub 권한 설명](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/permission-levels-for-a-personal-account-repository)

Private는 접근 범위 설정입니다. 초대된 사람이 파일을 다시 전달하는 것을 기술적으로 막지는 않습니다. 배포 범위와 재공유 여부는 지인들과 별도로 합의하세요.

## 업데이트와 Wheel

소스를 수정하지 않은 사용자는 아래와 같이 업데이트하고 MCP 클라이언트를 다시 시작합니다.

```sh
git pull --ff-only
python -m pip install .
```

`python`은 설치에 사용한 가상환경의 실행 파일이어야 합니다. 직접 수정한 사용자는 변경을 먼저 보존하고 차이를 검토하세요. 같은 버전을 다시 설치해야 한다면 `pip install --force-reinstall .`을 사용할 수 있습니다.

유지관리자는 `python -m pip wheel --no-deps . --wheel-dir dist`로 Wheel을 만들고 **Private 저장소의 Release**에 첨부할 수 있습니다. 수신자는 가상환경에서 `python -m pip install /path/to/package.whl`로 설치합니다. 배포 버전과 명세 출처를 함께 남기세요.

GitHub 권한과 광고 계정 권한은 별개입니다. 친구의 연결 테스트를 위해 소유자의 키나 실행 중인 MCP/Tunnel을 공유하지 않습니다.
