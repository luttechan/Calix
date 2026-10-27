# Calix 1.0 설계 참고

| 참고 | 반영 |
|---|---|
| [Fluent 2 타이포그래피](https://fluent2.microsoft.design/typography) | 제목, 본문, 보조 정보의 크기와 여백 계층 |
| [Fluent 2 레이아웃](https://fluent2.microsoft.design/layout) | 일관된 탐색, 카드, 상세 패널 |
| [Fluent 2 모션](https://fluent2.microsoft.design/motion) | 짧은 전환과 숨겨진 화면의 애니메이션 중지 |
| [Todoist 반복 날짜](https://www.todoist.com/help/todoist/features/introduction-to-recurring-dates-YUYVJJAV) | 매일, 매주, 매월 반복 생성 |
| [Todoist 필터](https://www.todoist.com/help/todoist/features/introduction-to-filters-V98wIH) | 검색, 과목, 유형, 상태를 함께 적용 |
| [Google Calendar 반복 일정](https://support.google.com/calendar/answer/37115) | 이번 일정 편집, 이번 일정 또는 전체 반복 삭제 |
| ANV Extended 2.0 로컬 크레딧 | 프로필, 개발자 이름, 링크 카드 구조 |
| Lexift 로컬 프로그램 | 실제 Qt 위젯과 레이아웃, 네이티브 텍스트 처리 |

복잡한 모션 대신 일관된 기본 흐름에 초점을 맞췄습니다. 텍스트는 Qt 네이티브 컨트롤로 표시합니다.

## 비밀 일기

암호화 라이브러리는 PyCA cryptography입니다. 직접 암호 알고리즘을 구현하지 않습니다.

- AES-256-GCM, 매번 새 96비트 nonce
- Argon2id: 64 MiB, 3회, 4 lanes, 무작위 128비트 salt, 256비트 출력
- 무작위 데이터 키를 암호에서 계산한 키로 감싸는 구조
- 일기 ID와 형식 버전을 인증 데이터에 묶음
- 날짜, 제목, 본문, HTML 서식 모두 암호화
- 4 KiB 단위 패딩으로 정확한 본문 길이를 숨김
- 별도 암호화 SQLite 저장소와 암호화 상태의 백업
- 복호화한 일기는 파일, 로그, 임시 파일에 기록하지 않음
- 틀린 암호와 변조된 데이터는 열지 않음
- 백그라운드 창, 다른 페이지 이동, 5분 비활동 시 자동 잠금
- 잠글 때 편집기, 목록, 실행 취소 이력을 비움. 키의 bytearray는 최선의 범위에서 덮어씀

Python, Qt, 운영체제의 모든 메모리 복사본을 완전히 지운다고 보장할 수는 없습니다.
실행 중인 컴퓨터의 악성코드, 키로거, 화면 캡처, 열린 상태의 메모리 접근은 보호 범위 밖입니다.
암호의 강도와 관리가 중요합니다. 암호 복구 수단이나 숨겨진 마스터 키는 없습니다.
암호 변경은 데이터 키를 새 암호로 다시 감쌉니다. 오래된 백업과 스냅샷은 당시 암호를 유지합니다.
암호 확인 시에는 Argon2id 작업 메모리가 일시적으로 추가됩니다.

근거: [PyCA AEAD](https://cryptography.io/en/latest/hazmat/primitives/aead/), [RFC 9106](https://www.rfc-editor.org/rfc/rfc9106.html).

## 저장과 실행

일반/비밀 일기는 학교 계정과 독립적으로 저장합니다. 수동 일정은 학교 일정 동기화로 덮어쓰지 않습니다.
백업 파일은 형식과 크기, 색상, 시간, 중복 ID 등을 확인하고 고정된 저장 명령으로 복원합니다.
SQLite rollback journal로 일정과 일기 복원을 하나의 트랜잭션으로 묶습니다.
로그인 브라우저는 별도 프로세스에 두고 메인 실행에서 불러오지 않습니다.
과목 동시 조회는 최대 4개로 제한합니다. 실제 학교 접속 시간은 서버와 네트워크에 영향을 받습니다.
