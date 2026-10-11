#!/usr/bin/env python3
"""量好 · 题材好 · 板块好 — 共享打分（供美股/A股扫描引用）."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

# 题材标签（可扩展）
US_THEME: dict[str, tuple[str, str]] = {
    # symbol: (题材, 板块ETF)
    "MU": ("存储/HBM", "SOXX"),
    "SNDK": ("闪存", "SOXX"),
    "WDC": ("存储", "SOXX"),
    "STX": ("HDD", "SOXX"),
    "NVDA": ("AI算力", "SOXX"),
    "AVGO": ("AI/定制硅", "SOXX"),
    "AMD": ("AI算力", "SOXX"),
    "MRVL": ("定制硅/光", "SOXX"),
    "SMCI": ("AI服务器", "SOXX"),
    "LITE": ("光/OCS", "SOXX"),
    "COHR": ("光/OCS", "SOXX"),
    "GLW": ("光纤", "XLK"),
    "AAOI": ("光模块", "SOXX"),
    "CRWD": ("AI安全", "HACK"),
    "PANW": ("AI安全", "HACK"),
    "FTNT": ("AI安全", "HACK"),
    "ZS": ("AI安全/零信任", "HACK"),
    "S": ("AI安全", "HACK"),
    "OKTA": ("身份安全", "HACK"),
    "NET": ("边缘安全", "XLK"),
    "PLTR": ("AI应用", "XLK"),
    "GOOG": ("互联网/云", "XLC"),
    "META": ("互联网/AI", "XLC"),
    "MSFT": ("云/AI", "XLK"),
    "AAPL": ("消费电子", "XLK"),
    "AMZN": ("云/消费", "XLY"),
    "PEP": ("必需消费", "XLP"),
    "KO": ("必需消费", "XLP"),
    "PG": ("必需消费", "XLP"),
    "MRK": ("医药防御", "XLV"),
    "JNJ": ("医药防御", "XLV"),
    "NVO": ("医药", "XLV"),
    "GEV": ("电力设备", "XLI"),
    "VST": ("电力", "XLU"),
    "CEG": ("电力", "XLU"),
    "VRT": ("数据中心电力", "XLK"),
}

ASHARE_THEME: dict[str, tuple[str, str]] = {
    # yahoo: (题材, 板块代理ETF或指数)
    "300502.SZ": ("光模块", "光通讯"),
    "300308.SZ": ("光模块", "光通讯"),
    "300394.SZ": ("光器件", "光通讯"),
    "002281.SZ": ("光/OCS", "光通讯"),
    "300620.SZ": ("光/OCS", "光通讯"),
    "601869.SS": ("光纤", "光通讯"),
    "600487.SS": ("光纤", "光通讯"),
    "600522.SS": ("光纤海缆", "光通讯"),
    "000063.SZ": ("通信设备", "科技"),
    "002475.SZ": ("消费电子", "科技"),
    "688561.SS": ("AI安全", "网安"),
    "300454.SZ": ("AI安全/云", "网安"),
    "002439.SZ": ("AI安全", "网安"),
    "002212.SZ": ("AI安全", "网安"),
    "300369.SZ": ("AI安全", "网安"),
    "688023.SS": ("AI安全", "网安"),
    "601360.SS": ("互联网安全", "网安"),
    "601318.SS": ("保险红利", "金融"),
    "601088.SS": ("煤炭红利", "红利"),
    "600036.SS": ("银行红利", "金融"),
    "600900.SS": ("水电红利", "红利"),
    "601899.SS": ("有色资源", "周期"),
    "300750.SZ": ("新能源", "新能源"),
    "002594.SZ": ("新能源车", "新能源"),
    "600089.SS": ("变压器/电力", "电力设备"),
    "002028.SZ": ("电力设备出海", "电力设备"),
    "688676.SS": ("变压器/AIDC", "电力设备"),
}


def grade(score: int) -> str:
    if score >= 2:
        return "好"
    if score >= 1:
        return "中"
    return "弱"


def volume_score(hist: pd.DataFrame, chg: float) -> tuple[int, str, float]:
    """量好：相对量 + 量价配合（不奖励放量大阳）."""
    v = hist["Volume"]
    if len(v) < 25:
        return 0, "量数据不足", 1.0
    vol = float(v.iloc[-1])
    v20 = float(v.iloc[-21:-1].mean())
    rvol = vol / v20 if v20 > 0 else 1.0
    pts = 0
    note = f"rvol={rvol:.2f}"
    if rvol >= 1.5 and -1 <= chg <= 2.5:
        pts = 2
        note += " 温和放量"
    elif rvol >= 1.2 and chg <= 2.5:
        pts = 1
        note += " 量能尚可"
    elif rvol < 0.7 and chg < -2:
        pts = 0
        note += " 缩量偏弱"
    elif 0.8 <= rvol <= 1.3 and -3 <= chg <= 1.5:
        pts = 1
        note += " 缩量整理可挂"
    else:
        pts = 0
        note += " 量价一般"
    if rvol >= 1.3 and chg > 3:
        pts = 0
        note = f"rvol={rvol:.2f} 放量大阳不计好量"
    return pts, note, round(rvol, 2)


def theme_score(symbol: str, market: str = "US") -> tuple[int, str, str]:
    table = US_THEME if market == "US" else ASHARE_THEME
    # normalize ashare keys
    key = symbol
    if market == "A" and symbol in table:
        key = symbol
    elif market == "A":
        # try with suffix already
        key = symbol
    info = table.get(key) or table.get(symbol.upper() if market == "US" else symbol)
    if not info:
        return 0, "未标注题材", "—"
    theme, board = info
    # 核心题材给 2，一般给 1
    core = {"存储/HBM", "光/OCS", "光模块", "AI安全", "AI安全/云", "AI安全/零信任", "变压器/电力", "变压器/AIDC", "保险红利"}
    pts = 2 if theme in core or "OCS" in theme or "安全" in theme or "光模块" in theme else 1
    return pts, theme, board


_sector_cache: dict[str, float | None] = {}


def sector_rel_5d(etf: str, benchmark: str = "SPY") -> float | None:
    if etf in _sector_cache:
        return _sector_cache[etf]
    if etf in {"光通讯", "网安", "科技", "金融", "红利", "周期", "新能源", "电力设备"}:
        _sector_cache[etf] = None
        return None
    try:
        eh = yf.Ticker(etf).history(period="2mo", auto_adjust=True)
        bh = yf.Ticker(benchmark).history(period="2mo", auto_adjust=True)
        if eh.empty or bh.empty:
            _sector_cache[etf] = None
            return None
        ec, bc = eh["Close"].dropna(), bh["Close"].dropna()
        # align last 6 trading days on overlapping index
        joined = pd.concat([ec.rename("e"), bc.rename("b")], axis=1).dropna()
        if len(joined) < 6:
            _sector_cache[etf] = None
            return None
        er = float(joined["e"].iloc[-1] / joined["e"].iloc[-6] - 1) * 100
        br = float(joined["b"].iloc[-1] / joined["b"].iloc[-6] - 1) * 100
        rel = er - br
        _sector_cache[etf] = rel
        return rel
    except Exception:
        _sector_cache[etf] = None
        return None


# A股板块代理成分（相对上证）
A_BOARD_PROXIES: dict[str, list[str]] = {
    "光通讯": ["300502.SZ", "300308.SZ", "300394.SZ", "002281.SZ"],
    "网安": ["688561.SS", "300454.SZ", "002439.SZ", "002212.SZ"],
    "金融": ["601318.SS", "600036.SS", "601166.SS"],
    "红利": ["601088.SS", "600900.SS", "601318.SS"],
    "新能源": ["300750.SZ", "002594.SZ", "601012.SS"],
    "电力设备": ["600089.SS", "002028.SZ", "688676.SS"],
    "周期": ["601899.SS"],
    "科技": ["000063.SZ", "002475.SZ", "688981.SS"],
}


def ashare_board_rel(board: str, closes: dict[str, pd.Series], bench: pd.Series | None) -> float | None:
    syms = A_BOARD_PROXIES.get(board) or []
    rets = []
    for s in syms:
        ser = closes.get(s)
        if ser is None or len(ser) < 6:
            continue
        rets.append(float(ser.iloc[-1] / ser.iloc[-6] - 1) * 100)
    if not rets or bench is None or len(bench) < 6:
        return None
    br = float(bench.iloc[-1] / bench.iloc[-6] - 1) * 100
    return float(np.mean(rets) - br)


def sector_score(rel: float | None) -> tuple[int, str]:
    if rel is None:
        return 0, "板块相对强弱缺数据"
    if rel >= 1.5:
        return 2, f"板块5日相对大盘+{rel:.1f}%"
    if rel >= 0:
        return 1, f"板块5日不弱({rel:+.1f}%)"
    if rel >= -2:
        return 0, f"板块略弱({rel:+.1f}%)"
    return 0, f"板块偏弱({rel:+.1f}%)"


def enrich(
    symbol: str,
    hist: pd.DataFrame,
    chg: float,
    market: str = "US",
    ashare_closes: dict[str, pd.Series] | None = None,
    ashare_bench: pd.Series | None = None,
) -> dict[str, Any]:
    v_pts, v_note, rvol = volume_score(hist, chg)
    t_pts, theme, board = theme_score(symbol, market)
    if market == "US":
        rel = sector_rel_5d(board) if board != "—" else None
    else:
        rel = ashare_board_rel(board, ashare_closes or {}, ashare_bench)
    s_pts, s_note = sector_score(rel)

    # 三好合计；题材未标注不给满分
    total = v_pts + t_pts + s_pts
    missing = sum(1 for p in (v_pts, t_pts, s_pts) if p == 0)
    return {
        "量": grade(v_pts),
        "题材": grade(t_pts) if theme != "未标注题材" else "弱",
        "板块": grade(s_pts),
        "量分": v_pts,
        "题材分": t_pts,
        "板块分": s_pts,
        "三好合计": total,
        "三好缺几": missing,
        "题材名": theme,
        "板块名": board,
        "rvol": rvol,
        "量注": v_note,
        "板块注": s_note,
        "三好标签": f"量{grade(v_pts)}/题材{grade(t_pts) if theme != '未标注题材' else '弱'}/板块{grade(s_pts)}",
    }
