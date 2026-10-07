#!/usr/bin/env python3
"""究公司 · 快速基本面（永泉适应率/PEG + 六维代理分 + 人工补全模板）.

Reads optional scan output (light_comm_dual_latest.json) or a ticker list.

Usage:
  python3 scripts/jiu_company_daily.py
  python3 scripts/jiu_company_daily.py --symbols MU,COHR,300502.SZ
  python3 scripts/jiu_company_daily.py --from-scan
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

ALERTS = Path("/workspace/scripts/alerts")
SCAN_JSON = ALERTS / "light_comm_dual_latest.json"

# 主题内「看人/组织/周期」备忘（非实时，需人工复核）
CURATED = {
    "MU": "⑤存储/HBM景气；⑥周期股波动大，勿深套摊平；③寡占但价格周期明显",
    "COHR": "③光模块+材料整合；⑤CPO 长期受益；⑥并购整合期",
    "LITE": "③高端光器件；⑤AI 光互联",
    "300502.SZ": "③光模块龙头之一；⑤AI 数据中心光模块；④看毛利率与北美客户占比",
    "300308.SZ": "③光模块；⑤同上；⑥估值常高于二线",
    "ASTS": "③频谱+MNO 合作模式；④仍亏损；⑥卫星主题高波动",
    "SWKS": "③射频前端；⑤手机+IoT；④周期与苹果链相关",
    "AVGO": "③宽护城河+收购；④现金流强；⑤AI 定制 ASIC",
    "NVDA": "③算力生态；⑥钟摆右端时只减不追",
}


def safe_float(x) -> float | None:
    try:
        if x is None or x != x:
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def adapt_rate(price: float, eps: float | None) -> float | None:
    if not eps or eps <= 0:
        return None
    return price / (eps * 4)


def peg_note(peg: float | None, pe: float | None, rev_g: float | None) -> str:
    if peg is not None and peg > 0:
        if peg <= 1:
            return f"PEG≈{peg:.2f}（≤1 偏合理）"
        if peg <= 1.5:
            return f"PEG≈{peg:.2f}（1～1.5 观察）"
        return f"PEG≈{peg:.2f}（>1.5 偏贵）"
    if pe and rev_g and rev_g > 0:
        impl = pe / (rev_g * 100)
        return f"PEG代理≈{impl:.2f}（PE/收入增速）"
    return "PEG 缺数据"


def proxy_scores(info: dict, adapt: float | None, sector: str) -> dict:
    margin = safe_float(info.get("profitMargins"))
    rev_g = safe_float(info.get("revenueGrowth"))
    de = safe_float(info.get("debtToEquity"))
    fcf = safe_float(info.get("freeCashflow"))

    s3 = 3
    if margin is not None:
        if margin >= 0.25:
            s3 = 5
        elif margin >= 0.12:
            s3 = 4
        elif margin >= 0.05:
            s3 = 3
        else:
            s3 = 2

    s4 = 3
    if fcf is not None and fcf > 0 and (rev_g is None or rev_g > 0):
        s4 = 4
    if fcf is not None and fcf < 0:
        s4 = 2
    if de is not None and de > 200:
        s4 = max(2, s4 - 1)

    s5 = 3
    if rev_g is not None:
        if rev_g >= 0.15:
            s5 = 5
        elif rev_g >= 0.08:
            s5 = 4
        elif rev_g >= 0:
            s5 = 3
        else:
            s5 = 2

    return {
        "③壁垒(代理)": s3,
        "④财务(代理)": s4,
        "⑤趋势(代理)": s5,
        "proxy_total": s3 + s4 + s5,
        "note": "①②⑥须人工；代理满分15，≥12 基本面尚可配合技术面",
    }


def fetch_one(symbol: str) -> dict:
    t = yf.Ticker(symbol)
    info = t.info or {}
    hist = t.history(period="5d", auto_adjust=True)
    price = float(hist["Close"].iloc[-1]) if not hist.empty else safe_float(info.get("currentPrice"))
    eps = safe_float(info.get("trailingEps"))
    adapt = adapt_rate(price, eps) if price else None
    pe = safe_float(info.get("forwardPE") or info.get("trailingPE"))
    peg = safe_float(info.get("pegRatio"))
    rev_g = safe_float(info.get("revenueGrowth"))

    sector = info.get("sector") or info.get("industry") or "—"
    summary = (info.get("longBusinessSummary") or "")[:280].replace("\n", " ")
    cap = safe_float(info.get("marketCap"))

    scores = proxy_scores(info, adapt, sector)
    sym_key = symbol.upper().replace(".SZ", ".SZ").replace(".SS", ".SS")
    curated = CURATED.get(symbol) or CURATED.get(sym_key.split(".")[0]) or ""

    return {
        "symbol": symbol,
        "name": info.get("shortName") or symbol,
        "price": price,
        "sector": sector,
        "market_cap_B": round(cap / 1e9, 1) if cap else None,
        "trailing_pe": safe_float(info.get("trailingPE")),
        "forward_pe": safe_float(info.get("forwardPE")),
        "adapt_rate": round(adapt, 2) if adapt else None,
        "peg_text": peg_note(peg, pe, rev_g),
        "revenue_growth_pct": round(rev_g * 100, 1) if rev_g is not None else None,
        "profit_margin_pct": round(safe_float(info.get("profitMargins")) * 100, 1)
        if safe_float(info.get("profitMargins")) is not None
        else None,
        "scores": scores,
        "curated": curated,
        "summary": summary + ("…" if len(summary) >= 280 else ""),
    }


def symbols_from_scan() -> list[str]:
    if not SCAN_JSON.exists():
        return []
    data = json.loads(SCAN_JSON.read_text(encoding="utf-8"))
    syms: list[str] = []
    for bucket in ("buy_us", "buy_ash"):
        for r in data.get(bucket, []):
            y = r.get("yahoo")
            if not y:
                s = r.get("symbol", "")
                y = f"{s}.SZ" if s.isdigit() and len(s) == 6 else s
            if y and y not in syms:
                syms.append(y)
    return syms


def format_md(rows: list[dict], generated_at: str) -> str:
    lines = [
        "# 究公司 · 快速基本面",
        "",
        f"生成：**{generated_at}** · 数据源：Yahoo（延迟）· **①②⑥ 需人工打分**",
        "",
        "永泉快筛：**适应率**=价/(EPS×4)；**PEG≤1** 加分；与 `light_comm_dual` 技术面联读。",
        "",
    ]
    for r in rows:
        sc = r["scores"]
        lines.extend(
            [
                f"## {r['symbol']} · {r['name']}",
                "",
                f"| 现价 | 市值(亿USD) | 行业 | 适应率 | 远期PE |",
                f"|------|-------------|------|--------|--------|",
                f"| {r.get('price')} | {r.get('market_cap_B') or '—'} | {r.get('sector')} | "
                f"{r.get('adapt_rate') or '—'} | {r.get('forward_pe') or r.get('trailing_pe') or '—'} |",
                "",
                f"- **{r['peg_text']}** · 收入增速 {r.get('revenue_growth_pct') or '—'}% · "
                f"净利率 {r.get('profit_margin_pct') or '—'}%",
                f"- **六维代理**：③{sc['③壁垒(代理)']} ④{sc['④财务(代理)']} ⑤{sc['⑤趋势(代理)']} "
                f"（合计 {sc['proxy_total']}/15）— {sc['note']}",
            ]
        )
        if r.get("curated"):
            lines.append(f"- **主题备忘**：{r['curated']}")
        if r.get("summary"):
            lines.append(f"- **业务摘要**：{r['summary']}")
        lines.extend(
            [
                "",
                "```",
                f"① 看人 __/5   ② 组织 __/5   ⑥ 周期 __/5   总分 __/30 → □优质 □小仓 □不做",
                "```",
                "",
            ]
        )
    lines.append("---")
    lines.append("`scripts/jiu_company_daily.py`")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", default="", help="逗号分隔，如 MU,COHR,300502.SZ")
    parser.add_argument("--from-scan", action="store_true", help="读取 light_comm_dual_latest.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    elif args.from_scan or SCAN_JSON.exists():
        symbols = symbols_from_scan()
    else:
        symbols = ["MU", "COHR", "300502.SZ", "300308.SZ", "ASTS", "SWKS"]

    if not symbols:
        symbols = ["MU", "COHR", "300502.SZ"]

    rows = []
    for sym in symbols:
        try:
            rows.append(fetch_one(sym))
        except Exception as e:
            rows.append({"symbol": sym, "name": "—", "error": str(e), "scores": {"proxy_total": 0}})

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    md = format_md([r for r in rows if "error" not in r], now)
    if any("error" in r for r in rows):
        md += "\n\n**跳过**：" + ", ".join(r["symbol"] for r in rows if "error" in r)

    ALERTS.mkdir(parents=True, exist_ok=True)
    slug = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (ALERTS / f"jiu_company_{slug}.md").write_text(md, encoding="utf-8")
    (ALERTS / "jiu_company_latest.md").write_text(md, encoding="utf-8")

    print(md)
    if args.json:
        p = ALERTS / f"jiu_company_{slug}.json"
        p.write_text(json.dumps({"generated_at": now, "companies": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
        (ALERTS / "jiu_company_latest.json").write_text(
            json.dumps({"generated_at": now, "companies": rows}, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\n[written] {p}")


if __name__ == "__main__":
    main()
