# 실행 환경

Windows 10 / 11, x64. Intel·AMD 제조사 제한 없음.
ARM64 및 32비트용 배포본은 제공하지 않음.

# 검증

- 자체 코드에 CPU 제조사 검사, AVX 강제 호출, `-march=native`, `target-cpu=native` 설정 없음.
- 공식 바이너리 패키지로 빌드. 소스 패키지의 로컬 CPU 최적화 빌드 차단.
- Qt와 OpenSSL은 실행 환경에 따라 가속 경로 선택.
- 별도 검사 프로세스에서 Qt AVX 계열 및 AES 가속, OpenSSL CPU 가속을 비활성화하고 검사.
- 기능 마스킹 검사는 실제 구형 CPU 또는 AMD 장비 검사를 대체하지 않음.

참고: [Qt CPU 경로 선택](https://github.com/qt/qtbase/blob/dev/src/corelib/global/qsimd.cpp), [OpenSSL CPU 기능 설정](https://docs.openssl.org/3.4/man3/OPENSSL_ia32cap/).
