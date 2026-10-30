# Calix 1.4.2

React + TypeScript / Tauri. Python 엔진은 표준 입출력으로 연결합니다.

## 코드 위치

```text
desktop/
  src/                 React 화면과 스타일
  src-tauri/src/       창, 로그인 WebView2, 트레이, 파일 선택
  engine_*.py          데이터 API, 세션, 동기화 연결, 업데이트
  tools/               빌드와 패키지 검사
learning_calendar/     기존 수집 엔진과 저장소
tests/                 Python 회귀 검사
```


## 실행

`main.py`와 `run_source.bat`는 Tauri 개발 모드를 실행합니다. Qt 앱으로 전환하지 않습니다.
Rust 및 Windows C++ 빌드 도구가 필요합니다.

React 화면만 편집: `python main.py --preview`.
미리보기에서는 로그인, 파일 선택과 설치 기능을 사용할 수 없습니다.

```text
python -m pip install -r requirements-build.txt brotli==1.2.1
python tools/prepare_assets.py
python desktop/tools/prepare_web_assets.py
python desktop/tools/build_engine.py
cd desktop
pnpm install --frozen-lockfile
pnpm tauri dev
```

빌드: `pnpm tauri build`.

Pretendard © 2021 Kil Hyung-jin. [SIL OFL 1.1](../asset/style/Pretendard-OFL.txt).
