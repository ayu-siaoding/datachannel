#!/usr/bin/env python3
"""仓位计算器：按账户资金、回撤档、买入价、止损幅度估算可买数量。"""

from __future__ import annotations

import argparse


# risk_per_trade, max_pos_pct, max_total_pct
PROFILES = {
    "5": {  # 目标回撤约 -5%
        "50": (0.004, 0.15, 0.40),
        "200": (0.0035, 0.12, 0.35),
        "1000": (0.003, 0.10, 0.30),
    },
    "8": {
        "50": (0.006, 0.20, 0.50),
        "200": (0.005, 0.15, 0.45),
        "1000": (0.004, 0.12, 0.40),
    },
    "10": {
        "50": (0.008, 0.25, 0.60),
        "200": (0.007, 0.20, 0.55),
        "1000": (0.005, 0.15, 0.50),
    },
}


def nearest_bucket(capital_wan: float) -> str:
    if capital_wan <= 80:
        return "50"
    if capital_wan <= 500:
        return "200"
    return "1000"


def main() -> None:
    p = argparse.ArgumentParser(description="ETF/龙头波段仓位计算")
    p.add_argument("--capital", type=float, required=True, help="总资金（万元）")
    p.add_argument("--dd", choices=["5", "8", "10"], default="8", help="目标最大回撤档")
    p.add_argument("--price", type=float, required=True, help="计划买入价")
    p.add_argument("--stop", type=float, default=0.03, help="止损幅度，ETF默认0.03")
    p.add_argument("--used-pct", type=float, default=0.0, help="当前已用仓位比例，如0.2")
    args = p.parse_args()

    bucket = nearest_bucket(args.capital)
    risk_pct, max_pos, max_total = PROFILES[args.dd][bucket]
    capital = args.capital * 10_000

    risk_budget = capital * risk_pct
    shares_by_risk = int(risk_budget / (args.price * args.stop) / 100) * 100
    shares_by_cap = int(capital * max_pos / args.price / 100) * 100
    remain_pct = max(0.0, max_total - args.used_pct)
    shares_by_total = int(capital * remain_pct / args.price / 100) * 100
    shares = max(0, min(shares_by_risk, shares_by_cap, shares_by_total))
    notional = shares * args.price

    print(f"资金档: {bucket}万附近 | 回撤档: -{args.dd}%")
    print(f"单笔风险预算: {risk_budget:,.0f} 元 ({risk_pct*100:.2f}%)")
    print(f"单笔仓位上限: {max_pos*100:.0f}% | 总仓上限: {max_total*100:.0f}%")
    print(f"剩余可开仓比例: {remain_pct*100:.1f}%")
    print(f"建议买入: {shares} 股/份 | 金额约 {notional:,.0f} 元 ({notional/capital*100:.1f}%)")
    if shares == 0:
        print("结果为0：已接近总仓上限，或单价/止损导致手数不足。")


if __name__ == "__main__":
    main()
