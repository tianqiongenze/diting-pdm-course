"""生成课堂用合成数据（脱敏，可复现）。

产物（默认写入 data/）：
    assets.csv          1200 台设备
    metrics_90d.csv     1200 × 90 天指标
    alerts.csv          5000 条历史告警（含误报标记）
    spares.csv          300 条备件
    workorders.csv      800 条工单
    waveforms/*.csv     20 组波形（4 类轴承故障 + 正常）

用法：
    python tools/gen_course_data.py --assets 1200 --days 90 --seed 42
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITES = ["A", "B", "C"]
TYPES = ["电机", "风机", "泵", "减速机", "压缩机"]
LINES = ["1号线", "2号线", "3号线", "总装", "焊装"]
BEARINGS = ["6208", "6309", "6311", "NU310"]


def gen_assets(n: int, rng: random.Random, out: Path) -> list[dict]:
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "asset_id": f"EQ-{rng.choice(SITES)}-{i:04d}",
            "name": f"{rng.choice(TYPES)}{i:03d}",
            "type": rng.choice(TYPES),
            "line": rng.choice(LINES),
            "criticality": rng.choice(["A", "A", "B", "B", "C"]),
            "rated_power_kw": rng.choice([7.5, 11, 15, 22, 30, 45, 55]),
            "bearing_model": rng.choice(BEARINGS),
            "commissioned": f"20{rng.randint(15, 23)}-{rng.randint(1, 12):02d}",
        })
    with (out / "assets.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return rows


def gen_metrics(assets: list[dict], days: int, rng: random.Random, out: Path) -> None:
    with (out / "metrics_90d.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["asset_id", "date", "vib_rms_mm_s", "vib_baseline_mm_s", "kurtosis",
                    "temp_c", "temp_baseline_c", "current_dev_pct", "trend_pct_per_day",
                    "zone_c", "zone_d", "degraded"])
        for a in assets:
            base = round(rng.uniform(1.2, 3.2), 2)
            temp_base = round(rng.uniform(38, 55), 1)
            # 10% 设备有明显退化趋势
            slope = -rng.uniform(0.2, 1.2) if rng.random() < 0.1 else -rng.uniform(0.0, 0.15)
            for d in range(days):
                drift = max(0.0, -slope) * d * rng.uniform(0.6, 1.4)
                w.writerow([
                    a["asset_id"], f"D{d + 1:03d}",
                    round(base + drift * rng.uniform(0.8, 1.2), 3),
                    base,
                    round(4.0 + drift * rng.uniform(1.0, 3.0) + rng.gauss(0, 0.2), 3),
                    round(temp_base + drift * rng.uniform(2.0, 6.0) + rng.gauss(0, 0.6), 2),
                    temp_base,
                    round(rng.gauss(0, 4) + drift * 8, 2),
                    round(slope * rng.uniform(0.8, 1.2), 3),
                    4.5, 7.1,
                    "false",
                ])


def gen_alerts(assets: list[dict], n: int, rng: random.Random, out: Path) -> None:
    with (out / "alerts.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["alert_id", "asset_id", "level", "raised_at", "is_false_positive", "reason_code"])
        for i in range(n):
            w.writerow([
                f"AL-{i + 1:05d}", rng.choice(assets)["asset_id"],
                rng.choices(["red", "orange", "yellow"], weights=[1, 3, 6])[0],
                f"D{rng.randint(1, 90):03d}",
                "true" if rng.random() < 0.93 else "false",   # 真实误报率约 93%
                rng.choice(["", "", "", "baseline_drift", "sensor_fault", "single_peak"]),
            ])


def gen_spares(assets: list[dict], n: int, rng: random.Random, out: Path) -> None:
    with (out / "spares.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["part_code", "name", "stock", "lead_time_days", "unit_price"])
        for i in range(n):
            w.writerow([
                f"SP-{i + 1:04d}",
                rng.choice(["轴承", "联轴器", "密封件", "皮带", "润滑油", "传感器"]),
                rng.randint(0, 20), rng.randint(1, 15), rng.choice([120, 380, 900, 2400, 6800]),
            ])


def gen_workorders(assets: list[dict], n: int, rng: random.Random, out: Path) -> None:
    with (out / "workorders.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["workorder_id", "asset_id", "type", "status", "created_at", "closed_at", "cost"])
        for i in range(n):
            created = rng.randint(1, 90)
            closed = created + rng.randint(1, 10)
            w.writerow([
                f"WO-{i + 1:05d}", rng.choice(assets)["asset_id"],
                rng.choice(["corrective", "preventive", "inspection"]),
                "closed" if closed <= 90 else "open",
                f"D{created:03d}", f"D{min(closed, 90):03d}",
                rng.randint(800, 42000),
            ])


def gen_waveforms(n: int, rng: random.Random, out: Path) -> None:
    wdir = out / "waveforms"
    wdir.mkdir(exist_ok=True)
    fs, secs = 12800, 1
    faults = ["normal", "BPFO", "BPFI", "BSF", "FTF"]
    for i in range(n):
        kind = faults[i % len(faults)]
        rows = []
        for k in range(fs * secs):
            t = k / fs
            v = 0.6 * math.sin(2 * math.pi * 30 * t) + rng.gauss(0, 0.08)
            if kind != "normal":
                f0 = {"BPFO": 107.0, "BPFI": 162.0, "BSF": 69.0, "FTF": 11.4}[kind]
                amp = 0.35 if i < 12 else 0.05
                v += amp * math.sin(2 * math.pi * f0 * t) + 0.6 * amp * math.sin(2 * math.pi * 2 * f0 * t)
            rows.append(f"{v:.5f}")
        (wdir / f"wf_{i + 1:02d}_{kind}.csv").write_text("sample\n" + "\n".join(rows), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", type=int, default=1200)
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--alerts", type=int, default=5000)
    ap.add_argument("--spares", type=int, default=300)
    ap.add_argument("--workorders", type=int, default=800)
    ap.add_argument("--waveforms", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default="data")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)

    assets = gen_assets(args.assets, rng, out)
    gen_metrics(assets, args.days, rng, out)
    gen_alerts(assets, args.alerts, rng, out)
    gen_spares(assets, args.spares, rng, out)
    gen_workorders(assets, args.workorders, rng, out)
    gen_waveforms(args.waveforms, rng, out)

    print(f"生成完成 → {out}")
    print(f"  设备 {args.assets} 台 / 指标 {args.assets * args.days} 行 / 告警 {args.alerts} 条")
    print(f"  备件 {args.spares} 条 / 工单 {args.workorders} 条 / 波形 {args.waveforms} 组")


if __name__ == "__main__":
    main()
