#!/usr/bin/env python3
"""
每日开盘：资金偏向哪些板块 + 板块内哪些个股更有机会涨。

美股：Yahoo 行业 ETF 相对强度 + 量能 + 钟摆/蔡森/永泉三层（复用 us_triple_layer_screen）。
A股：请配合 Cursor 里 tdx_wenda_quotes（见 docs/DAILY_OPEN_WORKFLOW.md）。

用法:
  python3 tools/daily_open_flow_and_picks.py
  python3 tools/daily_open_flow_and_picks.py --market us --save reports/daily_us.md
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from us_triple_layer_screen import market_pendulum, screen_symbol

US_SECTORS: dict[str, dict[str, object]] = {
    "科技": {"etf": "XLK", "watch": ["AAPL", "MSFT", "NVDA", "AMD", "AVGO", "MU", "QCOM", "ADBE", "CRM", "ORCL", "INTC", "TXN"]},
    "能源": {"etf": "XLE", "watch": ["XOM", "CVX", "COP", "SLB", "EOG", "OXY"]},
    "金融": {"etf": "XLF", "watch": ["JPM", "BAC", "GS", "MS", "V", "MA", "BRK-B"]},
    "医药": {"etf": "XLV", "watch": ["LLY", "UNH", "JNJ", "ABBV", "MRK", "PFE"]},
    "工业": {"etf": "XLI", "watch": ["CAT", "GE", "HON", "UPS", "RTX", "DE"]},
    "可选消费": {"etf": "XLY", "watch": ["AMZN", "TSLA", "HD", "MCD", "NKE", "BKNG"]},
    "必需消费": {"etf": "XLP", "watch": ["WMT", "COST", "PG", "KO", "PEP", "PM"]},
    "通信": {"etf": "XLC", "watch": ["META", "GOOGL", "NFLX", "DIS", "CMCSA", "T"]},
    "半导体(细分)": {"etf": "SMH", "watch": ["NVDA", "TSM", "AVGO", "AMD", "MU", "LRCX", "AMAT", "ASML", "QCOM", "INTC"]},
    "材料": {"etf": "XLB", "watch": ["LIN", "APD", "FCX", "NEM", "SHW"]},
}


def _etf_flow_score(etf: str, spy_ret1: float, spy_ret5: float) -> dict | None:
    h = yf.Ticker(etf).history(period="3mo")
    if len(h) < 25:
        return None
    close, vol = h["Close"], h["Volume"]
    ret1 = float(close.iloc[-1] / close.iloc[-2] - 1) if len(close) > 1 else 0.0
    ret5 = float(close.iloc[-1] / close.iloc[-6] - 1) if len(close) > 6 else ret1
    vol_ratio = float(vol.iloc[-1] / vol.iloc[-21:-1].mean()) if vol.iloc[-21:-1].mean() else 1.0
    rs1 = ret1 - spy_ret1
    rs5 = ret5 - spy_ret5
    # 资金偏好：相对 SPY 强 + 放量
    heat = rs5 * 100 + rs1 * 50 + (vol_ratio - 1) * 8
    return {
        "etf": etf,
        "ret1_pct": round(ret1 * 100, 2),
        "ret5_pct": round(ret5 * 100, 2),
        "rs1_pct": round(rs1 * 100, 2),
        "rs5_pct": round(rs5 * 100, 2),
        "vol_ratio": round(vol_ratio, 2),
        "heat": round(heat, 2),
    }


def rank_us_sectors(top_n: int = 5) -> tuple[list[dict], float, float]:
    spy = yf.Ticker("SPY").history(period="3mo")
    spy_ret1 = float(spy["Close"].iloc[-1] / spy["Close"].iloc[-2] - 1)
    spy_ret5 = float(spy["Close"].iloc[-1] / spy["Close"].iloc[-6] - 1)
    rows: list[dict] = []
    for name, cfg in US_SECTORS.items():
        etf = str(cfg["etf"])
        m = _etf_flow_score(etf, spy_ret1, spy_ret5)
        if m:
            rows.append({"sector": name, **m})
    rows.sort(key=lambda x: -x["heat"])
    return rows[:top_n], spy_ret1, spy_ret5


def _stock_opportunity_score(row, sector_rank: int) -> float:
    base = row.yongquan.score
    if row.overall == "可分批买入":
        base += 10
    elif row.overall.startswith("观察"):
        base += 4
    elif "剔除" in row.overall:
        base -= 20
    elif "观望" in row.overall:
        base -= 5
    if row.caisen.volume_confirm:
        base += 3
    if row.caisen.false_breakout:
        base -= 15
    base += max(0, 4 - sector_rank)  # 最热板块加分
    return base


def scan_us_picks(sector_rows: list[dict], max_per_sector: int = 4) -> list[dict]:
    picks: list[dict] = []
    seen: set[str] = set()
    for rank, sec in enumerate(sector_rows):
        name = sec["sector"]
        watch = US_SECTORS[name]["watch"]  # type: ignore[index]
        scored: list[tuple[float, object]] = []
        for sym in watch:
            if sym in seen:
                continue
            row = screen_symbol(sym)
            if not row:
                continue
            opp = _stock_opportunity_score(row, rank)
            scored.append((opp, row))
        scored.sort(key=lambda x: -x[0])
        for opp, row in scored[:max_per_sector]:
            seen.add(row.symbol)
            picks.append(
                {
                    "sector": name,
                    "sector_rank": rank + 1,
                    "opportunity_score": round(opp, 1),
                    "symbol": row.symbol,
                    "price": row.price,
                    "overall": row.overall,
                    "caisen": row.caisen.signals,
                    "yongquan_score": row.yongquan.score,
                    "stop": row.yongquan.stop_hint,
                    "weight_hint_pct": row.suggested_weight_pct,
                }
            )
    picks.sort(key=lambda x: -x["opportunity_score"])
    return picks


def format_report(sector_rows: list[dict], picks: list[dict], spy_ret1: float, spy_ret5: float) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    mkt = market_pendulum()
    lines = [
        f"# 每日开盘报告（美股） {now}",
        "",
        "> 研究用途，非投资建议。A 股请见 docs/DAILY_OPEN_WORKFLOW.md 中 tdx 步骤。",
        "",
        "## 1. 大盘钟摆（SPY）",
        f"- 一年价位分位：**{mkt.price_percentile_1y:.0%}** → {mkt.zone} / {mkt.posture}",
        f"- {mkt.note}",
        f"- SPY 近1日 {spy_ret1*100:.2f}% | 近5日 {spy_ret5*100:.2f}%",
        "",
        "## 2. 开盘资金偏向板块（ETF 相对强度 + 量能）",
        "| 排名 | 板块 | ETF | 近5日% | 相对SPY(5日) | 量比 | 热度 |",
        "|------|------|-----|--------|--------------|------|------|",
    ]
    for i, s in enumerate(sector_rows, 1):
        lines.append(
            f"| {i} | {s['sector']} | {s['etf']} | {s['ret5_pct']} | {s['rs5_pct']} | {s['vol_ratio']} | {s['heat']} |"
        )
    lines.extend(["", "## 3. 板块内有机会个股（钟摆+蔡森+永泉）", ""])
    lines.append("| 机会分 | 板块 | 代码 | 结论 | 永泉分 | 蔡森信号 | 止损参考 |")
    lines.append("|--------|------|------|------|--------|----------|----------|")
    for p in picks[:20]:
        sig = "；".join(p["caisen"][:2]) if p["caisen"] else "-"
        lines.append(
            f"| {p['opportunity_score']} | {p['sector']} | {p['symbol']} | {p['overall']} | "
            f"{p['yongquan_score']} | {sig} | {p['stop']} |"
        )
    lines.extend(
        [
            "",
            "## 4. 今日怎么用",
            "1. **先看第 1 节**：钟摆贪婪 → 总仓打折；恐惧 → 可略积极。",
            "2. **第 2 节定板块**：只做热度前 3 板块，避免冷门逆资金。",
            "3. **第 3 节定个股**：优先「可分批买入」；「观察」等蔡森放量；「剔除/观望」不做。",
            "4. **开盘 30 分钟**：价不破前低 + 板块 ETF 仍强于 SPY 再下首批。",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="每日开盘板块资金与个股机会")
    parser.add_argument("--market", choices=["us", "cn", "both"], default="us")
    parser.add_argument("--top-sectors", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--save", type=str, default="", help="保存 Markdown 路径")
    args = parser.parse_args()

    if args.market in ("cn", "both"):
        print("A股：请用 Cursor Agent 调用 tdx `tdx_wenda_quotes`（流程见 docs/DAILY_OPEN_WORKFLOW.md）\n")

    if args.market not in ("us", "both"):
        return 0

    sectors, spy_ret1, spy_ret5 = rank_us_sectors(args.top_sectors)
    picks = scan_us_picks(sectors)

    if args.json:
        print(
            json.dumps(
                {
                    "market_pendulum": market_pendulum().__dict__,
                    "sectors": sectors,
                    "picks": picks,
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
        )
    else:
        print(format_report(sectors, picks, spy_ret1, spy_ret5))

    if args.save:
        path = Path(args.save)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(format_report(sectors, picks, spy_ret1, spy_ret5), encoding="utf-8")
        print(f"\n已保存: {path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
