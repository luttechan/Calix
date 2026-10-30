# Calix

부산외대 Canvas 일정 관리 프로그램.

[다운로드](https://github.com/luttechan/Calix/releases/latest) / [사이트](https://luttechan.github.io/calix/) / [사용 설명서](https://luttechan.github.io/calix/guide/)

Windows 10 / 11, 64비트. 설치 파일 또는 ZIP 제공.

업데이트: 설정 → 앱 관리 → 업데이트 확인.

## 소스 실행

Python 3.14.10, Node 24, pnpm 11, Rust 및 Visual Studio C++ 빌드 도구.

```text
python -m pip install --only-binary=:all: -r requirements-build.txt brotli==1.2.1
python tools/prepare_assets.py
python desktop/tools/prepare_web_assets.py
python desktop/tools/build_engine.py
cd desktop
pnpm install --frozen-lockfile
pnpm tauri dev
```

빌드: `build_desktop.bat`.

화면 편집: `desktop/src`. 창과 로그인: `desktop/src-tauri/src`.
데이터 연결: `desktop/engine_*.py`. [개발 경로와 실행](desktop/README.md).

개발: Lutté Laurent

글꼴: Pretendard 기반 Calix Sans. © 2021 Kil Hyung-jin.
[SIL OFL 1.1 / 전체 저작권 고지](asset/style/Pretendard-OFL.txt)

