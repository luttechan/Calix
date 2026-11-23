# Vesper QR

```text
calix-vesper://pair?v=1&token=<base64url>&expires=<unix-seconds>
```

`v`는 형식 버전입니다. `token`은 패딩 없는 24바이트 난수, `expires`는 UTC 기준 Unix 초입니다. 발급 후 최대 5분 동안 표시합니다. 앱이나 계정 식별자, 학습 데이터, 네트워크 주소는 넣지 않습니다.

현재 QR은 표시용입니다. 재발급·닫기·잠금 시 이전 QR을 화면에서 제거합니다. 실제 연동을 추가할 때는 스캔만으로 연결을 확정하지 않고, 양쪽 기기 확인 후 발급 정보를 한 번만 사용합니다.
