# Calix v.1.4.21

부산외대 Canvas 일정 관리 프로그램.

[다운로드](https://github.com/luttechan/Calix/releases/latest) / [사이트](https://luttechan.github.io/calix/) / [사용 설명서](https://luttechan.github.io/calix/guide/)

Windows 10 / 11, 64비트. 설치 파일 또는 ZIP 제공.

업데이트: 설정 → 앱 관리 → 업데이트 확인.

## 1.1 → 1.4.21
1. 메인 엔진을 Qt에서 Tauri, React로 전환하고 UI 전면 개편
2. 홈, 과목별 일정과 학습 현황 제공
3. 달력, 체크리스트, 시간표 관리 기능 확장
4. 일반 일기, 비밀 일기 추가
5. 테마 5종 및 글래스 효과 적용
6. 로그인·업데이트 UI 통합 및 성능, 안정성 개선

## 1.4.2

- 첫 실행 닉네임 및 테마 설정
- 닉네임과 홈 문구 편집
- 확인 후 전체 DB 초기화
- 소스 진입점 정정 및 이전 Qt 화면 코드 제거

## 1.4.21

- 영상 수집의 그래픽 환경 의존과 준비 대기 개선
- 빈 영상 목록 조기 확정 방지
- 저장 후 재시작
- 숨김 개발자 콘솔: Ctrl+Shift+D. 로그는 기본 미수집

## 소스 실행

Python 3.14.10, Node.js 24, pnpm 11, Rust, Windows C++ 빌드 도구가 필요합니다.

```text
npm install -g pnpm@11.25.0
python -m pip install --only-binary=:all: -r requirements-build.txt brotli==1.2.1
python main.py
```

React 화면 미리보기:

```text
python main.py --preview
```

검사와 빌드:

```text
python -m pytest -q
build_desktop.bat
```

화면: `desktop/src`. 데이터 연결: `desktop/engine_*.py`.

개발: Lutté Laurent

글꼴: Pretendard 기반 Calix Sans. © 2021 Kil Hyung-jin.
[SIL OFL 1.1 / 전체 저작권 고지](asset/style/Pretendard-OFL.txt)

