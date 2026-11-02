# 측정 요약

- 측정 시각(UTC): 2026-11-02T14:40:30+00:00
- CPU: AMD Ryzen 5 7500F 6-Core Processor / OS: Windows-10-10.0.26200-SP0
- Python 3.11.18 (OpenSSL 3.5.9 29 Sep 2026), requests 2.34.2
- C++: MSVC, libcurl/8.18.0 Schannel zlib/1.2.13 brotli/1.2.0 zstd/1.5.6 libssh2/1.11.1 | OpenSSL 3.5.5 27 Jan 2026

### 1. 주문 생성 + 응답 파싱 (네트워크 없음)

| 구현 | 구간 | n | 평균 | p50 | p90 | p99 | p99.9 | 최대 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Python (requests + PyJWT) | 주문 생성(서명) | 300,000 | 26.0 µs | 25.1 µs | 26.4 µs | 44.2 µs | 92.6 µs | 5.06 ms |
| Python (requests + PyJWT) | 응답 파싱 | 300,000 | 3.8 µs | 3.7 µs | 3.8 µs | 6.4 µs | 13.5 µs | 76.8 µs |
| Python (stdlib, tuned) | 주문 생성(서명) | 300,000 | 9.6 µs | 9.3 µs | 9.6 µs | 15.4 µs | 39.8 µs | 4.98 ms |
| Python (stdlib, tuned) | 응답 파싱 | 300,000 | 3.8 µs | 3.7 µs | 3.9 µs | 6.2 µs | 12.7 µs | 278.2 µs |
| C++ (libcurl + OpenSSL) | 주문 생성(서명) | 300,000 | 2.7 µs | 2.6 µs | 2.7 µs | 4.5 µs | 8.1 µs | 163.3 µs |
| C++ (libcurl + OpenSSL) | 응답 파싱 | 300,000 | 0.5 µs | 0.5 µs | 0.6 µs | 0.7 µs | 1.1 µs | 250.9 µs |

### 2. 로컬 mock 서버 왕복 (연결 재사용)

| 구현 | 구간 | n | 평균 | p50 | p90 | p99 | p99.9 | 최대 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Python (requests + PyJWT) | 주문 생성(서명) | 19,996 | 57.8 µs | 55.6 µs | 61.9 µs | 88.2 µs | 131.7 µs | 325.8 µs |
| Python (requests + PyJWT) | HTTP 왕복 | 19,996 | 712.3 µs | 687.5 µs | 786.4 µs | 1.04 ms | 1.20 ms | 1.51 ms |
| Python (requests + PyJWT) | 응답 파싱 | 19,996 | 8.8 µs | 8.5 µs | 9.2 µs | 14.1 µs | 20.8 µs | 72.6 µs |
| Python (requests + PyJWT) | 합계 | 19,996 | 778.9 µs | 752.2 µs | 858.1 µs | 1.13 ms | 1.30 ms | 1.59 ms |
| Python (stdlib, tuned) | 주문 생성(서명) | 19,996 | 21.2 µs | 19.6 µs | 25.2 µs | 41.2 µs | 55.3 µs | 223.9 µs |
| Python (stdlib, tuned) | HTTP 왕복 | 19,996 | 88.4 µs | 80.9 µs | 108.5 µs | 162.6 µs | 302.3 µs | 686.9 µs |
| Python (stdlib, tuned) | 응답 파싱 | 19,996 | 6.5 µs | 5.9 µs | 7.9 µs | 13.1 µs | 20.7 µs | 184.8 µs |
| Python (stdlib, tuned) | 합계 | 19,996 | 116.1 µs | 106.6 µs | 141.7 µs | 212.6 µs | 354.0 µs | 719.8 µs |
| C++ (libcurl + OpenSSL) | 주문 생성(서명) | 19,996 | 5.7 µs | 5.4 µs | 6.1 µs | 11.0 µs | 17.7 µs | 99.2 µs |
| C++ (libcurl + OpenSSL) | HTTP 왕복 | 19,996 | 46.6 µs | 44.1 µs | 49.8 µs | 88.8 µs | 129.6 µs | 304.2 µs |
| C++ (libcurl + OpenSSL) | 응답 파싱 | 19,996 | 0.7 µs | 0.7 µs | 0.8 µs | 1.4 µs | 2.0 µs | 45.7 µs |
| C++ (libcurl + OpenSSL) | 합계 | 19,996 | 53.0 µs | 50.7 µs | 56.3 µs | 100.4 µs | 145.5 µs | 313.5 µs |

