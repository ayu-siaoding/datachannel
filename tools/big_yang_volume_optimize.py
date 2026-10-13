#!/usr/bin/env python3
"""Optimize first big-yang + volume entry for win-rate and expectancy."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

POOL = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "AMD", "AVGO", "TSM", "ASML",
    "QCOM", "MU", "AMAT", "LRCX", "INTC", "TXN", "KLAC", "TSLA", "NFLX", "ORCL",
    "CRM", "ADBE", "NOW", "PANW", "IBM", "PLTR", "SMCI", "DELL", "UBER", "JPM",
    "GS", "BAC", "V", "MA", "XOM", "CVX", "LLY", "UNH", "ABBV", "MRK", "COST",
    "WMT", "HD", "CAT", "GE", "ACN",
]

CACHE = Path("/tmp/big_yang_hist.pkl")


def load_hist() -> dict[str, pd.DataFrame]:
    if CACHE.exists():
        return pd.read_pickle(CACHE)
    out: dict[str, pd.DataFrame] = {}
    for s in POOL:
        try:
            h = yf.Ticker(s).history(period="5y", auto_adjust=True)
            if len(h) >= 220:
                out[s] = h
        except Exception:
            continue
    pd.to_pickle(out, CACHE)
    return out


def prep(h: pd.DataFrame) -> pd.DataFrame:
    df = h.copy()
    c, o, hi, lo, v = df["Close"], df["Open"], df["High"], df["Low"], df["Volume"]
    df["body"] = (c - o) / o.replace(0, np.nan)
    rng = (hi - lo).replace(0, np.nan)
    df["cpos"] = (c - lo) / rng
    df["vol_ma20"] = v.rolling(20).mean()
    df["vol_ratio"] = v / df["vol_ma20"]
    for n in (5, 10, 20, 60):
        df[f"ma{n}"] = c.rolling(n).mean()
    mids = (df["ma5"] + df["ma10"] + df["ma20"] + df["ma60"]) / 4
    spread = df[["ma5", "ma10", "ma20", "ma60"]].max(axis=1) - df[
        ["ma5", "ma10", "ma20", "ma60"]
    ].min(axis=1)
    df["spread"] = spread / mids
    df["ma5_slope"] = (df["ma5"] - df["ma5"].shift(3)) / df["ma5"].shift(3).abs()
    dif = c.ewm(span=12, adjust=False).mean() - c.ewm(span=26, adjust=False).mean()
    dea = dif.ewm(span=9, adjust=False).mean()
    df["dif"] = dif
    df["hist"] = (dif - dea) * 2
    df["prev_body"] = df["body"].shift(1)
    df["prev_vol_ratio"] = df["vol_ratio"].shift(1)
    return df


def signal_mask(
    df: pd.DataFrame,
    body_min: float,
    vol_mult: float,
    use_coil: bool,
    sp_max: float,
    close_pos: float,
    macd_water: bool,
) -> np.ndarray:
    m = (
        (df["body"] >= body_min)
        & (df["cpos"] >= close_pos)
        & (df["vol_ratio"] >= vol_mult)
        & (df["Close"] >= df["ma20"])
        & (df["ma5"] >= df["ma10"] * 0.997)
        & (df["ma5_slope"] > -0.001)
    )
    if use_coil:
        m &= df["spread"] <= sp_max
    # first big yang: previous bar not same-class signal
    prev_same = (
        (df["prev_body"] >= body_min * 0.9)
        & (df["prev_vol_ratio"] >= vol_mult * 0.9)
        & (df["prev_body"] > 0)
    )
    m &= ~prev_same
    if macd_water:
        m &= (df["dif"] > 0) & (df["hist"] > 0)
    arr = np.asarray(m.fillna(False).to_numpy(), dtype=bool).copy()
    # warmup
    arr[:60] = False
    return arr


def backtest_one(
    frames: dict[str, pd.DataFrame],
    body_min: float,
    vol_mult: float,
    use_coil: bool,
    sp_max: float,
    close_pos: float,
    macd_water: bool,
    tp: float,
    sl: float,
    min_n: int = 30,
) -> dict | None:
    exit_rets: list[float] = []
    hold_days: list[int] = []
    mfe_list: list[float] = []
    hit5 = 0
    hit10 = 0
    n = 0
    for df in frames.values():
        mask = signal_mask(df, body_min, vol_mult, use_coil, sp_max, close_pos, macd_water)
        close = df["Close"].to_numpy()
        high = df["High"].to_numpy()
        low = df["Low"].to_numpy()
        last = -99
        end = len(df) - 25
        idxs = np.where(mask[:end])[0]
        for i in idxs:
            if i - last < 5:
                continue
            last = i
            entry = float(close[i])
            if entry <= 0:
                continue
            n += 1
            fut_hi = high[i + 1 : i + 21]
            fut_lo = low[i + 1 : i + 21]
            mfe_list.append(float(fut_hi.max()) / entry - 1)
            if (fut_hi >= entry * 1.05).any():
                hit5 += 1
            if (fut_hi >= entry * 1.10).any():
                hit10 += 1
            exited = False
            for j in range(1, 21):
                if high[i + j] >= entry * (1 + tp):
                    exit_rets.append(tp)
                    hold_days.append(j)
                    exited = True
                    break
                if low[i + j] <= entry * (1 - sl):
                    exit_rets.append(-sl)
                    hold_days.append(j)
                    exited = True
                    break
            if not exited:
                exit_rets.append(float(close[i + 20]) / entry - 1)
                hold_days.append(20)
    if n < min_n:
        return None
    ex = np.array(exit_rets)
    mfe = np.array(mfe_list)
    win = float((ex > 0).mean())
    expect = float(ex.mean())
    pos = ex[ex > 0].sum()
    neg = abs(ex[ex <= 0].sum())
    pf = float(pos / neg) if neg > 0 else 99.0
    score = expect * 200 + win * 50 + min(n, 150) / 150 * 5 + float(mfe.mean()) * 15
    return {
        "n": n,
        "exit_win": win,
        "exit_avg": expect,
        "exit_med": float(np.median(ex)),
        "pf": pf,
        "hold": float(np.mean(hold_days)),
        "t5": hit5 / n,
        "t10": hit10 / n,
        "mfe": float(mfe.mean()),
        "score": score,
        "p": {
            "body": body_min,
            "vol": vol_mult,
            "coil": use_coil,
            "spread": sp_max,
            "cpos": close_pos,
            "macd": macd_water,
            "tp": tp,
            "sl": sl,
        },
    }


def current_matches(
    frames: dict[str, pd.DataFrame],
    body_min: float,
    vol_mult: float,
    use_coil: bool,
    sp_max: float,
    close_pos: float,
    macd_water: bool,
    lookback: int = 3,
) -> list[dict]:
    hits: list[dict] = []
    for sym, df in frames.items():
        mask = signal_mask(df, body_min, vol_mult, use_coil, sp_max, close_pos, macd_water)
        for off in range(0, lookback):
            i = len(df) - 1 - off
            if i < 60 or not mask[i]:
                continue
            row = df.iloc[i]
            hits.append(
                {
                    "symbol": sym,
                    "date": str(df.index[i].date()),
                    "close": round(float(row["Close"]), 2),
                    "body_pct": round(float(row["body"]) * 100, 2),
                    "vol_ratio": round(float(row["vol_ratio"]), 2),
                    "spread_pct": round(float(row["spread"]) * 100, 2),
                    "days_ago": off,
                }
            )
            break
    hits.sort(key=lambda x: (x["days_ago"], -x["vol_ratio"], -x["body_pct"]))
    return hits


def main() -> None:
    raw = load_hist()
    frames = {s: prep(h) for s, h in raw.items()}
    print(f"loaded {len(frames)} symbols")

    grid = []
    for body in (0.02, 0.03, 0.04, 0.05, 0.06):
        for vol in (1.2, 1.5, 2.0, 2.5):
            for use_coil in (True, False):
                spreads = (0.03, 0.045) if use_coil else (0.03,)
                for sp in spreads:
                    for cpos in (0.6, 0.75):
                        for macd in (False, True):
                            for tp, sl in (
                                (0.05, 0.05),
                                (0.08, 0.05),
                                (0.10, 0.07),
                                (0.08, 0.04),
                            ):
                                grid.append(
                                    (body, vol, use_coil, sp, cpos, macd, tp, sl)
                                )
    print(f"grid {len(grid)}")

    results: list[dict] = []
    for i, g in enumerate(grid):
        r = backtest_one(frames, *g)
        if r:
            results.append(r)
        if (i + 1) % 200 == 0:
            print(f"progress {i+1}/{len(grid)} kept {len(results)}", flush=True)

    results.sort(key=lambda x: -x["score"])
    print("\n===== TOP12 综合分 =====")
    for idx, r in enumerate(results[:12], 1):
        p = r["p"]
        print(
            f"#{idx} score={r['score']:.1f} n={r['n']} | "
            f"实体>={p['body']*100:.0f}% 量>={p['vol']}x 粘合={p['coil']} "
            f"MACD={p['macd']} 收盘位置>={p['cpos']} TP{p['tp']*100:.0f}/SL{p['sl']*100:.0f}"
        )
        print(
            f"    胜率{r['exit_win']*100:.1f}% 期望{r['exit_avg']*100:+.2f}% "
            f"中位{r['exit_med']*100:+.2f}% PF={r['pf']:.2f} 持仓{r['hold']:.1f}日 | "
            f"摸+5%{r['t5']*100:.0f}% +10%{r['t10']*100:.0f}% MFE{r['mfe']*100:.1f}%"
        )

    print("\n===== 胜率优先 n>=40 expect>0 =====")
    for r in sorted(
        [x for x in results if x["n"] >= 40 and x["exit_avg"] > 0],
        key=lambda x: (-x["exit_win"], -x["exit_avg"]),
    )[:8]:
        p = r["p"]
        print(
            f"胜率{r['exit_win']*100:.1f}% 期望{r['exit_avg']*100:+.2f}% n={r['n']} | "
            f"body{p['body']*100:.0f}% vol{p['vol']} coil={p['coil']} macd={p['macd']} "
            f"TP{p['tp']*100:.0f}/SL{p['sl']*100:.0f}"
        )

    print("\n===== 期望优先 n>=40 =====")
    for r in sorted([x for x in results if x["n"] >= 40], key=lambda x: -x["exit_avg"])[
        :8
    ]:
        p = r["p"]
        print(
            f"期望{r['exit_avg']*100:+.2f}% 胜率{r['exit_win']*100:.1f}% PF={r['pf']:.2f} "
            f"n={r['n']} | body{p['body']*100:.0f}% vol{p['vol']} coil={p['coil']} "
            f"macd={p['macd']} TP{p['tp']*100:.0f}/SL{p['sl']*100:.0f} MFE{r['mfe']*100:.1f}%"
        )

    bal = sorted(
        [x for x in results if x["n"] >= 35 and x["exit_win"] >= 0.58],
        key=lambda x: (-x["exit_avg"], -x["n"]),
    )[:10]
    if not bal:
        bal = sorted(
            [x for x in results if x["n"] >= 35 and x["exit_win"] >= 0.55],
            key=lambda x: (-x["exit_avg"], -x["n"]),
        )[:10]
    print("\n===== 均衡：高胜率+高期望 =====")
    for r in bal:
        p = r["p"]
        print(
            f"期望{r['exit_avg']*100:+.2f}% 胜率{r['exit_win']*100:.1f}% n={r['n']} "
            f"PF={r['pf']:.2f} | body>={p['body']*100:.0f}% 量>={p['vol']}x "
            f"粘合={p['coil']} macd={p['macd']} 收盘位置{p['cpos']} "
            f"TP{p['tp']*100:.0f}/SL{p['sl']*100:.0f} 摸5%={r['t5']*100:.0f}% "
            f"MFE={r['mfe']*100:.1f}%"
        )

    best = bal[0] if bal else results[0]
    p = best["p"]
    print("\n***** 推荐方法 *****")
    print(json.dumps(best, indent=2, ensure_ascii=False))

    matches = current_matches(
        frames,
        p["body"],
        p["vol"],
        p["coil"],
        p["spread"],
        p["cpos"],
        p["macd"],
        lookback=5,
    )
    print("\n===== 近5日符合推荐规则的标的 =====")
    print(json.dumps(matches[:15], indent=2, ensure_ascii=False))

    out = Path("/opt/cursor/artifacts/big_yang_volume_best.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"best": best, "top12": results[:12], "matches": matches[:20]}, indent=2),
        encoding="utf-8",
    )
    print(f"\nsaved {out}")


if __name__ == "__main__":
    main()
