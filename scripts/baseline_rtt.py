"""주문 왕복 시간을 나눠 보기 위한 기준값: 같은 호스트에 대한 TCP 연결 시간과 인증 없는 시세 조회 왕복.

- TCP connect  : SYN -> SYN/ACK 한 번 = 순수 네트워크 왕복(RTT)에 가깝다
- GET /v1/ticker: 같은 엣지/게이트웨이를 거치지만 인증, 주문 검증이 없는 요청
- 주문 테스트 왕복과의 차이 = 인증 + 주문 검증 등 거래소 내부 처리

결과: results/baseline_rtt.json
"""
import http.client
import json
import socket
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
HOST = "api.upbit.com"


def pct(v):
    v = np.asarray(v) / 1e6
    return {"n": int(v.size), "p50_ms": float(np.percentile(v, 50)), "p90_ms": float(np.percentile(v, 90)),
            "p99_ms": float(np.percentile(v, 99))}


def tcp_connect(n=40):
    addr = socket.getaddrinfo(HOST, 443, socket.AF_INET, socket.SOCK_STREAM)[0][4]
    out = []
    for _ in range(n):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        t = time.perf_counter_ns()
        s.connect(addr)
        out.append(time.perf_counter_ns() - t)
        s.close()
        time.sleep(0.1)
    return out


def ticker(n=200):
    conn = http.client.HTTPSConnection(HOST)
    conn.request("GET", "/v1/ticker?markets=KRW-BTC")
    conn.getresponse().read()  # 연결 수립(제외)
    out = []
    for _ in range(n):
        time.sleep(0.15)  # 시세 조회 제한(초당 10회)보다 느리게
        t = time.perf_counter_ns()
        conn.request("GET", "/v1/ticker?markets=KRW-BTC")
        conn.getresponse().read()
        out.append(time.perf_counter_ns() - t)
    return out


def main():
    result = {"tcp_connect": pct(tcp_connect()), "get_ticker_keepalive": pct(ticker())}
    (ROOT / "results" / "baseline_rtt.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
