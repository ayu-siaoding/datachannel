#!/usr/bin/env python3
"""
每日开盘：资金偏向哪些板块 + 板块内哪些个股更有机会涨。

- 美股：Yahoo 行业 ETF + 钟摆/蔡森/永泉
- A股：行业龙头池 yfinance + 同一套三层（基准 510300）
- both：合并一份报告

用法:
  python3 tools/daily_open_flow_and_picks.py --market both
  python3 tools/daily_open_flow_and_picks.py --market cn --save reports/daily_cn.md
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

from cn_open_market import cn_market_pendulum, rank_cn_sectors, scan_cn_picks
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
    base += max(0, 4 - sector_rank)
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


def _section_market(
    title: str,
    pendulum,
    bench_label: str,
    bench_ret1: float,
    bench_ret5: float,
    sector_rows: list[dict],
    picks: list[dict],
    sector_table_header: str,
) -> list[str]:
    lines = [
        f"## {title}",
        f"- 钟摆：一年分位 **{pendulum.price_percentile_1y:.0%}** → {pendulum.zone} / {pendulum.posture}",
        f"- {pendulum.note}",
        f"- {bench_label} 近1日 {bench_ret1*100:.2f}% | 近5日 {bench_ret5*100:.2f}%",
        "",
        sector_table_header,
    ]
    for i, s in enumerate(sector_rows, 1):
        if "etf" in s:
            lines.append(
                f"| {i} | {s['sector']} | {s['etf']} | {s['ret5_pct']} | {s['rs5_pct']} | {s['vol_ratio']} | {s['heat']} |"
            )
        else:
            lines.append(
                f"| {i} | {s['sector']} | {s['sample']} | {s['ret5_pct']} | {s['rs5_pct']} | {s['vol_ratio']} | {s['heat']} |"
            )
    lines.extend(["", "### 板块内个股机会", ""])
    lines.append("| 机会分 | 板块 | 代码 | 结论 | 永泉分 | 蔡森信号 | 止损参考 |")
    lines.append("|--------|------|------|------|--------|----------|----------|")
    for p in picks[:15]:
        sig = "；".join(p["caisen"][:2]) if p["caisen"] else "-"
        lines.append(
            f"| {p['opportunity_score']} | {p['sector']} | {p['symbol']} | {p['overall']} | "
            f"{p['yongquan_score']} | {sig} | {p['stop']} |"
        )
    return lines


def format_report_us(sector_rows, picks, spy_ret1, spy_ret5) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    mkt = market_pendulum()
    lines = [f"# 每日开盘报告（美股） {now}", "", "> 研究用途，非投资建议。", ""]
    lines += _section_market(
        "1. 大盘与板块（美股）",
        mkt,
        "SPY",
        spy_ret1,
        spy_ret5,
        sector_rows,
        picks,
        "| 排名 | 板块 | ETF | 近5日% | 相对基准(5日) | 量比 | 热度 |\n|------|------|-----|--------|--------------|------|------|",
    )
    lines += ["", "### 操作提示", "- 钟摆贪婪→小仓；只做热度前3板块；蔡森放量再首批。", ""]
    return "\n".join(lines)


def format_report_cn(sector_rows, picks, b1, b5) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    mkt = cn_market_pendulum()
    lines = [f"# 每日开盘报告（A股） {now}", "", "> 研究用途，非投资建议。主力净额可再用 tdx 交叉验证。", ""]
    lines += _section_market(
        "1. 大盘与板块（A股）",
        mkt,
        "510300",
        b1,
        b5,
        sector_rows,
        picks,
        "| 排名 | 板块 | 样本数 | 近5日% | 相对沪深300(5日) | 量比 | 热度 |\n|------|------|--------|--------|------------------|------|------|",
    )
    lines += [
        "",
        "### 操作提示",
        "- A股开盘 9:25 后看板块是否延续；政策主线优先（见 A股与美股投资逻辑对比笔记）。",
        "- Agent 可追加 tdx：`通达信行业板块涨幅排名前十` + `主力净流入排名前十`。",
        "",
    ]
    return "\n".join(lines)


def format_report_both(us_s, us_p, us_r1, us_r5, cn_s, cn_p, cn_r1, cn_r5) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# 每日开盘报告（A股 + 美股） {now}",
        "",
        "> 研究用途，非投资建议。",
        "",
        "---",
        "",
    ]
    lines.append(format_report_cn(cn_s, cn_p, cn_r1, cn_r5).split("\n", 3)[-1])
    lines.append("\n---\n")
    lines.append(format_report_us(us_s, us_p, us_r1, us_r5).split("\n", 3)[-1])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="每日开盘板块资金与个股机会")
    parser.add_argument("--market", choices=["us", "cn", "both"], default="both")
    parser.add_argument("--top-sectors", type=int, default=5)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--save", type=str, default="", help="保存 Markdown 路径")
    args = parser.parse_args()

    out_us = out_cn = None
    us_s = us_p = cn_s = cn_p = None
    us_r1 = us_r5 = cn_r1 = cn_r5 = 0.0

    if args.market in ("us", "both"):
        us_s, us_r1, us_r5 = rank_us_sectors(args.top_sectors)
        us_p = scan_us_picks(us_s)
        out_us = format_report_us(us_s, us_p, us_r1, us_r5)

    if args.market in ("cn", "both"):
        cn_s, cn_r1, cn_r5 = rank_cn_sectors(args.top_sectors)
        cn_p = scan_cn_picks(cn_s)
        out_cn = format_report_cn(cn_s, cn_p, cn_r1, cn_r5)

    if args.json:
        payload = {}
        if out_us:
            payload["us"] = {"sectors": us_s, "picks": us_p, "pendulum": market_pendulum().__dict__}
        if out_cn:
            payload["cn"] = {"sectors": cn_s, "picks": cn_p, "pendulum": cn_market_pendulum().__dict__}
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    else:
        if args.market == "both":
            print(format_report_both(us_s, us_p, us_r1, us_r5, cn_s, cn_p, cn_r1, cn_r5))
        elif args.market == "us":
            print(out_us)
        else:
            print(out_cn)

    if args.save:
        path = Path(args.save)
        path.parent.mkdir(parents=True, exist_ok=True)
        if args.market == "both":
            text = format_report_both(us_s, us_p, us_r1, us_r5, cn_s, cn_p, cn_r1, cn_r5)
        elif args.market == "us":
            text = out_us or ""
        else:
            text = out_cn or ""
        path.write_text(text, encoding="utf-8")
        print(f"\n已保存: {path}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
