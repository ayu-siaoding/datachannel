#!/usr/bin/env python3
"""Al Brooks 价格行为波段扫描器。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from bar_counter import find_h_setup, two_leg_pullback
from pa_core import parse_daily_bars
from position_sizer import size_position
from signals import classify_context, detect_signal_at
from stop_loss import build_long_stop_plan

# 默认扫描池：宽基 ETF + 高流动性龙头
DEFAULT_UNIVERSE = {
    "510300.SH": "沪深300ETF",
    "510050.SH": "上证50ETF",
    "512890.SH": "红利ETF",
    "588000.SH": "科创50ETF",
    "600519.SH": "贵州茅台",
    "601318.SH": "中国平安",
    "600036.SH": "招商银行",
    "300750.SZ": "宁德时代",
    "002594.SZ": "比亚迪",
    "601899.SH": "紫金矿业",
}


def score_setup(ctx, h_setup, tlp, stop_plan) -> tuple[int, list[str]]:
    score = 50
    reasons: list[str] = []
    if ctx.always_in == "bull":
        score += 15
        reasons.append("Always In 多头 +15")
    elif ctx.always_in == "range":
        score -= 10
        reasons.append("震荡背景 -10")
    else:
        score -= 25
        reasons.append("空头背景 -25")

    if ctx.cycle in ("channel_up", "spike_up"):
        score += 10
        reasons.append(f"周期 {ctx.cycle} +10")

    if h_setup:
        if h_setup.count == 2:
            score += 20
            reasons.append("H2 买点 +20")
        elif h_setup.count == 1:
            score += 5
            reasons.append("H1 仅观察 +5")
        elif h_setup.count == 3:
            score += 8
            reasons.append("H3 区间底 +8")

    if tlp:
        score += 8
        reasons.append("两段式回调 +8")

    if stop_plan and stop_plan.risk_per_share / stop_plan.entry < 0.04:
        score += 5
        reasons.append("止损距离合理 +5")
    elif stop_plan and stop_plan.risk_per_share / stop_plan.entry > 0.06:
        score -= 10
        reasons.append("止损过宽 -10")

    return max(5, min(90, score)), reasons


def analyze_symbol(symbol: str, name: str, bars_raw: list) -> dict | None:
    bars = parse_daily_bars(bars_raw)
    if len(bars) < 30:
        return None

    ctx = classify_context(bars)
    h = find_h_setup(bars)
    tlp = two_leg_pullback(bars)
    last = bars[-1]

    if ctx.always_in == "bear":
        return {
            "symbol": symbol,
            "name": name,
            "action": "排除",
            "score": 0,
            "close": last.close,
            "context": ctx.always_in,
            "cycle": ctx.cycle,
            "note": ctx.note,
        }

    if ctx.always_in == "range" and "中部" in ctx.note:
        return {
            "symbol": symbol,
            "name": name,
            "action": "观望",
            "score": 20,
            "close": last.close,
            "context": ctx.always_in,
            "cycle": ctx.cycle,
            "note": ctx.note,
        }

    entry = last.close
    structure_stop = last.low
    if h:
        entry = max(h.entry, last.close)
        structure_stop = h.stop

    stop_plan = build_long_stop_plan(bars, entry, structure_stop, ctx.ema20)
    score, reasons = score_setup(ctx, h, tlp, stop_plan)

    action = "观望"
    if score >= 70 and h and h.count >= 2:
        action = "买入观察"
    elif score >= 55:
        action = "仅观察"

    pos = size_position(200, entry, stop_plan.initial_stop)

    return {
        "symbol": symbol,
        "name": name,
        "action": action,
        "score": score,
        "close": last.close,
        "date": last.date,
        "context": ctx.always_in,
        "cycle": ctx.cycle,
        "context_note": ctx.note,
        "h_setup": h.label if h else None,
        "h_quality": h.quality if h else None,
        "two_leg": bool(tlp),
        "entry": entry,
        "stop": stop_plan.initial_stop,
        "risk_pct": round(stop_plan.risk_per_share / entry * 100, 2),
        "target_mm": stop_plan.target_measure,
        "target_swing": stop_plan.target_swing,
        "trail": stop_plan.trail_rule,
        "score_reasons": reasons,
        "sample_shares_200w": pos["shares"],
    }


def load_data_dir(data_dir: Path) -> dict[str, list]:
    out: dict[str, list] = {}
    for p in data_dir.glob("*.json"):
        sym = p.stem
        out[sym] = json.loads(p.read_text())
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Al Brooks 波段扫描")
    p.add_argument("--data-dir", type=Path, help="日K JSON 目录，文件名如 510300.SH.json")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    args = p.parse_args()

    if not args.data_dir or not args.data_dir.exists():
        print("请提供 --data-dir（含 Longbridge candlesticks JSON）", file=sys.stderr)
        print("示例: python3 scanner.py --data-dir ./sample_data", file=sys.stderr)
        sys.exit(1)

    dataset = load_data_dir(args.data_dir)
    results = []
    for sym, name in DEFAULT_UNIVERSE.items():
        raw = dataset.get(sym)
        if not raw:
            continue
        r = analyze_symbol(sym, name, raw)
        if r:
            results.append(r)

    results.sort(key=lambda x: x.get("score", 0), reverse=True)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return

    print("=" * 60)
    print("Al Brooks 价格行为波段扫描")
    print("=" * 60)
    if not results:
        print("无数据。请先写入 sample_data/*.json")
        return

    for r in results:
        print(f"\n[{r['action']}] {r['symbol']} {r['name']}  分={r['score']}")
        print(f"  收盘 {r['close']} | 背景 {r['context']}/{r['cycle']}")
        if r.get("h_setup"):
            print(f"  数K线: {r['h_setup']} ({r['h_quality']})")
        if r.get("stop"):
            print(f"  入场≈{r['entry']} 止损={r['stop']} 风险={r['risk_pct']}%")
            print(f"  目标 MM={r.get('target_mm')} 前高={r.get('target_swing')}")
        print(f"  {r.get('context_note', '')}")


if __name__ == "__main__":
    main()
