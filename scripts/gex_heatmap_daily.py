#!/usr/bin/env python3
"""
Daily dealer-style GEX heatmap (strike × expiration), similar to mobile「Dealer GEX Heatmap」.

Data: Yahoo Finance ^SPX option chains (delayed). Gamma from Black–Scholes using chain IV.
GEX convention (retail/dealer shorthand):
  call_contrib = +gamma * OI * 100 * spot
  put_contrib  = -gamma * OI * 100 * spot
  net_gex per (strike, expiry) = sum of both sides

Usage:
  python3 scripts/gex_heatmap_daily.py
  python3 scripts/gex_heatmap_daily.py --symbol SPY --spot-scale 1
  python3 scripts/gex_heatmap_daily.py --json

Cron (US cash open ~ 09:35 ET ≈ 13:35 UTC DST):
  35 13 * * 1-5 cd /path/to/repo && python3 scripts/gex_heatmap_daily.py >> scripts/alerts/cron.log 2>&1
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

DEFAULT_SYMBOL = "^SPX"
CONTRACT_MULT = 100
RISK_FREE = 0.045
DIV_YIELD = 0.0
MAX_EXPIRIES = 12
MIN_OPEN_INTEREST = 1
MAX_STRIKE_PCT = 0.035  # |K-S|/S
MIN_T_YEARS = 1 / (365 * 24 * 6)  # ~10 minutes
TOP_CELLS = 8


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def bs_gamma(spot: float, strike: float, t_years: float, sigma: float) -> float:
    if spot <= 0 or strike <= 0 or t_years <= MIN_T_YEARS or sigma <= 0:
        return 0.0
    vol_sqrt_t = sigma * math.sqrt(t_years)
    d1 = (math.log(spot / strike) + (RISK_FREE - DIV_YIELD + 0.5 * sigma * sigma) * t_years) / vol_sqrt_t
    return math.exp(-DIV_YIELD * t_years) * norm_pdf(d1) / (spot * vol_sqrt_t)


def parse_iv(raw: float) -> float | None:
    if raw is None or (isinstance(raw, float) and math.isnan(raw)):
        return None
    iv = float(raw)
    if iv <= 0:
        return None
    if iv < 3:
        iv *= 100
    if iv > 200:
        return None
    return iv / 100.0


def dte_label(exp: str, today: datetime) -> str:
    exp_dt = datetime.strptime(exp, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    dte = (exp_dt.date() - today.date()).days
    if dte <= 0:
        return f"{exp[5:]} (0DTE)"
    return f"{exp[5:]} ({dte}D)"


def fetch_spot(ticker: yf.Ticker, symbol: str) -> float:
    try:
        h = ticker.history(period="1d", prepost=True)
        if not h.empty:
            return float(h["Close"].iloc[-1])
    except Exception:
        pass
    try:
        fi = ticker.fast_info
        for attr in ("last_price", "regular_market_price", "previous_close"):
            v = getattr(fi, attr, None)
            if v:
                return float(v)
    except Exception:
        pass
    raise RuntimeError(f"Cannot resolve spot for {symbol}")


def build_gex_grid(symbol: str, max_expiries: int, max_strike_pct: float) -> tuple[float, pd.DataFrame, list[str]]:
    ticker = yf.Ticker(symbol)
    spot = fetch_spot(ticker, symbol)
    try:
        expirations = list(ticker.options)[:max_expiries]
    except Exception as exc:
        raise RuntimeError(f"No option chain for {symbol}: {exc}") from exc
    if not expirations:
        raise RuntimeError(f"Empty option expirations for {symbol}")

    now = datetime.now(timezone.utc)
    records: list[dict] = []

    for exp in expirations:
        exp_dt = datetime.strptime(exp, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        t_years = max((exp_dt - now).total_seconds() / (365.25 * 24 * 3600), MIN_T_YEARS)
        try:
            chain = ticker.option_chain(exp)
        except Exception:
            continue
        for side, df in (("C", chain.calls), ("P", chain.puts)):
            if df is None or df.empty:
                continue
            sign = 1.0 if side == "C" else -1.0
            for _, row in df.iterrows():
                oi = int(pd.to_numeric(row.get("openInterest"), errors="coerce") or 0)
                if oi < MIN_OPEN_INTEREST:
                    continue
                strike = float(row["strike"])
                if abs(strike - spot) / spot > max_strike_pct:
                    continue
                iv = parse_iv(row.get("impliedVolatility"))
                if iv is None:
                    continue
                gamma = bs_gamma(spot, strike, t_years, iv)
                if gamma <= 0:
                    continue
                gex_usd = sign * gamma * oi * CONTRACT_MULT * spot
                records.append(
                    {
                        "expiration": exp,
                        "strike": strike,
                        "gex_usd": gex_usd,
                        "gex_k": gex_usd / 1000.0,
                        "oi": oi,
                        "side": side,
                    }
                )

    if not records:
        raise RuntimeError("No GEX rows after filters (OI/IV/strike range).")

    detail = pd.DataFrame(records)
    grid = (
        detail.groupby(["strike", "expiration"], as_index=False)["gex_usd"]
        .sum()
        .assign(gex_k=lambda d: d["gex_usd"] / 1000.0)
    )
    return spot, grid, expirations


def pick_strike_rows(grid: pd.DataFrame, spot: float, n_each_side: int = 14) -> list[float]:
    strikes = sorted(grid["strike"].unique())
    if not strikes:
        return []
    closest_idx = min(range(len(strikes)), key=lambda i: abs(strikes[i] - spot))
    lo = max(0, closest_idx - n_each_side)
    hi = min(len(strikes), closest_idx + n_each_side + 1)
    return sorted(strikes[lo:hi], reverse=True)


def format_cell(gex_k: float) -> str:
    if abs(gex_k) >= 1000:
        return f"{gex_k:,.0f}K"
    if abs(gex_k) >= 100:
        return f"{gex_k:,.1f}K"
    return f"{gex_k:,.2f}K"


def key_levels(grid: pd.DataFrame, spot: float, expirations: list[str]) -> list[str]:
    lines: list[str] = []
    near = grid.copy()
    near["dist"] = (near["strike"] - spot).abs()
    for exp in expirations[:4]:
        sub = near[near["expiration"] == exp]
        if sub.empty:
            continue
        pos = sub.loc[sub["gex_usd"].idxmax()] if (sub["gex_usd"] > 0).any() else None
        neg = sub.loc[sub["gex_usd"].idxmin()] if (sub["gex_usd"] < 0).any() else None
        at_spot = sub.loc[(sub["dist"]).idxmin()]
        lines.append(f"- **{dte_label(exp, datetime.now(timezone.utc))}**")
        lines.append(f"  - 现价附近行权 **{at_spot['strike']:.0f}** · GEX **{format_cell(at_spot['gex_k'])}**")
        if pos is not None and pos["gex_usd"] > 0:
            lines.append(f"  - 最大正 GEX **{pos['strike']:.0f}** · **{format_cell(pos['gex_k'])}**")
        if neg is not None and neg["gex_usd"] < 0:
            lines.append(f"  - 最大负 GEX **{neg['strike']:.0f}** · **{format_cell(neg['gex_k'])}**")
    return lines


def format_markdown(
    symbol: str,
    spot: float,
    grid: pd.DataFrame,
    expirations: list[str],
    generated_at: str,
) -> str:
    exps = [e for e in expirations if e in set(grid["expiration"])][:6]
    strikes = pick_strike_rows(grid, spot)
    today = datetime.now(timezone.utc)

    lines = [
        f"# Dealer GEX Heatmap · {symbol} · {generated_at}",
        "",
        f"**Spot ≈ {spot:,.2f}**（Yahoo 延迟；Gamma 由 IV + Black–Scholes 推算，与券商 APP 数值会有偏差）",
        "",
        "> 解读：绿/正 GEX 常对应波动钝化、磁吸；紫/负 GEX 常对应对冲同向、易加速。",
        "",
        "## 热力表（Net GEX，单位 K USD）",
        "",
    ]

    header = "| Strike | " + " | ".join(dte_label(e, today) for e in exps) + " |"
    sep = "|---|" + "|".join(["---:"] * len(exps)) + "|"
    lines.extend([header, sep])

    pivot = grid.pivot_table(index="strike", columns="expiration", values="gex_k", aggfunc="sum")
    spot_strike = min(strikes, key=lambda s: abs(s - spot))
    for strike in strikes:
        is_spot_row = abs(strike - spot_strike) < 0.01
        label = f"**{strike:.0f} ←spot**" if is_spot_row else f"{strike:.0f}"
        row_cells = [label]
        for exp in exps:
            val = pivot.loc[strike, exp] if strike in pivot.index and exp in pivot.columns else float("nan")
            if pd.isna(val):
                row_cells.append("—")
            else:
                row_cells.append(format_cell(float(val)))
        lines.append("| " + " | ".join(row_cells) + " |")

    lines.append("")
    lines.append("## 关键档位（近端到期）")
    lines.append("")
    lines.extend(key_levels(grid, spot, exps))

    # Top absolute cells overall
    top = grid.reindex(grid["gex_usd"].abs().sort_values(ascending=False).index).head(TOP_CELLS)
    lines.append("")
    lines.append("## 全表 |GEX| Top")
    lines.append("")
    for _, r in top.iterrows():
        lines.append(
            f"- {r['strike']:.0f} · {r['expiration']} · **{format_cell(r['gex_k'])}**"
        )
    return "\n".join(lines)


def _cell_color(gex_k: float, vmax: float) -> str:
    if vmax <= 0 or gex_k != gex_k:
        return "#1a1a2e"
    t = min(abs(gex_k) / vmax, 1.0)
    if gex_k >= 0:
        # yellow / orange positive
        r = int(40 + 215 * t)
        g = int(30 + 170 * t)
        b = int(20 + 40 * t)
    else:
        # purple negative
        r = int(30 + 120 * t)
        g = int(20 + 30 * t)
        b = int(60 + 180 * t)
    return f"rgb({r},{g},{b})"


def format_html_heatmap(
    symbol: str,
    spot: float,
    grid: pd.DataFrame,
    expirations: list[str],
    generated_at: str,
) -> str:
    exps = [e for e in expirations if e in set(grid["expiration"])][:6]
    strikes = pick_strike_rows(grid, spot)
    today = datetime.now(timezone.utc)
    pivot = grid.pivot_table(index="strike", columns="expiration", values="gex_k", aggfunc="sum")
    spot_strike = min(strikes, key=lambda s: abs(s - spot))

    vals: list[float] = []
    for strike in strikes:
        for exp in exps:
            if strike in pivot.index and exp in pivot.columns:
                v = pivot.loc[strike, exp]
                if not pd.isna(v):
                    vals.append(abs(float(v)))
    vmax = max(vals) if vals else 1.0

    head = "".join(f"<th>{dte_label(e, today)}</th>" for e in exps)
    body_rows: list[str] = []
    for strike in strikes:
        is_spot = abs(strike - spot_strike) < 0.01
        cells = [f'<td class="strike{" spot" if is_spot else ""}">{strike:.0f}</td>']
        for exp in exps:
            val = pivot.loc[strike, exp] if strike in pivot.index and exp in pivot.columns else float("nan")
            if pd.isna(val):
                cells.append('<td class="empty">—</td>')
            else:
                gex_k = float(val)
                bg = _cell_color(gex_k, vmax)
                fg = "#111" if gex_k >= 0 and abs(gex_k) / vmax > 0.55 else "#eee"
                cells.append(
                    f'<td style="background:{bg};color:{fg}">{format_cell(gex_k)}</td>'
                )
        body_rows.append("<tr>" + "".join(cells) + "</tr>")

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Dealer GEX · {symbol} · {generated_at}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; background: #0f0f14; color: #e8e8e8; margin: 12px; }}
    h1 {{ font-size: 1.1rem; margin: 0 0 4px; }}
    .meta {{ color: #aaa; font-size: 0.85rem; margin-bottom: 12px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 0.72rem; }}
    th, td {{ border: 1px solid #333; padding: 4px 6px; text-align: right; }}
    th {{ background: #222; position: sticky; top: 0; }}
    td.strike {{ text-align: center; font-weight: 600; background: #1c1c24; }}
    td.strike.spot {{ outline: 2px dashed #fff; }}
    td.empty {{ color: #555; }}
    .note {{ margin-top: 12px; font-size: 0.8rem; color: #888; }}
  </style>
</head>
<body>
  <h1>Dealer GEX Heatmap · {symbol}</h1>
  <div class="meta">Spot ≈ {spot:,.2f} · {generated_at} · Yahoo + BS Gamma（非 Apex 原图）</div>
  <table>
    <thead><tr><th>Strike</th>{head}</tr></thead>
    <tbody>
      {"".join(body_rows)}
    </tbody>
  </table>
  <p class="note">正 GEX（黄/橙）≈ 钝化/磁吸；负 GEX（紫）≈ 易加速。与付费终端数值会有偏差。</p>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default=DEFAULT_SYMBOL, help="Yahoo ticker (^SPX or SPY)")
    parser.add_argument("--push-dir", type=Path, default=Path("/workspace/scripts/alerts"))
    parser.add_argument("--max-expiries", type=int, default=MAX_EXPIRIES)
    parser.add_argument("--strike-pct", type=float, default=MAX_STRIKE_PCT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    generated_at = now.strftime("%Y-%m-%d %H:%M UTC")
    date_slug = now.strftime("%Y-%m-%d")
    time_slug = now.strftime("%H%M")
    sym_slug = args.symbol.replace("^", "").lower()

    print(f"GEX scan {args.symbol}...", flush=True)
    spot, grid, expirations = build_gex_grid(args.symbol, args.max_expiries, args.strike_pct)

    args.push_dir.mkdir(parents=True, exist_ok=True)
    # 当日汇总（覆盖更新）
    md_path = args.push_dir / f"gex_heatmap_{sym_slug}_{date_slug}.md"
    csv_path = args.push_dir / f"gex_heatmap_{sym_slug}_{date_slug}.csv"
    # 每次运行快照（盘前/盘中留档）
    snap_base = f"gex_heatmap_{sym_slug}_{date_slug}_{time_slug}"
    html_snap = args.push_dir / f"{snap_base}.html"
    html_latest = args.push_dir / f"gex_heatmap_{sym_slug}_latest.html"

    md = format_markdown(args.symbol, spot, grid, expirations, generated_at)
    html = format_html_heatmap(args.symbol, spot, grid, expirations, generated_at)
    md_path.write_text(md, encoding="utf-8")
    html_snap.write_text(html, encoding="utf-8")
    html_latest.write_text(html, encoding="utf-8")
    grid.sort_values(["expiration", "strike"]).to_csv(csv_path, index=False)

    if args.json:
        payload = {
            "symbol": args.symbol,
            "spot": spot,
            "generated_at": generated_at,
            "rows": grid.to_dict(orient="records"),
        }
        json_path = args.push_dir / f"gex_heatmap_{sym_slug}_{date_slug}.json"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        (args.push_dir / f"{snap_base}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"[written] {json_path}")

    print(md)
    print(
        f"\n[written] {md_path}\n[written] {csv_path}\n[written] {html_snap}\n[written] {html_latest}"
    )


if __name__ == "__main__":
    main()
