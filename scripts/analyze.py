"""results/raw/*의 측정값을 요약표(results/summary.md, summary.json)와 차트(results/*.png)로 만든다."""
import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib
import matplotlib.ticker

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "results" / "raw"
OUT = ROOT / "results"

IMPLS = ["py-idiomatic", "py-tuned", "cpp-curl"]
LABEL = {"py-idiomatic": "Python (requests + PyJWT)", "py-tuned": "Python (stdlib, tuned)", "cpp-curl": "C++ (libcurl + OpenSSL)"}
# 201(주문 가능) 또는 400(잔액 부족 등 주문 검증 거절): 둘 다 인증+주문 검증을 거친 정상 왕복이다.
# 401(인증), 429(요청 제한), 5xx는 제외한다.
VALID_STATUS = ("201", "400")
STAGES = ["sign_ns", "http_ns", "parse_ns", "total_ns"]

# 참조 팔레트(dataviz palette.md) 범주색 앞 세 슬롯: 세 계열 모두 색각이상 구분 검증된 조합
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
})


def load(mode):
    data = defaultdict(lambda: defaultdict(list))  # impl -> key -> values
    for f in sorted((RAW / mode).glob("*.csv")):
        with open(f) as fh:
            for r in csv.DictReader(fh):
                if r["status"] not in VALID_STATUS:
                    data[r["impl"]]["non201"].append(1)
                    continue
                for s in STAGES:
                    data[r["impl"]][f"{r['conn']}:{s}"].append(int(r[s]))
    return data


def stats(values):
    v = np.asarray(values, dtype=float) / 1e3  # us
    return {"n": int(v.size), "mean": v.mean(), "p50": np.percentile(v, 50), "p90": np.percentile(v, 90),
            "p99": np.percentile(v, 99), "p99.9": np.percentile(v, 99.9), "max": v.max()}


def fmt_us(x):
    return f"{x / 1e3:,.2f} ms" if x >= 1000 else f"{x:,.1f} µs"


