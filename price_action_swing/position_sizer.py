#!/usr/bin/env python3
"""按实际风险（结构止损）反推仓位。"""

from __future__ import annotations

import argparse


# 账户最大回撤档 → (单笔风险%, 单笔仓位上限, 总仓上限)
PROFILES = {
    "5": {"50": (0.004, 0.15, 0.40), "200": (0.0035, 0.12, 0.35), "1000": (0.003, 0.10, 0.30)},
    "8": {"50": (0.006, 0.20, 0.50), "200": (0.005, 0.15, 0.45), "1000": (0.004, 0.12, 0.40)},
    "10": {"50": (0.008, 0.25, 0.60), "200": (0.007, 0.20, 0.55), "1000": (0.005, 0.15, 0.50)},
}


def nearest_bucket(capital_wan: float) -> str:
    if capital_wan <= 80:
        return "50"
    if capital_wan <= 500:
        return "200"
    return "1000"


def size_position(
    capital_wan: float,
    entry: float,
    stop: float,
    dd: str = "8",
    used_pct: float = 0.0,
    lot: int = 100,
) -> dict:
    bucket = nearest_bucket(capital_wan)
    risk_pct, max_pos, max_total = PROFILES[dd][bucket]
    capital = capital_wan * 10_000
    risk_per_share = max(entry - stop, entry * 0.005)
    risk_budget = capital * risk_pct

    by_risk = int(risk_budget / risk_per_share / lot) * lot
    by_pos = int(capital * max_pos / entry / lot) * lot
    remain = max(0.0, max_total - used_pct)
    by_total = int(capital * remain / entry / lot) * lot
    shares = max(0, min(by_risk, by_pos, by_total))
    notional = shares * entry
    r_multiple_to_2 = entry + 2 * risk_per_share

    return {
        "capital_wan": capital_wan,
        "dd": dd,
        "bucket": bucket,
        "entry": entry,
        "stop": stop,
        "risk_per_share": round(risk_per_share, 4),
        "risk_budget": round(risk_budget, 0),
        "shares": shares,
        "notional": round(notional, 0),
        "notional_pct": round(notional / capital * 100, 2),
        "target_2r": round(r_multiple_to_2, 3),
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Al Brooks 波段：结构止损反推仓位")
    p.add_argument("--capital", type=float, required=True, help="总资金（万元）")
    p.add_argument("--entry", type=float, required=True, help="计划入场价")
    p.add_argument("--stop", type=float, required=True, help="结构止损价")
    p.add_argument("--dd", choices=["5", "8", "10"], default="8")
    p.add_argument("--used-pct", type=float, default=0.0, help="已用仓位比例")
    args = p.parse_args()

    r = size_position(args.capital, args.entry, args.stop, args.dd, args.used_pct)
    print(f"回撤档 -{r['dd']}% | 资金档 {r['bucket']}万")
    print(f"实际风险/股: {r['risk_per_share']:.4f} | 风险预算: {r['risk_budget']:,.0f} 元")
    print(f"建议: {r['shares']} 股 | 金额 {r['notional']:,.0f} 元 ({r['notional_pct']}%)")
    print(f"2R 目标价: {r['target_2r']}")
    if r["shares"] == 0:
        print("结果为 0：止损过宽或已接近总仓上限。")


if __name__ == "__main__":
    main()
