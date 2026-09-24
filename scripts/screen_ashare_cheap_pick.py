#!/usr/bin/env python3
"""A-share 低价小盘「捡漏」扫描（弱化定价权/六维，重结构+KDJ+横盘+流动性）。

依赖: pip install baostock pandas numpy
用法: python3 scripts/screen_ashare_cheap_pick.py [--end YYYY-MM-DD]
"""

from __future__ import annotations

import argparse
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import baostock as bs
import numpy as np
import pandas as pd

PRICE_MIN, PRICE_MAX = 1.5, 3.5
AMOUNT_MIN = 4e7  # 日成交额下限（元）
CODE_PREFIXES = ("sz.002", "sz.000", "sh.603")


def calc_kdj(h, l, c, n=9, m1=3, m2=3):
    low_n = l.rolling(n).min()
    high_n = h.rolling(n).max()
    rsv = (c - low_n) / (high_n - low_n).replace(0, np.nan) * 100
    k = rsv.ewm(alpha=1 / m1, adjust=False).mean()
    d = k.ewm(alpha=1 / m2, adjust=False).mean()
    j = 3 * k - 2 * d
    return k, d, j


def fetch_codes(end: str) -> list[str]:
    rs = bs.query_all_stock(day=end)
    codes = []
    while rs.error_code == "0" and rs.next():
        row = rs.get_row_data()
        c, t = row[0], row[1]
        if t != "1":
            continue
        if c.startswith(("sh.688", "bj.")):
            continue
        if not c.startswith(CODE_PREFIXES):
            continue
        codes.append(c)
    return codes


def last_bar(code: str, end: str) -> tuple | None:
    rs = bs.query_history_k_data_plus(
        code,
        "date,close,pctChg,amount,turn",
        start_date=end,
        end_date=end,
        frequency="d",
        adjustflag="2",
    )
    rows = []
    while rs.error_code == "0" and rs.next():
        rows.append(rs.get_row_data())
    if not rows:
        return None
    d = rows[-1]
    try:
        return (
            code,
            float(d[1]),
            float(d[2] or 0),
            float(d[3] or 0),
            float(d[4] or 0),
        )
    except (TypeError, ValueError):
        return None


def load_names() -> dict[str, str]:
    rs = bs.query_stock_basic()
    out = {}
    while rs.error_code == "0" and rs.next():
        row = rs.get_row_data()
        out[row[0]] = row[1]
    return out


