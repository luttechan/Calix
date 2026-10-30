# Calix 1.4

React + TypeScript / Tauri. Python 엔진은 표준 입출력으로 연결합니다.

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
