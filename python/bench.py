"""Python 주문 경로 지연 측정.

    python python/bench.py --impl tuned --mode live --n 50 --out results/raw/x.csv

mode
- sign      : 네트워크 없이 주문 생성(직렬화 + 해시 + JWT)과 응답 파싱만 반복
- loopback  : 로컬 mock 서버(cpp/mock_server)로 HTTP 왕복까지 포함
- live      : 업비트 order-test API. 연결 재사용, 첫 요청은 새 연결(cold)로 기록
- live-cold : 업비트 order-test API. 요청마다 새 TCP+TLS 연결

CSV 열: impl,mode,seq,conn,status,sign_ns,http_ns,parse_ns,total_ns (C++과 같음)
"""
import argparse
import csv
import http.client
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(__file__))
from upbit_order import ORDER, ORDER_TEST_PATH, TunedSigner, build_idiomatic, parse_response  # noqa: E402

UPBIT_HOST = "api.upbit.com"
SAMPLE_RESPONSE = (b'{"market":"KRW-BTC","uuid":"cdd92199-2897-4e14-9448-f923320408ad","side":"bid","ord_type":"limit",'
                   b'"price":"50000000","state":"wait","created_at":"2026-11-02T14:00:00+09:00","volume":"0.0001",'
                   b'"remaining_volume":"0.0001","reserved_fee":"2.5","remaining_fee":"2.5","paid_fee":"0",'
                   b'"locked":"5002.5","executed_volume":"0","prevented_volume":"0","prevented_locked":"0",'
                   b'"trades_count":0}')
now = time.perf_counter_ns


def load_keys(path: str):
    env = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.strip().split("=", 1)
                env[k] = v
    return env.get("UPBIT_ACCESS_KEY", ""), env.get("UPBIT_SECRET_KEY", "")


# ----------------------------------------------------------------------------- HTTP 클라이언트
class IdiomaticClient:
    """requests.Session (업비트 공식 예제 방식)."""

    def __init__(self, base_url: str, fresh: bool):
        self.url, self.fresh = base_url + ORDER_TEST_PATH, fresh
        self.session = requests.Session()

    def build(self, ak, sk):
        return build_idiomatic(ORDER, ak, sk)

    def send(self, req):
        if self.fresh:
            self.session.close()
            self.session = requests.Session()
        r = self.session.post(self.url, data=req.body,
                              headers={"Authorization": req.authorization, "Content-Type": "application/json"})
        return r.status_code, r.content


class TunedClient:
    """http.client 지속 연결. requests의 추상화 계층을 걷어낸 버전."""

    def __init__(self, base_url: str, fresh: bool):
        scheme, host = base_url.split("://")
        self.fresh = fresh
        self._factory = (lambda: http.client.HTTPSConnection(host)) if scheme == "https" else \
            (lambda: http.client.HTTPConnection(*host.split(":")))
        self.conn = self._factory()
        self.signer = None

    def build(self, ak, sk):
        if self.signer is None:
            self.signer = TunedSigner(ak, sk)
        return self.signer.build(ORDER)

    def send(self, req):
        if self.fresh:
            self.conn.close()
            self.conn = self._factory()
        self.conn.request("POST", ORDER_TEST_PATH, req.body,
                          {"Authorization": req.authorization, "Content-Type": "application/json"})
        resp = self.conn.getresponse()
        return resp.status, resp.read()


IMPLS = {"idiomatic": IdiomaticClient, "tuned": TunedClient}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--impl", choices=IMPLS, required=True)
    ap.add_argument("--mode", choices=["sign", "loopback", "live", "live-cold"], required=True)
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--interval-ms", type=float, default=0, help="요청 간격(업비트 order-test 제한 8회/초)")
    ap.add_argument("--spin", action="store_true", help="요청 간격을 sleep 대신 busy-wait로 기다린다")
    ap.add_argument("--warm", action="store_true",
                    help="busy-wait 동안 더미 주문을 계속 만들어 캐시를 데워 둔다(전송하지 않음)")
    ap.add_argument("--port", type=int, default=18080)
    ap.add_argument("--env", default=".env")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    ak, sk = load_keys(a.env)
    if a.mode == "sign" and not ak:
        ak, sk = "A" * 40, "S" * 40  # 서명 측정은 실제 키가 없어도 된다
    base = f"http://127.0.0.1:{a.port}" if a.mode == "loopback" else f"https://{UPBIT_HOST}"
    client = IMPLS[a.impl](base, fresh=a.mode == "live-cold")
    impl = f"py-{a.impl}"

    rows = []
    next_at = now()
    for seq in range(a.n):
        if a.interval_ms:
            if a.warm:
                while now() < next_at:
                    client.build(ak, sk)
            elif a.spin:
                while now() < next_at:
                    pass
            else:
                wait = (next_at - now()) / 1e9
                if wait > 0:
                    time.sleep(wait)
            next_at += int(a.interval_ms * 1e6)
        t0 = now()
        req = client.build(ak, sk)
        t1 = now()
        if a.mode == "sign":
            status, raw = 201, SAMPLE_RESPONSE
        else:
            status, raw = client.send(req)
        t2 = now()
        result = parse_response(raw)
        t3 = now()
        if a.mode != "sign" and seq == 0 and not result.ok:
            print(f"[{impl}] first response {status}: {result.error}", file=sys.stderr)
        conn = "cold" if a.mode == "live-cold" or (a.mode != "sign" and seq == 0) else "warm"
        rows.append((impl, a.mode, seq, conn, status, t1 - t0, t2 - t1, t3 - t2, t3 - t0))

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["impl", "mode", "seq", "conn", "status", "sign_ns", "http_ns", "parse_ns", "total_ns"])
        w.writerows(rows)


if __name__ == "__main__":
    main()
