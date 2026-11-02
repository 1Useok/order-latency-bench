"""requests의 HTTP 왕복 비용 중 프록시 환경 조회가 차지하는 몫을 잰다(loopback mock 서버 대상).

requests.Session은 trust_env=True(기본)일 때 요청마다 환경변수/레지스트리에서 프록시 설정을 찾는다.
같은 요청을 trust_env=True/False로 보내 차이를 보고, results/requests_trust_env.json에 남긴다.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
from upbit_order import ORDER, build_idiomatic  # noqa: E402

URL = "http://127.0.0.1:18080/v1/orders/test"
N, WARMUP = 5000, 200


def measure(trust_env: bool):
    s = requests.Session()
    s.trust_env = trust_env
    req = build_idiomatic(ORDER, "A" * 40, "S" * 40)
    headers = {"Authorization": req.authorization, "Content-Type": "application/json"}
    for _ in range(WARMUP):
        s.post(URL, data=req.body, headers=headers)
    v = []
    for _ in range(N):
        t = time.perf_counter_ns()
        s.post(URL, data=req.body, headers=headers)
        v.append(time.perf_counter_ns() - t)
    v = np.asarray(v) / 1e3
    return {"n": N, "p50_us": float(np.percentile(v, 50)), "p99_us": float(np.percentile(v, 99))}


def main():
    mock = subprocess.Popen([str(ROOT / "build" / "mock_server.exe")], stdout=subprocess.DEVNULL)
    try:
        time.sleep(0.5)
        result = {"trust_env=True (default)": measure(True), "trust_env=False": measure(False)}
    finally:
        mock.terminate()
    (ROOT / "results" / "requests_trust_env.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
