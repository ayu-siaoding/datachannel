#!/usr/bin/env python3
"""Daily SPX + SPY + QQQ upside/downside level chains (GEX profile style).

Usage:
  python3 scripts/spx_spy_levels_daily.py
  python3 scripts/spx_spy_levels_daily.py --json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import sys

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gex_heatmap_daily import build_gex_grid, fetch_spot

ALERTS = Path("/workspace/scripts/alerts")
NEAR_EXP = 3
MAX_STRIKE_PCT = 0.035


def instrument_params(spot: float) -> dict:
    if spot >= 1000:
        return {"band": 25.0, "step": 15.0, "step2": 10.0, "round": 5.0, "n_up": 3, "n_dn": 4, "fmt": ".0f"}
    if spot >= 300:
        return {"band": 6.0, "step": 3.0, "step2": 2.0, "round": 1.0, "n_up": 3, "n_dn": 4, "fmt": ".2f"}
    return {"band": 2.5, "step": 1.5, "step2": 1.0, "round": 0.5, "n_up": 3, "n_dn": 4, "fmt": ".2f"}


def round_level(x: float, unit: float) -> float:
    if unit >= 1:
        return round(x / unit) * unit
    return round(x / unit) * unit


def spx_to_spy(spx: float, spy: float, spx_level: float) -> float:
    ratio = spx / spy if spy > 0 else 10.03
    return round(spx_level / ratio, 2)


def aggregate_by_strike(grid: pd.DataFrame, expirations: list[str]) -> pd.Series:
    use = grid[grid["expiration"].isin(expirations[:NEAR_EXP])]
    if use.empty:
        use = grid
    return use.groupby("strike")["gex_usd"].sum().sort_index()


def local_peaks(series: pd.Series, spot: float, above: bool, n: int) -> list[float]:
    strikes = series.index.to_list()
    vals = series.values
    peaks: list[tuple[float, float]] = []
    for i in range(1, len(strikes) - 1):
        s = float(strikes[i])
        if above and s <= spot:
            continue
        if not above and s >= spot:
            continue
        if abs(vals[i]) >= abs(vals[i - 1]) and abs(vals[i]) >= abs(vals[i + 1]):
            peaks.append((s, abs(vals[i])))
    peaks.sort(key=lambda x: x[1], reverse=True)
    ordered = sorted([p[0] for p in peaks], reverse=not above)
    return ordered[:n] if len(ordered) >= n else ordered


def fill_levels(
    spot: float, existing: list[float], above: bool, n: int, step: float, step2: float, rnd: float
) -> list[float]:
    out = sorted(set(existing), reverse=not above)
    anchor = spot if not out else (max(out) if above else min(out))
    st = step
    while len(out) < n:
        anchor = anchor + st if above else anchor - st
        anchor = round_level(anchor, rnd)
        if anchor not in out:
            out.append(anchor)
        out = sorted(set(out), reverse=not above)
        st = step2 if len(out) >= 2 else step
    return sorted(out) if above else sorted(out, reverse=True)


def dominant_strike(agg: pd.Series, spot: float, band: float, rnd: float) -> float:
    b = agg[(agg.index >= spot - band) & (agg.index <= spot + band)]
    if not b.empty and (b > 0).any():
        return float(b.idxmax())
    return round_level(spot, rnd)


def build_chains(spot: float, agg: pd.Series) -> dict:
    p = instrument_params(spot)
    dom = dominant_strike(agg, spot, p["band"], p["round"])
    up_peaks = local_peaks(agg, spot, above=True, n=p["n_up"])
    dn_peaks = local_peaks(agg, spot, above=False, n=p["n_dn"])
    upside = fill_levels(spot, up_peaks, True, p["n_up"], p["step"], p["step2"], p["round"])
    downside = fill_levels(spot, dn_peaks, False, p["n_dn"], p["step"], p["step2"], p["round"])
    tol = p["round"] * 5
    upside = sorted([u for u in upside if u > spot - tol])[: p["n_up"]]
    if len(upside) < p["n_up"]:
        upside = fill_levels(spot, upside, True, p["n_up"], p["step"], p["step2"], p["round"])
    downside = sorted([d for d in downside if d < spot + tol], reverse=True)[: p["n_dn"]]
    if len(downside) < p["n_dn"]:
        downside = fill_levels(spot, downside, False, p["n_dn"], p["step"], p["step2"], p["round"])
    return {"dominant": dom, "upside": upside, "downside": downside, "fmt": p["fmt"]}


def fmt_chain(levels: list[float], fmt: str) -> str:
    return " --> ".join(format(x, fmt) for x in levels)


def commentary(label: str, dom: float, spot: float, upside: list[float], fmt: str) -> str:
    room_up = upside[0] - spot if upside else 0
    dom_s = format(dom, fmt)
    if spot >= 1000 and room_up < 12:
        return (
            f"{label}: {dom_s} remains near the profile's dominant pin today; "
            f"upside looks quite limited (first shelf ~{room_up:.0f} pts above spot)."
        )
    if spot < 1000 and room_up < 2:
        return (
            f"{label}: {dom_s} dominant; upside limited (first shelf ~{room_up:.2f} above spot)."
        )
    return f"{label}: dominant **{dom_s}** · spot **{format(spot, fmt)}**."


def section_block(title: str, spot: float, chains: dict, spy_equiv: list[float] | None = None) -> list[str]:
    fmt = chains["fmt"]
    lines = [
        title,
        fmt_chain(chains["upside"], fmt),
    ]
    if spy_equiv is not None:
        lines.append("SPY: " + " --> ".join(f"{x:.2f}" for x in spy_equiv))
    lines.append(commentary(title.split()[0], chains["dominant"], spot, chains["upside"], fmt))
    lines.append("")
    lines.append(title.replace("UPSIDE", "DOWNSIDE"))
    lines.append(fmt_chain(chains["downside"], fmt))
    if spy_equiv is not None:
        # downside spy equiv passed separately
        pass
    return lines


def chains_for_symbol(yahoo_symbol: str, strike_pct: float = MAX_STRIKE_PCT) -> tuple[float, dict]:
    ticker = yf.Ticker(yahoo_symbol)
    spot = fetch_spot(ticker, yahoo_symbol)
    try:
        spot_g, grid, exps = build_gex_grid(yahoo_symbol, 12, strike_pct)
        spot = spot_g
        agg = aggregate_by_strike(grid, exps)
    except Exception:
        p = instrument_params(spot)
        dom = round_level(spot, p["round"])
        agg = pd.Series({dom: 1.0, dom + p["step"]: 0.5, dom - p["step"]: -0.5})
    return spot, build_chains(spot, agg)


def format_plain(
    generated_at: str,
    spx_spot: float,
    spy_spot: float,
    spx_c: dict,
    spy_c: dict,
    qqq_c: dict,
    qqq_spot: float,
) -> str:
    up_spy_from_spx = [spx_to_spy(spx_spot, spy_spot, x) for x in spx_c["upside"]]
    dn_spy_from_spx = [spx_to_spy(spx_spot, spy_spot, x) for x in spx_c["downside"]]

    lines = [
        f"生成 {generated_at}",
        "",
        "======== SPX（含 SPY 换算）========",
        f"SPX {spx_spot:.2f} | Dominant {spx_c['dominant']:.0f}",
        "SPX/SPY UPSIDE",
        fmt_chain(spx_c["upside"], spx_c["fmt"]),
        "SPY: " + " --> ".join(f"{x:.2f}" for x in up_spy_from_spx),
        commentary("SPX", spx_c["dominant"], spx_spot, spx_c["upside"], spx_c["fmt"]),
        "",
        "SPX/SPY DOWNSIDE",
        fmt_chain(spx_c["downside"], spx_c["fmt"]),
        "SPY: " + " --> ".join(f"{x:.2f}" for x in dn_spy_from_spx),
        "",
        "======== SPY（ETF 期权 GEX）========",
        f"SPY {spy_spot:.2f} | Dominant {spy_c['dominant']:.2f}",
        "SPY UPSIDE",
        fmt_chain(spy_c["upside"], spy_c["fmt"]),
        commentary("SPY", spy_c["dominant"], spy_spot, spy_c["upside"], spy_c["fmt"]),
        "",
        "SPY DOWNSIDE",
        fmt_chain(spy_c["downside"], spy_c["fmt"]),
        "",
        "======== QQQ（ETF 期权 GEX）========",
        f"QQQ {qqq_spot:.2f} | Dominant {qqq_c['dominant']:.2f}",
        "QQQ UPSIDE",
        fmt_chain(qqq_c["upside"], qqq_c["fmt"]),
        commentary("QQQ", qqq_c["dominant"], qqq_spot, qqq_c["upside"], qqq_c["fmt"]),
        "",
        "QQQ DOWNSIDE",
        fmt_chain(qqq_c["downside"], qqq_c["fmt"]),
        "",
        "---",
        "SPX/SPY/QQQ · scripts/spx_spy_levels_daily.py · GEX 估算，非付费 Profile 原值",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    generated_at = now.strftime("%Y-%m-%d %H:%M UTC")
    date_slug = now.strftime("%Y-%m-%d")
    time_slug = now.strftime("%H%M")

    spy_spot = fetch_spot(yf.Ticker("SPY"), "SPY")
    spx_spot, spx_c = chains_for_symbol("^SPX")
    _, spy_c = chains_for_symbol("SPY")
    qqq_spot, qqq_c = chains_for_symbol("QQQ")

    plain = format_plain(generated_at, spx_spot, spy_spot, spx_c, spy_c, qqq_c, qqq_spot)

    ALERTS.mkdir(parents=True, exist_ok=True)
    (ALERTS / f"spx_spy_levels_{date_slug}.txt").write_text(plain, encoding="utf-8")
    (ALERTS / f"spx_spy_levels_{date_slug}_{time_slug}.txt").write_text(plain, encoding="utf-8")
    (ALERTS / "spx_spy_levels_latest.txt").write_text(plain, encoding="utf-8")

    print(plain)
    if args.json:
        payload = {
            "generated_at": generated_at,
            "SPX": {"spot": spx_spot, **{k: spx_c[k] for k in ("dominant", "upside", "downside")}},
            "SPY": {
                "spot": spy_spot,
                **{k: spy_c[k] for k in ("dominant", "upside", "downside")},
                "from_spx_upside": [spx_to_spy(spx_spot, spy_spot, x) for x in spx_c["upside"]],
                "from_spx_downside": [spx_to_spy(spx_spot, spy_spot, x) for x in spx_c["downside"]],
            },
            "QQQ": {"spot": qqq_spot, **{k: qqq_c[k] for k in ("dominant", "upside", "downside")}},
        }
        p = ALERTS / f"spx_spy_levels_{date_slug}.json"
        p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\n[written] {p}")


if __name__ == "__main__":
    main()
