# Calix

부산외대 Canvas 일정 관리 프로그램.

[다운로드](https://github.com/luttechan/Calix/releases/latest) / [사이트](https://luttechan.github.io/calix/) / [사용 설명서](https://luttechan.github.io/calix/guide/)

Windows 10 / 11, 64비트. 압축 해제 후 `Calix.exe` 실행.

## 소스 실행

Python 3.14.10.

```text
python -m pip install --only-binary=:all: -r requirements-build.txt
python tools/prepare_assets.py
python main.py
```

빌드: `build_windows.bat`. 출력: 저장소 밖 `../Calix-builds/Calix 1.0.8/`.

개발: Lutté Laurent
