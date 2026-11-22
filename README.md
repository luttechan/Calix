<h1 align="center">Calix</h1>

<p align="center">부산외국어대학교 Canvas 일정 관리</p>

<p align="center"><a href="https://github.com/luttechan/Calix/releases/latest"><strong>Windows 다운로드</strong></a>　<a href="https://luttechan.github.io/calix/guide/">사용 설명서</a>　<a href="https://luttechan.github.io/calix/">공식 사이트</a></p>

<p align="center">Windows 10 / 11 x64　|　공개 버전 1.7.5</p>

<p align="center"><img src="docs/images/calendar.webp" alt="Calix 달력 화면. 예시 일정이 과제와 영상 색상으로 구분되어 있습니다." width="1040"></p>

## 주요 기능

| 영역 | 기능 |
| --- | --- |
| Canvas | 과목별 과제, 영상, 제출 상태, 교수 코멘트, 출결 동기화 |
| 일정 | 달력, 마감 보드, 체크리스트, 학기별 시간표, 사용자 카테고리 |
| 학습 | 학점 계산, 뽀모도로, 공부 기록, 주간 통계, Anki |
| 보관 | 일기장, 저장 데이터 암호화, 백업과 복원 |

## 1.7.5

영어와 일본어를 추가했습니다. 설정 → 언어에서 변경할 수 있습니다. 일반·긴급 마감 알림을 개선했습니다. 긴급 마감은 남은 시간을 표시하며, 기준을 분 또는 시간으로 설정할 수 있습니다. 상단 바에서 창이 이동하지 않던 문제를 수정했습니다.

## 1.7.4

시간표에서 비대면 수업 영역의 겹침을 수정했습니다. 화면 전환에 모션을 추가했고, 잠금 화면에서 종료할 수 있습니다. 학습 화면에서 ANV 2.1 연결과 최근 Anki 동기화 상태를 확인할 수 있습니다.

## 1.7.3

홈에서 메인 학기를 수동 변경할 수 있습니다. Anki 연동 오류를 수정하고, 별도 콘솔과 잠금 해제음을 추가했습니다.

## 1.7.2

학기 자동 전환, Anki 덱 현황 연동, 시간표 시간 선택과 한글 입력을 추가했습니다.

## 1.7.1

설정 탭의 아이콘과 이름을 한 줄로 정렬하고, 창 너비에 맞춰 배치합니다.

## 1.7.0

달력 연도·월 이동, 체크리스트 기한과 열 너비 편집, 시간표 상세 화면을 개선했습니다. 시작 잠금 화면과 일반 리마인드 표시 오류를 수정했습니다.

[변경 이력](https://github.com/luttechan/Calix/releases)

<details>
<summary>소스 실행</summary>

Python 3.14.10, Node.js 24, pnpm 11, Rust, Windows C++ 빌드 도구가 필요합니다.

```powershell
pymanager install --update 3.14.10
pymanager exec -V:3.14.10 -m venv --upgrade .venv
.venv\Scripts\python -m pip install --only-binary=:all: -r requirements-build.txt brotli==1.2.1
npm install -g pnpm@11.25.0
.venv\Scripts\python main.py
```

React 미리보기는 `.venv\Scripts\python main.py --preview`로 실행합니다.

</details>

Lutté Laurent, Lutein Studio

Pretendard 기반 Calix Sans. © 2021 Kil Hyung-jin. [SIL OFL 1.1](asset/style/Pretendard-OFL.txt)