def table(rows, title):
    lines = [f"### {title}", "", "| 구현 | 구간 | n | 평균 | p50 | p90 | p99 | p99.9 | 최대 |", "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for impl, stage, s in rows:
        lines.append(f"| {LABEL[impl]} | {stage} | {s['n']:,} | " + " | ".join(
            fmt_us(s[k]) for k in ["mean", "p50", "p90", "p99", "p99.9", "max"]) + " |")
    return "\n".join(lines) + "\n"


MODE_TITLE = {
    ("sign", "warm"): "1. 주문 생성 + 응답 파싱 (네트워크 없음)",
    ("loopback", "warm"): "2. 로컬 mock 서버 왕복 (연결 재사용)",
    ("live", "warm"): "3. 업비트 order-test (연결 재사용)",
    ("live", "cold"): "4a. 업비트 order-test (각 실행의 첫 요청, 새 연결)",
    ("live-cold", "cold"): "4b. 업비트 order-test (요청마다 새 연결)",
    ("sign-idle", "warm"): "5a. 주문 생성, 150ms 간격 (간격 동안 sleep)",
    ("sign-spin", "warm"): "5b. 주문 생성, 150ms 간격 (간격 동안 busy-wait)",
    ("sign-warm", "warm"): "5c. 주문 생성, 150ms 간격 (간격 동안 더미 주문으로 캐시 데우기)",
}
STAGE_NAME = {"sign_ns": "주문 생성(서명)", "http_ns": "HTTP 왕복", "parse_ns": "응답 파싱", "total_ns": "합계"}


def stacked_medians(data, conn, stages, title, path, unit=1.0, unit_label="µs"):
    fig, ax = plt.subplots(figsize=(8, 2.8))
    impls = [i for i in IMPLS if data.get(i)][::-1]
    left = np.zeros(len(impls))
    colors = dict(zip(stages, SERIES))
    for s in stages:
        vals = np.array([np.median(data[i][f"{conn}:{s}"]) / 1e3 / unit for i in impls])
        ax.barh([LABEL[i] for i in impls], vals, left=left, color=colors[s], height=0.55,
                edgecolor=SURFACE, linewidth=2, label=STAGE_NAME[s])
        left += vals
    for y, total in enumerate(left):
        ax.text(total, y, f"  {total:,.1f} {unit_label}", va="center", color=INK, fontsize=9)
    ax.set_xlim(0, left.max() * 1.22)
    ax.set_xlabel(f"구간별 중앙값 ({unit_label})")
    ax.set_title(title, loc="left", fontsize=11, color=INK)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def cdf(data, conn, title, path):
    fig, ax = plt.subplots(figsize=(8, 3.6))
    for impl, color in zip(IMPLS, SERIES):
        v = np.sort(np.asarray(data[impl][f"{conn}:total_ns"]) / 1e6)
        if not v.size:
            continue
        ax.plot(v, np.arange(1, v.size + 1) / v.size, color=color, linewidth=2, label=LABEL[impl])
    ax.set_xlabel("주문 1건 전체 지연 (ms)")
    ax.set_ylabel("누적 비율")
    ax.set_title(title, loc="left", fontsize=11, color=INK)
    ax.legend(loc="lower right", frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def decomposition_chart(summary, baseline, path):
    """실서버 주문 1건(중앙값)을 클라이언트 처리 / 네트워크 왕복 / 거래소 처리로 나눈다.

    클라이언트 처리 = 서명 + 파싱(실서버 측정) + HTTP 클라이언트 스택(loopback 왕복 중앙값),
    네트워크 = TCP connect 중앙값, 거래소 처리 = 나머지.
    """
    parts = ["클라이언트 처리", "네트워크 왕복 (TCP connect)", "거래소 처리 (나머지)"]
    impls = IMPLS[::-1]
    rows = []
    for i in impls:
        live = summary["live"][i]
        total = live["warm:total_ns"]["p50"] / 1e3
        client = (live["warm:sign_ns"]["p50"] + live["warm:parse_ns"]["p50"]
                  + summary["loopback"][i]["warm:http_ns"]["p50"]) / 1e3
        net = baseline["tcp_connect"]["p50_ms"]
        rows.append((client, net, total - client - net))
    fig, ax = plt.subplots(figsize=(8, 3.0))
    left = np.zeros(len(impls))
    for k, (name, color) in enumerate(zip(parts, SERIES)):
        vals = np.array([r[k] for r in rows])
        ax.barh([LABEL[i] for i in impls], vals, left=left, color=color, height=0.55,
                edgecolor=SURFACE, linewidth=2, label=name)
        left += vals
    for y, r in enumerate(rows):
        ax.text(left[y], y, f"  {sum(r):.1f} ms (클라이언트 {r[0]:.2f} ms)", va="center", fontsize=9, color=INK)
    ax.set_xlim(0, left.max() * 1.45)
    ax.set_xlabel("주문 1건 지연 중앙값 (ms)")
    ax.set_title("업비트 order-test 주문 1건의 구성 (연결 재사용)", loc="left", fontsize=11, color=INK)
    ax.grid(axis="y", visible=False)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.28), ncol=3, frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def idle_chart(path):
    """같은 서명 코드의 p50/p99: 연속 실행 vs 주문 사이 150ms sleep vs 150ms busy-wait."""
    conds = [("sign-idle", "150ms 간격, sleep"), ("sign-spin", "150ms 간격, busy-wait"),
             ("sign-warm", "150ms 간격, 더미 주문으로 데우기"), ("sign", "연속 실행")]
    data = {m: load(m) for m, _ in conds}
    impls = IMPLS[::-1]
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.2), sharey=True)
    h = 0.2
    for ax, (q, qname) in zip(axes, [(50, "p50"), (99, "p99")]):
        for k, ((m, label), color) in enumerate(zip(conds, SERIES)):
            ys = np.arange(len(impls)) + (1.5 - k) * h
            vals = [np.percentile(data[m][i]["warm:sign_ns"], q) / 1e3 for i in impls]
            ax.barh(ys, vals, height=h, color=color, edgecolor=SURFACE, linewidth=2, label=label)
            for y, v in zip(ys, vals):
                ax.text(v, y, f" {v:,.1f}", va="center", fontsize=8, color=INK2)
        ax.set_xscale("log")
        ax.set_xlim(1, 1500)
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f"{x:g}"))
        ax.set_title(f"주문 생성(서명) {qname} (µs, 로그 축)", loc="left", fontsize=10, color=INK)
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(np.arange(len(impls)), [LABEL[i] for i in impls])
    fig.legend(*axes[0].get_legend_handles_labels(), loc="lower center", ncol=4, frameon=False, fontsize=8)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    plt.rcParams["font.family"] = ["Malgun Gothic", "DejaVu Sans"]
    summary, md = {}, ["# 측정 요약", ""]
    env = json.loads((OUT / "env.json").read_text(encoding="utf-8")) if (OUT / "env.json").exists() else {}
    if env:
        md += [f"- 측정 시각(UTC): {env.get('measured_at')}", f"- CPU: {env.get('cpu')} / OS: {env.get('os')}",
               f"- Python {env.get('python')} ({env.get('python_ssl')}), requests {env.get('requests')}",
               f"- C++: MSVC, {env.get('cxx_libs')}", ""]

    for mode, conns in [("sign", ["warm"]), ("loopback", ["warm"]), ("live", ["warm", "cold"]), ("live-cold", ["cold"]),
                        ("sign-idle", ["warm"]), ("sign-spin", ["warm"]),
                        ("sign-warm", ["warm"])]:
        if not (RAW / mode).exists():
            continue
        data = load(mode)
        summary[mode] = {}
        for conn in conns:
            rows = []
            stages = ["sign_ns", "parse_ns"] if mode.startswith("sign") else STAGES
            for impl in IMPLS:
                summary[mode].setdefault(impl, {})
                for s in stages:
                    vals = data[impl][f"{conn}:{s}"]
                    if vals:
                        st = stats(vals)
                        summary[mode][impl][f"{conn}:{s}"] = st
                        rows.append((impl, STAGE_NAME[s], st))
                summary[mode][impl]["non201"] = len(data[impl]["non201"])
            if rows:
                md.append(table(rows, MODE_TITLE[(mode, conn)]))

        if mode == "sign":
            stacked_medians(data, "warm", ["sign_ns", "parse_ns"], "주문 생성 + 응답 파싱 (네트워크 없음)", OUT / "sign.png")
        elif mode == "loopback":
            stacked_medians(data, "warm", ["sign_ns", "http_ns", "parse_ns"],
                            "로컬 mock 서버 왕복 포함 (클라이언트 스택 비용)", OUT / "loopback.png")
        elif mode == "live":
            cdf(data, "warm", "업비트 order-test 전체 지연 분포 (연결 재사용)", OUT / "live_cdf.png")

    if (OUT / "baseline_rtt.json").exists() and {"loopback", "live"} <= summary.keys():
        decomposition_chart(summary, json.loads((OUT / "baseline_rtt.json").read_text()), OUT / "live.png")
    if all((RAW / m).exists() for m in ("sign", "sign-idle", "sign-spin", "sign-warm")):
        idle_chart(OUT / "idle.png")

    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
    (OUT / "summary.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
