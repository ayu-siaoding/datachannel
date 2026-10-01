#!/usr/bin/env python3
"""Daily SPX/SPY upside & downside level chains (GEX profile style).

Output format (like mobile profile cards):
  SPX/SPY UPSIDE:  7690 --> 7705 --> 7715
  SPY:             766.46 --> 767.96 --> 768.96
  SPX/SPY DOWNSIDE: 7665 --> 7650 --> ...

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
        s = strikes[i]
        if above and s <= spot:
            continue
        if not above and s >= spot:
            continue
        if abs(vals[i]) >= abs(vals[i - 1]) and abs(vals[i]) >= abs(vals[i + 1]):
            peaks.append((s, abs(vals[i])))
    peaks.sort(key=lambda x: x[1], reverse=True)
    ordered = sorted([p[0] for p in peaks], reverse=not above)
    if len(ordered) >= n:
        return ordered[:n] if above else ordered[:n]
    return ordered


def fill_levels(spot: float, existing: list[float], above: bool, n: int, step: float = 15.0) -> list[float]:
    out = sorted(set(existing), reverse=not above)
    anchor = spot if not out else (max(out) if above else min(out))
    while len(out) < n:
        anchor = anchor + step if above else anchor - step
        anchor = round(anchor / 5) * 5
        if anchor not in out:
            out.append(anchor)
        out = sorted(set(out), reverse=not above)
        step = 10.0 if len(out) >= 2 else 15.0
    return sorted(out) if above else sorted(out, reverse=True)


def dominant_strike(agg: pd.Series, spot: float) -> float:
    band = agg[(agg.index >= spot - 25) & (agg.index <= spot + 25)]
    if not band.empty and (band > 0).any():
        return float(band.idxmax())
    return round(spot / 5) * 5


def build_chains(spot_spx: float, agg: pd.Series) -> dict:
    dom = dominant_strike(agg, spot_spx)
    up_peaks = local_peaks(agg, spot_spx, above=True, n=3)
    dn_peaks = local_peaks(agg, spot_spx, above=False, n=4)
    upside = fill_levels(spot_spx, up_peaks, above=True, n=3)
    downside = fill_levels(spot_spx, dn_peaks, above=False, n=4)
    # ensure monotonic chains from spot perspective
    upside = sorted([u for u in upside if u > spot_spx - 5])[:3]
    if len(upside) < 3:
        upside = fill_levels(spot_spx, upside, above=True, n=3)
    downside = sorted([d for d in downside if d < spot_spx + 5], reverse=True)[:4]
    if len(downside) < 4:
        downside = fill_levels(spot_spx, downside, above=False, n=4)
    return {"dominant": dom, "upside_spx": upside, "downside_spx": downside}


def commentary(dom: float, spot: float, upside: list[float]) -> str:
    room_up = upside[0] - spot if upside else 0
    if room_up < 12:
        return (
            f"{dom:.0f} remains near the profile's dominant pin today; "
            f"upside looks quite limited (first shelf ~{room_up:.0f} pts above spot)."
        )
    return (
        f"Profile dominant near **{dom:.0f}**; spot **{spot:,.2f}**. "
        f"First upside shelf **{upside[0]:.0f}**, then **{' --> '.join(f'{x:.0f}' for x in upside[1:])}**."
    )


def format_card(
    spot_spx: float,
    spot_spy: float,
    chains: dict,
    generated_at: str,
) -> str:
    up = chains["upside_spx"]
    dn = chains["downside_spx"]
    dom = chains["dominant"]
    up_spy = [spx_to_spy(spot_spx, spot_spy, x) for x in up]
    dn_spy = [spx_to_spy(spot_spx, spot_spy, x) for x in dn]

    up_arrow = " --> ".join(f"{x:.0f}" for x in up)
    dn_arrow = " --> ".join(f"{x:.0f}" for x in dn)
    up_spy_s = " --> ".join(f"{x:.2f}" for x in up_spy)
    dn_spy_s = " --> ".join(f"{x:.2f}" for x in dn_spy)

    note = commentary(dom, spot_spx, up)
    return f"""# SPX / SPY 日内点位 · {generated_at}

**Spot:** SPX **{spot_spx:,.2f}** · SPY **{spot_spy:.2f}** · Dominant pin ≈ **{dom:.0f}**

## SPX/SPY UPSIDE
{up_arrow}
SPY: {up_spy_s}

{note}

## SPX/SPY DOWNSIDE
{dn_arrow}
SPY: {dn_spy_s}

---
*由 scripts/spx_spy_levels_daily.py 根据 ^SPX 近月 GEX 聚合生成；与付费 Profile 终端会有偏差，仅供纪律参照。*
"""


def format_plain(spot_spx: float, spot_spy: float, chains: dict, generated_at: str) -> str:
    md = format_card(spot_spx, spot_spy, chains, generated_at)
    # compact for WeChat-style copy
    up = chains["upside_spx"]
    dn = chains["downside_spx"]
    up_spy = [spx_to_spy(spot_spx, spot_spy, x) for x in up]
    dn_spy = [spx_to_spy(spot_spx, spot_spy, x) for x in dn]
    lines = [
        f"生成 {generated_at}",
        f"SPX {spot_spx:.2f} | SPY {spot_spy:.2f} | Dominant {chains['dominant']:.0f}",
        "",
        "SPX/SPY UPSIDE",
        " --> ".join(f"{x:.0f}" for x in up),
        "SPY: " + " --> ".join(f"{x:.2f}" for x in up_spy),
        commentary(chains["dominant"], spot_spx, up),
        "",
        "SPX/SPY DOWNSIDE",
        " --> ".join(f"{x:.0f}" for x in dn),
        "SPY: " + " --> ".join(f"{x:.2f}" for x in dn_spy),
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

    spy_t = yf.Ticker("SPY")
    spot_spy = fetch_spot(spy_t, "SPY")
    spot_spx, grid, exps = build_gex_grid("^SPX", 12, MAX_STRIKE_PCT)
    agg = aggregate_by_strike(grid, exps)
    chains = build_chains(spot_spx, agg)

    ALERTS.mkdir(parents=True, exist_ok=True)
    plain = format_plain(spot_spx, spot_spy, chains, generated_at)
    md = format_card(spot_spx, spot_spy, chains, generated_at)

    (ALERTS / f"spx_spy_levels_{date_slug}.txt").write_text(plain, encoding="utf-8")
    (ALERTS / f"spx_spy_levels_{date_slug}.md").write_text(md, encoding="utf-8")
    (ALERTS / f"spx_spy_levels_{date_slug}_{time_slug}.txt").write_text(plain, encoding="utf-8")
    (ALERTS / "spx_spy_levels_latest.txt").write_text(plain, encoding="utf-8")

    print(plain)
    if args.json:
        payload = {
            "generated_at": generated_at,
            "spot_spx": spot_spx,
            "spot_spy": spot_spy,
            **chains,
            "upside_spy": [spx_to_spy(spot_spx, spot_spy, x) for x in chains["upside_spx"]],
            "downside_spy": [spx_to_spy(spot_spx, spot_spy, x) for x in chains["downside_spx"]],
        }
        p = ALERTS / f"spx_spy_levels_{date_slug}.json"
        p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\n[written] {p}")


if __name__ == "__main__":
    main()
