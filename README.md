# Microcap Radar

## 로컬 실행

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

기존 HTML 내장 종목과 `data/TICKER.json` 분석을 함께 사용합니다. 로컬 서버에서는 `data/` 디렉터리 목록을 읽으므로 새 JSON 파일만 추가하고 새로고침하면 됩니다. JSON 로딩 실패 시 내장 데이터는 계속 사용할 수 있으며, 실패한 파일은 브라우저 콘솔에 기록됩니다.

## 종목 추가

`data/CDT.json`과 같은 형식으로 `data/ABC.json`을 추가합니다. 파일명은 대문자 티커이며 `ticker` 필드와 일치해야 합니다. 기존 Radar 데이터 형식도 지원합니다. `signal.color/text/summary`, `verified`, `scenario`, `framework`, `memo.dilution/watch`, `events[].event`는 기존 분석 화면의 신호등, 공시 이력, 시나리오, 4인 프레임, 메모, 일정에 연결됩니다. 제공되지 않은 수치는 추정해서 채우지 않습니다.

## GitHub Pages

저장소 **Settings → Pages → Source**를 **GitHub Actions**로 설정합니다. `main`에 push하면 `pages.yml`이 `data/*.json`을 스캔하여 `data/index.json`을 생성하고 사이트를 배포합니다. 따라서 앞으로 종목 JSON만 추가하면 되며 HTML이나 목록을 수동 편집할 필요가 없습니다. `update-status.json` 같은 상태 파일은 종목 목록에서 제외됩니다. 기존 자동 업데이트 워크플로는 유지됩니다.

다른 정적 호스팅을 사용할 경우 배포 전에 다음 명령을 실행하고 `index.html`과 `data/`를 함께 배포합니다.

```sh
python3 scripts/build-data-index.py
```

## 검증

로컬 서버 실행 후 Python Playwright와 Chromium이 설치된 환경에서:

```sh
python3 tests/radar-browser.py
```

현재 클라우드 환경에는 필요한 브라우저 도구가 설치되어 있습니다. 테스트는 28개 분석 화면, 11개 탭, CDT 검색, 메모 지속성, 모바일 렌더링, 잘못된 JSON 격리, 정적 목록 로딩, 새 JSON 자동 발견을 확인합니다. 새 종목 테스트의 임시 파일은 종료 시 제거됩니다.