### 3. 업비트 order-test (연결 재사용)

| 구현 | 구간 | n | 평균 | p50 | p90 | p99 | p99.9 | 최대 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Python (requests + PyJWT) | 주문 생성(서명) | 590 | 195.8 µs | 190.4 µs | 228.9 µs | 305.8 µs | 510.5 µs | 563.9 µs |
| Python (requests + PyJWT) | HTTP 왕복 | 590 | 34.42 ms | 34.26 ms | 40.78 ms | 50.21 ms | 61.25 ms | 64.21 ms |
| Python (requests + PyJWT) | 응답 파싱 | 590 | 17.9 µs | 17.6 µs | 22.2 µs | 28.5 µs | 80.8 µs | 121.2 µs |
| Python (requests + PyJWT) | 합계 | 590 | 34.64 ms | 34.46 ms | 41.00 ms | 50.43 ms | 61.42 ms | 64.41 ms |
| Python (stdlib, tuned) | 주문 생성(서명) | 590 | 119.8 µs | 120.0 µs | 139.4 µs | 171.4 µs | 208.0 µs | 209.0 µs |
| Python (stdlib, tuned) | HTTP 왕복 | 590 | 33.55 ms | 33.79 ms | 38.74 ms | 46.75 ms | 66.55 ms | 67.23 ms |
| Python (stdlib, tuned) | 응답 파싱 | 590 | 20.8 µs | 20.6 µs | 25.4 µs | 32.1 µs | 46.2 µs | 63.0 µs |
| Python (stdlib, tuned) | 합계 | 590 | 33.69 ms | 33.93 ms | 38.89 ms | 46.91 ms | 66.69 ms | 67.39 ms |
| C++ (libcurl + OpenSSL) | 주문 생성(서명) | 590 | 46.5 µs | 46.2 µs | 55.7 µs | 74.9 µs | 147.6 µs | 189.7 µs |
| C++ (libcurl + OpenSSL) | HTTP 왕복 | 590 | 33.92 ms | 33.85 ms | 39.97 ms | 49.57 ms | 68.19 ms | 69.61 ms |
| C++ (libcurl + OpenSSL) | 응답 파싱 | 590 | 1.9 µs | 1.9 µs | 2.3 µs | 3.0 µs | 4.8 µs | 6.3 µs |
| C++ (libcurl + OpenSSL) | 합계 | 590 | 33.96 ms | 33.91 ms | 40.02 ms | 49.60 ms | 68.25 ms | 69.66 ms |

### 4a. 업비트 order-test (각 실행의 첫 요청, 새 연결)

