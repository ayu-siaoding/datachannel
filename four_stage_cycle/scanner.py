#!/usr/bin/env python3
"""Ted Zhang 四阶段市场周期扫描器（周线）。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cycle_core import classify_cycle, parse_weekly_bars

DEFAULT_UNIVERSE = {
    "SMH.US": "半导体ETF",
    "NVDA.US": "英伟达",
    "GLD.US": "黄金ETF",
    "510300.SH": "沪深300ETF",
    "512890.SH": "红利ETF",
    "600519.SH": "贵州茅台",
    "BTC-USD": "比特币(需自备数据)",
}


def load_data_dir(data_dir: Path) -> dict[str, list]:
    out: dict[str, list] = {}
    for p in data_dir.glob("*.json"):
        out[p.stem] = json.loads(p.read_text())
    return out


def analyze_symbol(symbol: str, name: str, bars_raw: list) -> dict:
    bars = parse_weekly_bars(bars_raw)
    state = classify_cycle(bars)
    sma_fmt = {
        str(k): round(v, 3) if v is not None else None for k, v in state.sma.items()
    }
    return {
        "symbol": symbol,
        "name": name,
        "phase": state.phase,
        "phase_name": state.phase_name,
        "action": state.action,
        "confidence": state.confidence,
        "close": round(state.close, 3),
        "date": state.date,
        "ma_alignment": state.ma_alignment,
        "price_above_all_ma": state.price_above_all_ma,
        "higher_highs_lows": state.higher_highs_lows,
        "volume_breakout": state.volume_breakout,
        "sma": sma_fmt,
        "notes": state.notes,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="四阶段市场周期扫描（周线 SMA 10/20/30/40）")
    p.add_argument("--data-dir", type=Path, help="周线 JSON 目录，如 sample_data/")
    p.add_argument("--phase", type=int, choices=[1, 2, 3, 4], help="只显示指定阶段")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    args = p.parse_args()

    if not args.data_dir or not args.data_dir.exists():
        print("请提供 --data-dir（含 Longbridge 周线 candlesticks JSON）", file=sys.stderr)
        print("示例: python3 scanner.py --data-dir ./sample_data", file=sys.stderr)
        sys.exit(1)

    dataset = load_data_dir(args.data_dir)
    results = []
    for sym, name in DEFAULT_UNIVERSE.items():
        raw = dataset.get(sym)
        if not raw:
            continue
        r = analyze_symbol(sym, name, raw)
        if args.phase and r["phase"] != args.phase:
            continue
        results.append(r)

    # 第二阶段优先展示（唯一做多阶段）
    phase_order = {2: 0, 3: 1, 1: 2, 4: 3, 0: 4}
    results.sort(key=lambda x: (phase_order.get(x["phase"], 9), -x["confidence"]))

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    print("=" * 64)
    print("Ted Zhang 四阶段市场周期扫描（周线）")
    print("SMA: 10 / 20 / 30 / 40 周 | 仅第二阶段适合做多")
    print("=" * 64)
    if not results:
        print("无数据。请先写入 sample_data/*.json")
        return

    for r in results:
        print(f"\n[{r['action']}] {r['symbol']} {r['name']}")
        print(f"  阶段: {r['phase_name']} (P{r['phase']})  置信度={r['confidence']}")
        print(f"  收盘 {r['close']} @ {r['date']} | 均线排列={r['ma_alignment']}")
        print(
            f"  SMA10={r['sma']['10']} SMA20={r['sma']['20']} "
            f"SMA30={r['sma']['30']} SMA40={r['sma']['40']}"
        )
        for note in r.get("notes", []):
            print(f"  · {note}")


if __name__ == "__main__":
    main()
