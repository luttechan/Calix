# Calix 1.4.1

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

편집 기준 경로는 `G:\Development\Calix`입니다. 실행 파일은 형제 폴더 `Calix-builds`에 둡니다.

## 실행

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