| 구현 | 구간 | n | 평균 | p50 | p90 | p99 | p99.9 | 최대 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Python (requests + PyJWT) | 주문 생성(서명) | 10 | 155.9 µs | 147.5 µs | 173.1 µs | 205.8 µs | 209.0 µs | 209.4 µs |
| Python (requests + PyJWT) | HTTP 왕복 | 10 | 63.84 ms | 58.65 ms | 74.20 ms | 120.01 ms | 124.60 ms | 125.10 ms |
| Python (requests + PyJWT) | 응답 파싱 | 10 | 26.3 µs | 25.6 µs | 29.6 µs | 33.7 µs | 34.2 µs | 34.2 µs |
| Python (requests + PyJWT) | 합계 | 10 | 64.02 ms | 58.86 ms | 74.38 ms | 120.18 ms | 124.76 ms | 125.27 ms |
| Python (stdlib, tuned) | 주문 생성(서명) | 10 | 101.0 µs | 93.0 µs | 110.3 µs | 156.4 µs | 161.0 µs | 161.5 µs |
| Python (stdlib, tuned) | HTTP 왕복 | 10 | 54.85 ms | 50.11 ms | 61.07 ms | 105.57 ms | 110.02 ms | 110.52 ms |
| Python (stdlib, tuned) | 응답 파싱 | 10 | 28.1 µs | 27.0 µs | 33.1 µs | 33.5 µs | 33.5 µs | 33.5 µs |
| Python (stdlib, tuned) | 합계 | 10 | 54.98 ms | 50.23 ms | 61.19 ms | 105.71 ms | 110.16 ms | 110.65 ms |
| C++ (libcurl + OpenSSL) | 주문 생성(서명) | 10 | 71.8 µs | 70.5 µs | 78.2 µs | 84.3 µs | 84.9 µs | 85.0 µs |
| C++ (libcurl + OpenSSL) | HTTP 왕복 | 10 | 67.82 ms | 58.24 ms | 89.24 ms | 130.81 ms | 134.97 ms | 135.43 ms |
| C++ (libcurl + OpenSSL) | 응답 파싱 | 10 | 1.8 µs | 1.8 µs | 2.2 µs | 2.5 µs | 2.5 µs | 2.5 µs |
| C++ (libcurl + OpenSSL) | 합계 | 10 | 67.90 ms | 58.32 ms | 89.31 ms | 130.89 ms | 135.05 ms | 135.51 ms |

### 4b. 업비트 order-test (요청마다 새 연결)

| 구현 | 구간 | n | 평균 | p50 | p90 | p99 | p99.9 | 최대 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Python (requests + PyJWT) | 주문 생성(서명) | 40 | 210.0 µs | 213.8 µs | 234.7 µs | 253.4 µs | 255.8 µs | 256.1 µs |
| Python (requests + PyJWT) | HTTP 왕복 | 40 | 50.69 ms | 50.12 ms | 54.32 ms | 78.58 ms | 89.94 ms | 91.20 ms |
| Python (requests + PyJWT) | 응답 파싱 | 40 | 22.7 µs | 22.1 µs | 26.9 µs | 29.2 µs | 30.2 µs | 30.3 µs |
| Python (requests + PyJWT) | 합계 | 40 | 50.93 ms | 50.34 ms | 54.50 ms | 78.79 ms | 90.13 ms | 91.39 ms |
| Python (stdlib, tuned) | 주문 생성(서명) | 40 | 134.2 µs | 135.3 µs | 150.1 µs | 173.4 µs | 179.7 µs | 180.4 µs |
| Python (stdlib, tuned) | HTTP 왕복 | 40 | 56.29 ms | 55.41 ms | 63.10 ms | 93.48 ms | 99.10 ms | 99.73 ms |
| Python (stdlib, tuned) | 응답 파싱 | 40 | 27.7 µs | 26.1 µs | 31.2 µs | 50.7 µs | 58.0 µs | 58.8 µs |
| Python (stdlib, tuned) | 합계 | 40 | 56.45 ms | 55.57 ms | 63.21 ms | 93.66 ms | 99.28 ms | 99.91 ms |
| C++ (libcurl + OpenSSL) | 주문 생성(서명) | 40 | 54.7 µs | 46.2 µs | 75.3 µs | 113.1 µs | 122.4 µs | 123.4 µs |
| C++ (libcurl + OpenSSL) | HTTP 왕복 | 40 | 51.52 ms | 43.95 ms | 58.49 ms | 192.26 ms | 253.42 ms | 260.22 ms |
| C++ (libcurl + OpenSSL) | 응답 파싱 | 40 | 2.5 µs | 2.5 µs | 3.0 µs | 4.2 µs | 4.6 µs | 4.6 µs |
| C++ (libcurl + OpenSSL) | 합계 | 40 | 51.57 ms | 43.99 ms | 58.54 ms | 192.31 ms | 253.47 ms | 260.26 ms |

### 5a. 주문 생성, 150ms 간격 (간격 동안 sleep)

