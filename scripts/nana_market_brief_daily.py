#!/usr/bin/env python3
"""Daily US market brief (娜娜话美股-style structured data).

Covers macro proxies, index/sector tape, SOX technical bands, Mag7 vs SPY,
AI hardware / storage / software relative strength, and SPX candle shape.

Usage:
  python3 scripts/nana_market_brief_daily.py
  python3 scripts/nana_market_brief_daily.py --json
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ALERTS = Path("/workspace/scripts/alerts")
LEVELS_LATEST = ALERTS / "spx_spy_levels_latest.txt"

INDICES = {
    "标普500": "^GSPC",
    "纳斯达克": "^IXIC",
    "道指": "^DJI",
}

MACRO = {
    "10年美债收益率(^TNX)": "^TNX",
    "WTI原油": "CL=F",
    "VIX": "^VIX",
    "美元DX": "DX-Y.NYB",
}

SECTORS = {
    "半导体SOXX": "SOXX",
    "科技XLK": "XLK",
    "软件IGV": "IGV",
    "网络安全HACK": "HACK",
    "能源XLE": "XLE",
}

MAG7 = {
    "AAPL": "AAPL",
    "MSFT": "MSFT",
    "GOOGL": "GOOGL",
    "AMZN": "AMZN",
    "META": "META",
    "NVDA": "NVDA",
    "TSLA": "TSLA",
}

AI_HARDWARE = {
    "NVDA": "NVDA",
    "AVGO": "AVGO",
    "AMD": "AMD",
    "MU": "MU",
    "STX": "STX",
    "WDC": "WDC",
    "MRVL": "MRVL",
    "SMCI": "SMCI",
}

SOX_RESIST_BAND = (12400.0, 12600.0)
FRED_SERIES = {
    "失业率(UNRATE)": "UNRATE",
    "10Y国债(DGS10)": "DGS10",
}


def fetch_fred_last(series_id: str) -> tuple[str | None, float | None]:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        lines = [ln for ln in text.strip().splitlines() if ln and not ln.startswith("DATE")]
        if len(lines) < 2:
            return None, None
        last = lines[-1].split(",")
        if len(last) < 2 or last[1] in (".", ""):
            for row in reversed(lines[1:]):
                parts = row.split(",")
                if len(parts) >= 2 and parts[1] not in (".", ""):
                    return parts[0], float(parts[1])
            return None, None
        return last[0], float(last[1])
    except Exception:
        return None, None


def history_closes(symbols: list[str], period: str = "6mo") -> pd.DataFrame:
    if not symbols:
        return pd.DataFrame()
    raw = yf.download(
        symbols,
        period=period,
        group_by="ticker",
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    if raw.empty:
        return pd.DataFrame()
    if len(symbols) == 1:
        return raw[["Close"]].rename(columns={"Close": symbols[0]})
    closes = {}
    for sym in symbols:
        try:
            closes[sym] = raw[sym]["Close"]
        except Exception:
            continue
    return pd.DataFrame(closes).dropna(how="all")


def pct_change(series: pd.Series, days: int = 1) -> float | None:
    if series is None or len(series) < days + 1:
        return None
    a, b = float(series.iloc[-1 - days]), float(series.iloc[-1])
    if a == 0:
        return None
    return (b - a) / a * 100.0


def last_ohlc(ticker: str) -> dict | None:
    h = yf.Ticker(ticker).history(period="10d", auto_adjust=True)
    if h.empty:
        return None
    row = h.iloc[-1]
    prev = h.iloc[-2] if len(h) >= 2 else row
    return {
        "date": h.index[-1].strftime("%Y-%m-%d"),
        "open": float(row["Open"]),
        "high": float(row["High"]),
        "low": float(row["Low"]),
        "close": float(row["Close"]),
        "prev_close": float(prev["Close"]),
        "chg_pct": (float(row["Close"]) - float(prev["Close"])) / float(prev["Close"]) * 100.0
        if float(prev["Close"])
        else 0.0,
    }


def classify_candle(o: float, h: float, l: float, c: float) -> str:
    rng = max(h - l, 1e-9)
    body = abs(c - o)
    body_ratio = body / rng
    upper = h - max(o, c)
    lower = min(o, c) - l
    if body_ratio < 0.15 and upper / rng > 0.35 and lower / rng > 0.35:
        return "十字星/纺锤（多空博弈、追高意愿弱）"
    if c > o and body_ratio > 0.5:
        return "阳线实体"
    if c < o and body_ratio > 0.5:
        return "阴线实体"
    if c > o:
        return "小阳/上影偏长" if upper > body else "小阳"
    if c < o:
        return "小阴/上影偏长" if upper > body else "小阴"
    return "平收"


def sox_commentary(sox_close: float, sox_hist: pd.Series) -> str:
    lo, hi = SOX_RESIST_BAND
    parts = [f"SOX 收盘 **{sox_close:,.0f}**"]
    if sox_close >= hi:
        parts.append(f"已站上原强阻力区 **{lo:,.0f}–{hi:,.0f}**，偏多（关注前高）")
    elif sox_close >= lo:
        parts.append(f"处于 **{lo:,.0f}–{hi:,.0f}** 阻力带内，突破确认中")
    else:
        parts.append(f"仍在 **{lo:,.0f}–{hi:,.0f}** 下方，硬件情绪待确认")
    if len(sox_hist) >= 126:
        ytd = pct_change(sox_hist, min(126, len(sox_hist) - 1))
        if ytd is not None:
            parts.append(f"近6个月涨跌约 **{ytd:+.1f}%**")
    return "；".join(parts) + "。"


def spy_forward_pe() -> float | None:
    try:
        info = yf.Ticker("SPY").info
        for key in ("forwardPE", "trailingPE"):
            v = info.get(key)
            if v and v == v:
                return float(v)
    except Exception:
        pass
    return None


def read_gex_snippet() -> str | None:
    if not LEVELS_LATEST.exists():
        return None
    text = LEVELS_LATEST.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    spx_line = next((ln for ln in lines if ln.startswith("SPX ") and "|" in ln), None)
    return spx_line


def build_report() -> tuple[str, dict]:
    now = datetime.now(timezone.utc)
    generated_at = now.strftime("%Y-%m-%d %H:%M UTC")
    date_slug = now.strftime("%Y-%m-%d")

    index_rows = []
    for label, sym in INDICES.items():
        ohlc = last_ohlc(sym)
        if not ohlc:
            continue
        index_rows.append(
            {
                "name": label,
                "symbol": sym,
                "close": ohlc["close"],
                "chg_pct": round(ohlc["chg_pct"], 2),
                "session": ohlc["date"],
            }
        )

    spx_ohlc = last_ohlc("^GSPC")
    spx_shape = ""
    if spx_ohlc:
        spx_shape = classify_candle(
            spx_ohlc["open"], spx_ohlc["high"], spx_ohlc["low"], spx_ohlc["close"]
        )

    macro_rows = []
    for label, sym in MACRO.items():
        ohlc = last_ohlc(sym)
        if not ohlc:
            continue
        macro_rows.append(
            {
                "name": label,
                "symbol": sym,
                "last": round(ohlc["close"], 3 if sym == "^TNX" else 2),
                "chg_pct": round(ohlc["chg_pct"], 2),
            }
        )

    fred_rows = []
    for label, sid in FRED_SERIES.items():
        dt, val = fetch_fred_last(sid)
        if val is not None:
            fred_rows.append({"name": label, "series": sid, "as_of": dt, "value": val})

    all_syms = list({*SECTORS.values(), *MAG7.values(), *AI_HARDWARE.values(), "SPY", "^SOX"})
    closes = history_closes(all_syms, period="6mo")
    spy_s = closes["SPY"] if "SPY" in closes else None
    spy_1d = pct_change(spy_s, 1) if spy_s is not None else None

    def rel_vs_spy(sym: str) -> dict:
        s = closes[sym] if sym in closes else None
        if s is None or spy_s is None:
            return {"symbol": sym, "chg_1d": None, "rel_vs_spy": None, "close": None}
        c1 = pct_change(s, 1)
        rel = (c1 - spy_1d) if c1 is not None and spy_1d is not None else None
        return {
            "symbol": sym,
            "close": round(float(s.iloc[-1]), 2),
            "chg_1d": round(c1, 2) if c1 is not None else None,
            "rel_vs_spy": round(rel, 2) if rel is not None else None,
        }

    sector_rows = [{"label": k, **rel_vs_spy(v)} for k, v in SECTORS.items()]
    mag7_rows = [{"label": k, **rel_vs_spy(v)} for k, v in MAG7.items()]
    ai_rows = [{"label": k, **rel_vs_spy(v)} for k, v in AI_HARDWARE.items()]

    sox_s = closes["^SOX"] if "^SOX" in closes else None
    sox_close = float(sox_s.iloc[-1]) if sox_s is not None and len(sox_s) else None
    sox_text = sox_commentary(sox_close, sox_s) if sox_close and sox_s is not None else ""

    pe = spy_forward_pe()
    pe_text = ""
    if pe:
        pe_text = f"SPY 市盈率（Yahoo 代理）：远期约 **{pe:.1f}x**（视频口径常引用标普远期 ~19x，以卖方一致预期为准）。"

    hw_avg_rel = [
        r["rel_vs_spy"] for r in ai_rows if r.get("rel_vs_spy") is not None
    ]
    igv_rel = next((r["rel_vs_spy"] for r in sector_rows if r["label"] == "软件IGV"), None)
    hw_vs_sw = ""
    if hw_avg_rel and igv_rel is not None:
        avg = sum(hw_avg_rel) / len(hw_avg_rel)
        if avg > igv_rel + 0.3:
            hw_vs_sw = "AI 硬件相对软件 **偏强**（硬件跑赢 SPY 均值 > 软件），与「硬件主线 / 软件跷跷板」叙事一致。"
        elif avg < igv_rel - 0.3:
            hw_vs_sw = "软件今日相对 **更强**，硬件分化（勿当作趋势反转，看 SOX 结构）。"
        else:
            hw_vs_sw = "硬件与软件相对 SPY **接近**，板块跷跷板不明显。"

    gex = read_gex_snippet()

    md_lines = [
        f"# 美股日更数据简报（娜娜结构）",
        f"",
        f"生成：**{generated_at}** · 数据源：Yahoo Finance + FRED（延迟/免费代理，非实时终端）",
        f"",
        f"## 1. 三大指数（收盘）",
        f"",
        f"| 指数 | 收盘 | 日涨跌 |",
        f"|------|------|--------|",
    ]
    for r in index_rows:
        md_lines.append(f"| {r['name']} | {r['close']:,.2f} | {r['chg_pct']:+.2f}% |")

    md_lines.extend(
        [
            "",
            "## 2. 宏观与风险偏好（价格代理）",
            "",
            "| 指标 | 最新 | 日涨跌 |",
            "|------|------|--------|",
        ]
    )
    for r in macro_rows:
        md_lines.append(f"| {r['name']} | {r['last']} | {r['chg_pct']:+.2f}% |")

    if fred_rows:
        md_lines.extend(["", "**FRED 最新公布：**"])
        for r in fred_rows:
            md_lines.append(f"- {r['name']}：{r['value']}（截至 {r['as_of']}）")
        md_lines.append(
            "- 非农/CPI/Fed 加息概率需 CME FedWatch 或新闻稿；本脚本用 **收益率/油价/VIX** 作风险偏好代理。"
        )

    md_lines.extend(
        [
            "",
            "## 3. 标普技术面（日 K 形状）",
            "",
        ]
    )
    if spx_ohlc:
        md_lines.append(
            f"- 日期 **{spx_ohlc['date']}** · 收 **{spx_ohlc['close']:,.2f}** ({spx_ohlc['chg_pct']:+.2f}%)"
        )
        md_lines.append(
            f"- O/H/L/C：{spx_ohlc['open']:,.2f} / {spx_ohlc['high']:,.2f} / "
            f"{spx_ohlc['low']:,.2f} / {spx_ohlc['close']:,.2f}"
        )
        md_lines.append(f"- 解读：**{spx_shape}**")
    if pe_text:
        md_lines.append(f"- {pe_text}")

    md_lines.extend(["", "## 4. 费城半导体 / AI 硬件", "", sox_text, ""])
    md_lines.extend(["### 板块 ETF vs SPY（1 日）", "", "| 板块 | 收盘 | 日涨跌 | 相对 SPY |", "|------|------|--------|----------|"])
    for r in sector_rows:
        rel = f"{r['rel_vs_spy']:+.2f}%" if r.get("rel_vs_spy") is not None else "—"
        chg = f"{r['chg_1d']:+.2f}%" if r.get("chg_1d") is not None else "—"
        close = r.get("close") or "—"
        md_lines.append(f"| {r['label']} | {close} | {chg} | {rel} |")
    if hw_vs_sw:
        md_lines.append("")
        md_lines.append(hw_vs_sw)

    md_lines.extend(["", "## 5. Mag7", "", "| 股票 | 收盘 | 日涨跌 | 相对 SPY |", "|------|------|--------|----------|"])
    for r in sorted(mag7_rows, key=lambda x: x.get("rel_vs_spy") or -999, reverse=True):
        rel = f"{r['rel_vs_spy']:+.2f}%" if r.get("rel_vs_spy") is not None else "—"
        chg = f"{r['chg_1d']:+.2f}%" if r.get("chg_1d") is not None else "—"
        md_lines.append(f"| {r['label']} | {r.get('close', '—')} | {chg} | {rel} |")

    md_lines.extend(["", "## 6. AI 硬件 / 存储观察", "", "| 股票 | 收盘 | 日涨跌 | 相对 SPY |", "|------|------|--------|----------|"])
    for r in sorted(ai_rows, key=lambda x: x.get("rel_vs_spy") or -999, reverse=True):
        rel = f"{r['rel_vs_spy']:+.2f}%" if r.get("rel_vs_spy") is not None else "—"
        chg = f"{r['chg_1d']:+.2f}%" if r.get("chg_1d") is not None else "—"
        md_lines.append(f"| {r['label']} | {r.get('close', '—')} | {chg} | {rel} |")

    md_lines.extend(
        [
            "",
            "## 7. 期权 GEX 档位（若已跑 spx_spy_levels）",
            "",
            gex or "_尚未生成：先运行 `python3 scripts/spx_spy_levels_daily.py`_",
            "",
            "---",
            "脚本：`scripts/nana_market_brief_daily.py` · 结构对齐日更视频：宏观 → 指数 → 技术 → SOX/硬件 → Mag7 → 个股",
        ]
    )

    payload = {
        "generated_at": generated_at,
        "indices": index_rows,
        "macro": macro_rows,
        "fred": fred_rows,
        "spx": {**(spx_ohlc or {}), "candle_label": spx_shape},
        "spy_pe_proxy": pe,
        "sox": {"close": sox_close, "commentary": sox_text},
        "sectors": sector_rows,
        "mag7": mag7_rows,
        "ai_hardware": ai_rows,
        "hardware_vs_software_note": hw_vs_sw,
        "gex_snippet": gex,
    }
    return "\n".join(md_lines), payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    md, payload = build_report()
    now = datetime.now(timezone.utc)
    date_slug = now.strftime("%Y-%m-%d")
    time_slug = now.strftime("%H%M")

    ALERTS.mkdir(parents=True, exist_ok=True)
    (ALERTS / f"nana_market_brief_{date_slug}.md").write_text(md, encoding="utf-8")
    (ALERTS / f"nana_market_brief_{date_slug}_{time_slug}.md").write_text(md, encoding="utf-8")
    (ALERTS / "nana_market_brief_latest.md").write_text(md, encoding="utf-8")

    print(md)
    if args.json:
        jp = ALERTS / f"nana_market_brief_{date_slug}.json"
        jp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        (ALERTS / "nana_market_brief_latest.json").write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\n[written] {jp}")


if __name__ == "__main__":
    main()
