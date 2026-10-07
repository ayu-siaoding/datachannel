#!/usr/bin/env python3
"""A 股每日开盘：板块热度（yfinance）+ 三层选股。tdx 主力净额可在 Agent 中补充校验。"""
from __future__ import annotations

import sys
from pathlib import Path

import yfinance as yf

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from us_triple_layer_screen import pendulum_layer, screen_symbol

# 行业龙头观察池（代码带 .SS / .SZ）
CN_SECTORS: dict[str, list[str]] = {
    "半导体": ["688981.SS", "603501.SS", "688012.SS", "002371.SZ", "603986.SS", "600584.SS"],
    "新能源": ["300750.SZ", "002594.SZ", "601012.SS", "300124.SZ", "002460.SZ", "688005.SS"],
    "白酒消费": ["600519.SS", "000858.SZ", "000568.SZ", "600809.SS", "000596.SZ"],
    "银行": ["601398.SS", "600036.SS", "000001.SZ", "601288.SS", "601166.SS"],
    "医药": ["600276.SS", "000538.SZ", "300760.SZ", "603259.SS", "300122.SZ"],
    "AI算力/硬件": ["601138.SS", "000977.SZ", "300308.SZ", "002230.SZ", "688111.SS"],
    "券商": ["600030.SS", "601688.SS", "300059.SZ", "601211.SS", "000776.SZ"],
    "军工": ["600893.SS", "000768.SZ", "600760.SS", "002179.SZ", "600150.SS"],
    "汽车": ["601633.SS", "000625.SZ", "601238.SS", "002594.SZ", "600104.SS"],
    "地产链": ["000002.SZ", "600048.SS", "001979.SZ", "600585.SS", "000876.SZ"],
}


def _bench_returns() -> tuple[float, float]:
    """沪深300ETF 510300 作基准。"""
    h = yf.Ticker("510300.SS").history(period="3mo")
    if len(h) < 6:
        h = yf.Ticker("000300.SS").history(period="6mo")
    if len(h) < 2:
        return 0.0, 0.0
    ret1 = float(h["Close"].iloc[-1] / h["Close"].iloc[-2] - 1)
    ret5 = float(h["Close"].iloc[-1] / h["Close"].iloc[-6] - 1) if len(h) > 6 else ret1
    return ret1, ret5


def _sector_metrics(name: str, symbols: list[str], bench_ret1: float, bench_ret5: float) -> dict | None:
    rets1, rets5, vol_ratios = [], [], []
    for sym in symbols:
        h = yf.Ticker(sym).history(period="3mo")
        if len(h) < 25:
            continue
        c, v = h["Close"], h["Volume"]
        rets1.append(float(c.iloc[-1] / c.iloc[-2] - 1))
        rets5.append(float(c.iloc[-1] / c.iloc[-6] - 1))
        vma = float(v.iloc[-21:-1].mean())
        if vma:
            vol_ratios.append(float(v.iloc[-1] / vma))
    if not rets5:
        return None
    ret1 = sum(rets1) / len(rets1)
    ret5 = sum(rets5) / len(rets5)
    vol_ratio = sum(vol_ratios) / len(vol_ratios) if vol_ratios else 1.0
    rs1, rs5 = ret1 - bench_ret1, ret5 - bench_ret5
    heat = rs5 * 100 + rs1 * 50 + (vol_ratio - 1) * 8
    return {
        "sector": name,
        "ret1_pct": round(ret1 * 100, 2),
        "ret5_pct": round(ret5 * 100, 2),
        "rs1_pct": round(rs1 * 100, 2),
        "rs5_pct": round(rs5 * 100, 2),
        "vol_ratio": round(vol_ratio, 2),
        "heat": round(heat, 2),
        "sample": len(rets5),
    }


def cn_market_pendulum():
    h = yf.Ticker("510300.SS").history(period="1y")
    if len(h) < 60:
        h = yf.Ticker("000300.SS").history(period="1y")
    return pendulum_layer(h, {})


def rank_cn_sectors(top_n: int = 5) -> tuple[list[dict], float, float]:
    b1, b5 = _bench_returns()
    rows: list[dict] = []
    for name, syms in CN_SECTORS.items():
        m = _sector_metrics(name, syms, b1, b5)
        if m:
            rows.append(m)
    rows.sort(key=lambda x: -x["heat"])
    return rows[:top_n], b1, b5


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


def scan_cn_picks(sector_rows: list[dict], max_per_sector: int = 4) -> list[dict]:
    picks: list[dict] = []
    seen: set[str] = set()
    for rank, sec in enumerate(sector_rows):
        name = sec["sector"]
        for sym in CN_SECTORS.get(name, []):
            if sym in seen:
                continue
            row = screen_symbol(sym)
            if not row:
                continue
            opp = _stock_opportunity_score(row, rank)
            seen.add(sym)
            picks.append(
                {
                    "sector": name,
                    "sector_rank": rank + 1,
                    "opportunity_score": round(opp, 1),
                    "symbol": sym,
                    "price": row.price,
                    "overall": row.overall,
                    "caisen": row.caisen.signals,
                    "yongquan_score": row.yongquan.score,
                    "stop": row.yongquan.stop_hint,
                    "weight_hint_pct": row.suggested_weight_pct,
                }
            )
        # trim per sector
    # regroup trim
    by_sec: dict[str, list] = {}
    for p in picks:
        by_sec.setdefault(p["sector"], []).append(p)
    trimmed: list[dict] = []
    for sec in sector_rows:
        name = sec["sector"]
        lst = sorted(by_sec.get(name, []), key=lambda x: -x["opportunity_score"])[:max_per_sector]
        trimmed.extend(lst)
    trimmed.sort(key=lambda x: -x["opportunity_score"])
    return trimmed