def analyze(code: str, name: str, end: str, start: str) -> dict | None:
    if "ST" in name or "退" in name:
        return None
    rs = bs.query_history_k_data_plus(
        code,
        "date,open,high,low,close,volume,amount,turn,pctChg",
        start_date=start,
        end_date=end,
        frequency="d",
        adjustflag="2",
    )
    rows = []
    while rs.error_code == "0" and rs.next():
        rows.append(rs.get_row_data())
    if len(rows) < 60:
        return None

    df = pd.DataFrame(
        rows,
        columns=["date", "open", "high", "low", "close", "volume", "amount", "turn", "pct"],
    )
    for col in ["open", "high", "low", "close", "volume", "amount", "turn", "pct"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    c, h, l, v = df["close"], df["high"], df["low"], df["volume"]
    last = float(c.iloc[-1])
    chg = float(df["pct"].iloc[-1])
    low52, high52 = float(c.min()), float(c.max())
    pos = (last - low52) / (high52 - low52 + 1e-9)

    ma20, ma60 = c.rolling(20).mean(), c.rolling(60).mean()
    k, d, j = calc_kdj(h, l, c)
    kv, dv, jv = float(k.iloc[-1]), float(d.iloc[-1]), float(j.iloc[-1])
    kv_p, dv_p = float(k.iloc[-2]), float(d.iloc[-2])

    vol_ma20 = v.rolling(20).mean()
    vol_ratio = float(v.iloc[-1] / vol_ma20.iloc[-1]) if vol_ma20.iloc[-1] > 0 else 1.0
    range20 = float((c.iloc[-20:].max() - c.iloc[-20:].min()) / last)

    score, tags = 0, []
    if pos <= 0.35:
        score += 2
        tags.append(f"近一年低位区(pos={pos:.2f})")
    elif pos <= 0.55:
        score += 1
        tags.append(f"中低位(pos={pos:.2f})")
    if kv < 35 and jv < 40:
        score += 2
        tags.append(f"KDJ低位K{kv:.0f}J{jv:.0f}")
    if kv > kv_p and dv > dv_p and kv < 50:
        score += 1
        tags.append("KDJ拐头")
    if range20 < 0.18:
        score += 1
        tags.append(f"横盘收窄({range20 * 100:.0f}%)")
    if 0.8 <= vol_ratio <= 2.5 and chg > -5:
        score += 1
        tags.append(f"量能温和(vol比{vol_ratio:.1f})")
    if last < ma20.iloc[-1] and ma20.iloc[-1] > ma60.iloc[-1] * 0.98:
        score += 1
        tags.append("回踩均线")
    if chg > 4 or jv > 85:
        score -= 3
        tags.append("不追")

    stop = round(float(l.iloc[-20:].min()) * 0.95, 2)
    risk = round((last - stop) / last * 100, 1)
    if risk <= 12:
        score += 1
        tags.append(f"止损约{risk}%")

    action = "观望"
    if score >= 6:
        action = "捡漏观察池A"
    elif score >= 4:
        action = "捡漏观察池B"

    return {
        "code": code.split(".")[1],
        "name": name,
        "price": round(last, 2),
        "pct": round(chg, 2),
        "pos": round(pos, 2),
        "k": round(kv, 1),
        "j": round(jv, 1),
        "score": score,
        "action": action,
        "stop": stop,
        "risk_pct": risk,
        "amount": float(df["amount"].iloc[-1]),
        "tags": "；".join(tags),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--end", default="2025-09-23", help="扫描截止交易日")
    args = parser.parse_args()
    end = args.end
    start = pd.Timestamp(end) - pd.DateOffset(months=6)
    start_s = start.strftime("%Y-%m-%d")

    lg = bs.login()
    if lg.error_code != "0":
        print(lg.error_msg, file=sys.stderr)
        return 1

    names = load_names()
    codes = fetch_codes(end)
    print(f"代码池 {len(codes)} 只，截止 {end}")

    cheap = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(last_bar, c, end): c for c in codes}
        for f in as_completed(futs):
            r = f.result()
            if r and PRICE_MIN <= r[1] <= PRICE_MAX and r[3] >= AMOUNT_MIN:
                cheap.append(r)

    cheap_df = pd.DataFrame(
        cheap, columns=["code", "close", "pct", "amount", "turn"]
    ).sort_values("amount", ascending=False)
    top = cheap_df.head(80)["code"].tolist()
    print(f"流动性过滤后 {len(cheap_df)} 只，深研前 {len(top)} 只")

    rows = []
    for i, code in enumerate(top):
        name = names.get(code, "")
        try:
            row = analyze(code, name, end, start_s)
            if row:
                rows.append(row)
        except Exception as e:
            print(f"skip {code}: {e}", file=sys.stderr)
        if (i + 1) % 20 == 0:
            print(f"  深研进度 {i + 1}/{len(top)}")

    out = pd.DataFrame(rows).sort_values(["score", "amount"], ascending=[False, False])
    out_path = "/workspace/scripts/cheap_small_cap_pick_latest.csv"
    out.to_csv(out_path, index=False)

    print("\n=== 捡漏观察池 Top 15 ===\n")
    cols = ["code", "name", "price", "pct", "pos", "k", "j", "score", "action", "stop", "risk_pct"]
    print(out[cols].head(15).to_string(index=False))
    print(f"\n完整结果: {out_path}")
    bs.logout()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
