# 글꼴

입력 원본: asset/style/PretendardVariable.ttf. 사용자 제공 파일은 변경하지 않습니다.

Windows GDI에서 가변 글꼴의 첫 중간 굵기 처리에 지연이 관찰되어 400 / 500 / 600 / 700 굵기를 빌드 시 고정합니다. 모든 글리프를 유지하고 별도 서브셋은 만들지 않습니다.

생성 파일: CalixSans-Regular.ttf / CalixSans-Medium.ttf / CalixSans-SemiBold.ttf / CalixSans-Bold.ttf.

OFL의 예약 글꼴 이름을 지키기 위해 파생 글꼴의 표시 이름을 Calix Sans로 구분합니다. 글자 모양은 제공된 Pretendard의 해당 굵기에서 생성합니다. 라이선스와 원 저작권 표시는 asset/style/Pretendard-OFL.txt에 포함됩니다.

재생성: python tools/build_fonts.py. fonttools 4.67.0 필요.

일기에 저장된 기존 Pretendard와 맑은 고딕 서식은 편집기에 표시할 때 현재 앱 글꼴로 맞추며, 글자와 굵기, 색은 유지합니다. 원본 일기 파일을 일괄 변경하지 않습니다.