| 구현 | 구간 | n | 평균 | p50 | p90 | p99 | p99.9 | 최대 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Python (requests + PyJWT) | 주문 생성(서명) | 300 | 199.5 µs | 195.2 µs | 227.4 µs | 275.9 µs | 309.8 µs | 321.8 µs |
| Python (requests + PyJWT) | 응답 파싱 | 300 | 14.4 µs | 13.7 µs | 17.1 µs | 22.2 µs | 29.0 µs | 31.0 µs |
| Python (stdlib, tuned) | 주문 생성(서명) | 300 | 126.5 µs | 125.2 µs | 140.8 µs | 207.6 µs | 222.9 µs | 223.2 µs |
| Python (stdlib, tuned) | 응답 파싱 | 300 | 28.4 µs | 28.5 µs | 32.2 µs | 37.6 µs | 49.5 µs | 53.6 µs |
| C++ (libcurl + OpenSSL) | 주문 생성(서명) | 300 | 46.1 µs | 45.5 µs | 61.6 µs | 76.4 µs | 80.5 µs | 81.1 µs |
| C++ (libcurl + OpenSSL) | 응답 파싱 | 300 | 3.1 µs | 2.9 µs | 3.8 µs | 7.6 µs | 20.6 µs | 25.3 µs |

### 5b. 주문 생성, 150ms 간격 (간격 동안 busy-wait)

| 구현 | 구간 | n | 평균 | p50 | p90 | p99 | p99.9 | 최대 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Python (requests + PyJWT) | 주문 생성(서명) | 300 | 185.5 µs | 182.2 µs | 214.4 µs | 277.3 µs | 326.7 µs | 327.3 µs |
| Python (requests + PyJWT) | 응답 파싱 | 300 | 13.2 µs | 12.3 µs | 16.2 µs | 21.4 µs | 83.2 µs | 108.9 µs |
| Python (stdlib, tuned) | 주문 생성(서명) | 300 | 116.2 µs | 116.4 µs | 129.7 µs | 153.1 µs | 179.7 µs | 184.5 µs |
| Python (stdlib, tuned) | 응답 파싱 | 300 | 23.8 µs | 23.1 µs | 27.3 µs | 33.1 µs | 83.2 µs | 98.7 µs |
| C++ (libcurl + OpenSSL) | 주문 생성(서명) | 300 | 34.9 µs | 34.9 µs | 40.5 µs | 49.0 µs | 78.8 µs | 84.6 µs |
| C++ (libcurl + OpenSSL) | 응답 파싱 | 300 | 2.3 µs | 2.3 µs | 2.7 µs | 3.7 µs | 4.2 µs | 4.3 µs |

### 5c. 주문 생성, 150ms 간격 (간격 동안 더미 주문으로 캐시 데우기)

| 구현 | 구간 | n | 평균 | p50 | p90 | p99 | p99.9 | 최대 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Python (requests + PyJWT) | 주문 생성(서명) | 300 | 28.1 µs | 25.5 µs | 30.3 µs | 72.6 µs | 153.2 µs | 156.6 µs |
| Python (requests + PyJWT) | 응답 파싱 | 300 | 10.8 µs | 10.3 µs | 12.2 µs | 17.7 µs | 27.3 µs | 30.5 µs |
| Python (stdlib, tuned) | 주문 생성(서명) | 300 | 11.0 µs | 9.6 µs | 10.5 µs | 41.3 µs | 104.8 µs | 111.3 µs |
| Python (stdlib, tuned) | 응답 파싱 | 300 | 22.0 µs | 21.7 µs | 25.0 µs | 31.5 µs | 42.6 µs | 45.4 µs |
| C++ (libcurl + OpenSSL) | 주문 생성(서명) | 300 | 3.5 µs | 3.0 µs | 3.3 µs | 4.8 µs | 70.7 µs | 72.6 µs |
| C++ (libcurl + OpenSSL) | 응답 파싱 | 300 | 2.3 µs | 2.3 µs | 2.8 µs | 3.2 µs | 3.9 µs | 4.1 µs |
