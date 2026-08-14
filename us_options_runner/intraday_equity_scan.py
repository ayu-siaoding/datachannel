#!/usr/bin/env python3
"""Print intraday equity pre-market checklist from YAML config.

Usage:
  python3 us_options_runner/intraday_equity_scan.py
  python3 us_options_runner/intraday_equity_scan.py --levels 485.50
"""

from __future__ import annotations

import argparse
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config" / "intraday_equity.yaml"


def load_config() -> dict:
    if yaml is None:
        raise SystemExit("pip install pyyaml")
    with CONFIG.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def print_levels(entry: float, shares: int, target_pct: tuple, stop_pct: tuple) -> None:
    t_lo, t_hi = target_pct
    s_lo, s_hi = stop_pct
    notional = entry * shares
    print(f"\n--- 40 股 @ ${entry:.2f} · 本金 ${notional:,.0f} ---")
    for label, pct in [("止盈低", t_lo), ("止盈高", t_hi), ("止损低", -s_lo), ("止损高", -s_hi)]:
        px = entry * (1 + pct)
        pnl = (px - entry) * shares
        print(f"  {label}: ${px:.2f}  ({pct:+.2%})  ≈ ${pnl:+,.0f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Intraday equity pre-market checklist")
    parser.add_argument(
        "--levels",
        type=float,
        nargs="+",
        metavar="PRICE",
        help="Compute stop/target prices for one or more entry prices",
    )
    args = parser.parse_args()
    cfg = load_config()

    print("=" * 60)
    print("大票日内 · 盘前 3 条筛选")
    print("=" * 60)
    for i, flt in enumerate(cfg["pre_market_filters"], 1):
        print(f"\n【筛选 {i}】{flt['name']}")
        for rule in flt["rules"]:
            print(f"  · {rule}")

    print("\n【熟悉名单 tier1】", ", ".join(s.replace(".US", "") for s in cfg["watchlist"]["tier1"]))
    t = cfg["trade"]
    r = cfg["risk"]
    print(f"\n【参数】≥${t['min_price_usd']} · {t['default_shares']} 股/单 · 最多 {t['max_trades_per_day']} 笔/天")
    print(f"【目标】+{r['target_pct'][0]:.1%}~+{r['target_pct'][1]:.1%}  ·  【止损】-{r['stop_pct'][0]:.1%}~-{r['stop_pct'][1]:.1%}")
    print(f"【日亏上限】${r['max_daily_loss_usd']}  ·  连亏 2 单停 {r['consecutive_loss_skip_days']} 天")

    print("\n【时段 · 北京】")
    for k, v in cfg["session_beijing"].items():
        print(f"  {k}: {v}")

    print("\n详细执行表 → docs/intraday_equity_playbook.md")

    shares = t["default_shares"]
    target = tuple(cfg["risk"]["target_pct"])
    stop = tuple(cfg["risk"]["stop_pct"])
    for price in args.levels or []:
        print_levels(price, shares, target, stop)


if __name__ == "__main__":
    main()
