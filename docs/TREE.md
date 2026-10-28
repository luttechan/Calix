# 디렉터리

```text
Calix/                         소스 저장소
├─ main.py
├─ learning_calendar/          앱 코드
├─ asset/                      공용 원본 자산
├─ tests/
├─ tools/                      자산 생성과 빌드 검사
├─ docs/
├─ Calix.spec
├─ requirements*.txt
├─ run_source.bat
└─ build_windows.bat

Calix-builds/                  저장소 밖 실행 파일
└─ Calix 1.0.8/
   ├─ Calix.exe
   ├─ _internal/               네이티브 라이브러리와 런타임 자산
   └─ run_windows.bat          릴리즈에 포함
```

버전별 소스는 Git 태그로 보관합니다. 폰트 파생본과 썸네일은 빌드 시 생성합니다.
개인 자료는 `%APPDATA%\LutteLaurent\Calix`에 저장합니다.
