"""전체 측정 실행: 구현별 측정을 라운드마다 번갈아 실행해 시간대별 네트워크 변동이 한쪽에 몰리지 않게 한다.

    python scripts/run_bench.py                 # sign, loopback, live, live-cold 전부
    python scripts/run_bench.py --modes sign loopback

결과: results/raw/<mode>/<impl>_r<round>.csv, results/env.json
업비트 order-test는 주문을 만들지 않는다. 요청 제한(초당 8회)보다 느리게 보낸다.
"""
import argparse
import csv
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
CPP = ROOT / "build" / "upbit_bench.exe"
MOCK = ROOT / "build" / "mock_server.exe"
RAW = ROOT / "results" / "raw"

IMPLS = {
    "py-idiomatic": [PY, str(ROOT / "python" / "bench.py"), "--impl", "idiomatic"],
    "py-tuned": [PY, str(ROOT / "python" / "bench.py"), "--impl", "tuned"],
    "cpp-curl": [str(CPP)],
}

# 실험 이름: (bench mode, 라운드 수, 라운드당 요청 수, 요청 간격 ms, 추가 인자)
PLAN = {
    "sign": ("sign", 3, 100_000, 0, []),
    "loopback": ("loopback", 4, 5_000, 0, []),
    "live": ("live", 10, 60, 150, []),
    "live-cold": ("live-cold", 5, 8, 300, []),
    # 주문 사이에 쉬는 동안 캐시/CPU 상태가 식는 영향: 같은 서명을 150ms 간격으로, sleep vs busy-wait
    "sign-idle": ("sign", 2, 150, 150, []),
    "sign-spin": ("sign", 2, 150, 150, ["--spin"]),
    "sign-warm": ("sign", 2, 150, 150, ["--warm"]),
}


def run_round(name: str, mode: str, impl: str, rnd: int, n: int, interval: float, extra: list) -> Path:
    out = RAW / name / f"{impl}_r{rnd}.csv"
    cmd = IMPLS[impl] + extra + ["--mode", mode, "--n", str(n), "--interval-ms", str(interval),
                         "--env", str(ROOT / ".env"), "--out", str(out)]
    subprocess.run(cmd, check=True, cwd=ROOT)
    return out


def statuses(path: Path):
    with open(path) as f:
        return [row["status"] for row in csv.DictReader(f)]


def record_env():
    def tool_version(cmd):
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.splitlines()[0].strip()
        except Exception:
            return ""

    import requests
    import ssl
    cache = (ROOT / "build" / "CMakeCache.txt")
    compiler = ""
    if cache.exists():
        for line in cache.read_text(errors="ignore").splitlines():
            if line.startswith("CMAKE_CXX_COMPILER:"):
                compiler = line.split("=", 1)[1]
    cpu = tool_version(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Processor).Name"])
    env = {
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "os": platform.platform(),
        "cpu": cpu,
        "python": platform.python_version(),
        "python_ssl": ssl.OPENSSL_VERSION,
        "requests": requests.__version__,
        "cxx_compiler": compiler,
        "cxx_libs": tool_version([str(CPP), "--version"]),
    }
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "env.json").write_text(json.dumps(env, indent=2, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modes", nargs="+", default=list(PLAN), choices=list(PLAN))
    a = ap.parse_args()
    if not CPP.exists():
        sys.exit("C++ build missing: run scripts\\build.bat first")
    record_env()

    for name in a.modes:
        mode, rounds, n, interval, extra = PLAN[name]
        mock = subprocess.Popen([str(MOCK)], stdout=subprocess.DEVNULL) if mode == "loopback" else None
        try:
            if mock:
                time.sleep(0.5)
            for rnd in range(rounds):
                for impl in IMPLS:
                    t = time.time()
                    out = run_round(name, mode, impl, rnd, n, interval, extra)
                    st = statuses(out)
                    bad = sum(s not in ("201", "400") for s in st)
                    print(f"{name:9s} r{rnd} {impl:12s} n={len(st)} invalid={bad} ({time.time() - t:.1f}s)", flush=True)
                    if mode.startswith("live") and bad > len(st) // 2:
                        sys.exit(f"{impl}: most live responses failed (status {set(st)}); check API key / allowed IP")
        finally:
            if mock:
                mock.terminate()


if __name__ == "__main__":
    main()
