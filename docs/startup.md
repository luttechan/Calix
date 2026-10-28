# 시작 화면

기존 Calix SVG 로고와 제공된 Pretendard를 이용한 UI 이미지입니다. asset/startup.png는 확인용, startup.bmp는 Qt가 준비되기 전에 Windows에서 직접 읽는 실행용 이미지입니다. source/tools/render_startup.py로 다시 만들 수 있습니다.

main.py의 시작부에서 Qt를 가져오기 전에 startup_notice를 실행합니다. 같은 프로세스의 별도 Windows 메시지 루프가 이미지를 그려 로딩 중 대기 표시가 계속 움직입니다. 항상 위에 표시하며 클릭과 Alt+F4로 중간에 사라지지 않습니다.

startup_handoff는 메인 창의 첫 Paint를 확인한 후 120ms 뒤 이미지를 닫습니다. 준비 시간과 무관한 고정 종료 타이머는 사용하지 않습니다. Python 시작 오류는 안내 화면을 남기며 닫기 버튼으로 종료합니다. 프로세스 강제 종료 또는 Python이 시작되기 이전의 실행 환경 오류는 이 화면으로 처리할 수 없습니다.

로그인 전용, 연결 검사, 패키지 smoke 검사, 도움말 실행은 시작 이미지를 생략합니다. Windows가 아닌 환경과 offscreen 검사에서도 생략합니다.

영상과 과제의 요약 버튼은 자식 레이블의 크기를 포함한 레이아웃 크기를 사용합니다. 숫자가 길어져도 버튼 안에서 잘리지 않게 최소 크기를 계산합니다.
