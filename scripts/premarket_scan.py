#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股短线题材 · 开盘前 10 分钟扫描（排除北交所）
依据：溢价 / 集中 / 共识（空间龙、中军、补涨）

用法:
  python3 scripts/premarket_scan.py
  python3 scripts/premarket_scan.py --mode dragon
  python3 scripts/premarket_scan.py --date 20251027

建议在 Asia/Shanghai 09:20 运行（见 scripts/run_premarket.sh 与 README）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import akshare as ak
import pandas as pd
import requests

SH_TZ = ZoneInfo("Asia/Shanghai")
EM_UT = "7eea3edcaed734bea9cbfc24409ed989"
EM_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/ztb/",
}


def norm_code(raw: str) -> str:
    s = str(raw).strip().lower()
    s = re.sub(r"^(sh|sz|bj)", "", s)
    return s.zfill(6) if s.isdigit() else s


def is_allowed_board(code: str) -> bool:
    c = norm_code(code)
    if not re.fullmatch(r"\d{6}", c):
        return False
    if c.startswith(("4", "8")):  # 北交所等
        return False
    prefix = c[:3]
    allowed = (
        "600",
        "601",
        "603",
        "605",
        "688",
        "000",
        "001",
        "002",
        "003",
        "300",
        "301",
    )
    return any(c.startswith(p) for p in allowed)


def is_st(name: str) -> bool:
    n = str(name).upper()
    return "ST" in n


def trade_dates() -> list[date]:
    cal = ak.tool_trade_date_hist_sina()
    col = cal["trade_date"]
    return sorted(col.tolist())


def resolve_trade_date(as_of: date) -> date:
    days = trade_dates()
    if as_of in days:
        return as_of
    prior = [d for d in days if d <= as_of]
    if not prior:
        raise RuntimeError("交易日历为空或 as_of 过早")
    return prior[-1]


def prev_trade_date(trade_day: date) -> date:
    days = trade_dates()
    idx = days.index(trade_day)
    if idx == 0:
        raise RuntimeError("无上一交易日")
    return days[idx - 1]


def fetch_zt_pool_on(trade_day: date) -> pd.DataFrame:
    """指定交易日收盘时的涨停股池。"""
    d = trade_day.strftime("%Y%m%d")
    try:
        df = ak.stock_zt_pool_em(date=d)
        if not df.empty:
            return df
    except Exception:
        pass
    url = "https://push2ex.eastmoney.com/getTopicZTPool"
    params = {
        "ut": EM_UT,
        "dpt": "wz.ztzt",
        "Pageindex": "0",
        "pagesize": "5000",
        "sort": "fbt:asc",
        "date": d,
    }
    r = requests.get(url, params=params, headers=EM_HEADERS, timeout=20)
    r.raise_for_status()
    pool = (r.json().get("data") or {}).get("pool") or []
    if not pool:
        return pd.DataFrame()
    df = pd.DataFrame(pool)
    if "c" in df.columns:
        df["代码"] = df["c"]
    if "n" in df.columns:
        df["名称"] = df["n"]
    if "lbc" in df.columns:
        df["连板数"] = df["lbc"]
    if "hybk" in df.columns:
        df["所属行业"] = df["hybk"]
    if "amount" in df.columns:
        df["成交额"] = df["amount"]
    return df


def fetch_yesterday_zt_pool(trade_day: date) -> pd.DataFrame:
    """trade_day 当日开盘前扫描时，date 参数传「今天」交易日，返回「昨涨停」池。"""
    d = trade_day.strftime("%Y%m%d")
    url = "https://push2ex.eastmoney.com/getYesterdayZTPool"
    params = {
        "ut": EM_UT,
        "dpt": "wz.ztzt",
        "Pageindex": "0",
        "pagesize": "5000",
        "sort": "zs:desc",
        "date": d,
    }
    r = requests.get(url, params=params, headers=EM_HEADERS, timeout=20)
    r.raise_for_status()
    data_json = r.json()
    pool = (data_json.get("data") or {}).get("pool") or []
    if not pool:
        try:
            prev = ak.stock_zt_pool_previous_em(date=d)
            if not prev.empty:
                return prev
        except Exception:
            pass
        # 备用：上一交易日「涨停股池」= 昨日收盘涨停
        prev_day = prev_trade_date(trade_day)
        return fetch_zt_pool_on(prev_day)
    df = pd.DataFrame(pool)
    rename = {
        "c": "代码",
        "n": "名称",
        "p": "最新价",
        "ztp": "涨停价",
        "zdf": "涨跌幅",
        "amount": "成交额",
        "ltsz": "流通市值",
        "tshare": "总市值",
        "hs": "换手率",
        "zf": "振幅",
        "zs": "涨速",
        "fbt": "昨日封板时间",
        "lbc": "昨日连板数",
        "hybk": "所属行业",
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    if "代码" not in df.columns and "c" in df.columns:
        df["代码"] = df["c"]
    return df


def fetch_spot_tx() -> pd.DataFrame:
    df = ak.stock_zh_a_spot_tx()
    df = df.copy()
    df["code"] = df["code"].astype(str).map(norm_code)
    return df


def attach_auction_premium(zt: pd.DataFrame, spot: pd.DataFrame) -> pd.DataFrame:
    if zt.empty:
        return zt
    out = zt.copy()
    out["代码"] = out["代码"].astype(str).map(norm_code)
    spot_map = spot.set_index("code")
    prems = []
    speeds = []
    for code in out["代码"]:
        if code in spot_map.index:
            row = spot_map.loc[code]
            prems.append(float(row.get("zdf", float("nan"))))
            speeds.append(float(row.get("speed", float("nan"))))
        else:
            prems.append(float("nan"))
            speeds.append(float("nan"))
    out["竞价涨跌幅"] = prems
    out["涨速"] = speeds
    return out


def normalize_zt_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    if "昨日连板数" not in out.columns and "连板数" in out.columns:
        out["昨日连板数"] = out["连板数"]
    return out


def filter_universe(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = normalize_zt_columns(df.copy())
    out["代码"] = out["代码"].astype(str).map(norm_code)
    mask = out["代码"].map(is_allowed_board)
    if "名称" in out.columns:
        mask &= ~out["名称"].astype(str).map(is_st)
    return out.loc[mask].reset_index(drop=True)


def theme_key(row: pd.Series) -> str:
    if "所属行业" in row and pd.notna(row["所属行业"]) and str(row["所属行业"]).strip():
        return str(row["所属行业"]).strip()
    if "短线主题名称" in row and pd.notna(row["短线主题名称"]):
        return str(row["短线主题名称"]).split(".")[0]
    return "其他"


def score_themes(df: pd.DataFrame) -> list[tuple[str, int, float]]:
    """返回 [(主题, 家数, 连板分和)] 降序。"""
    if df.empty:
        return []
    buckets: dict[str, list[float]] = defaultdict(list)
    for _, row in df.iterrows():
        lb = row.get("昨日连板数", row.get("连板数", 0))
        buckets[theme_key(row)].append(float(lb or 0))
    stats = []
    for k, lbs in buckets.items():
        stats.append((k, len(lbs), sum(lbs) + max(lbs) * 2))
    stats.sort(key=lambda x: (x[2], x[1]), reverse=True)
    return stats


def _连板列(df: pd.DataFrame) -> pd.Series:
    for col in ("昨日连板数", "连板数"):
        if col in df.columns:
            return pd.to_numeric(df[col], errors="coerce").fillna(0)
    return pd.Series(0, index=df.index, dtype=float)


def pick_roles(df: pd.DataFrame, main_theme: str) -> dict[str, list[str]]:
    if df.empty:
        return {"空间龙": [], "中军": [], "补涨": []}
    sub = df[df.apply(lambda r: theme_key(r) == main_theme, axis=1)].copy()
    if sub.empty:
        sub = df.copy()
    sub = sub.copy()
    sub["昨日连板数"] = _连板列(sub)
    sub["成交额"] = (
        pd.to_numeric(sub["成交额"], errors="coerce").fillna(0)
        if "成交额" in sub.columns
        else pd.Series(0, index=sub.index, dtype=float)
    )

    dragon = sub.sort_values(
        ["昨日连板数", "成交额"], ascending=[False, False]
    ).head(2)["代码"].tolist()

    rest = sub[~sub["代码"].isin(dragon)]
    mid = rest.sort_values("成交额", ascending=False).head(2)["代码"].tolist()

    catch = rest[
        (rest["昨日连板数"] >= 1) & (rest["昨日连板数"] <= 2)
    ].sort_values("成交额", ascending=False).head(3)["代码"].tolist()

    return {"空间龙": dragon, "中军": mid, "补涨": catch}


def premium_label(zdf: float, mode: str) -> str:
    if pd.isna(zdf):
        return "无竞价数据"
    if zdf >= 7:
        tag = "高开"
    elif zdf >= 3:
        tag = "合格"
    elif zdf >= 0:
        tag = "弱"
    else:
        tag = "低开"
    if mode == "relay" and zdf >= 7:
        tag += "·慎追非核心"
    return tag


def build_watchlist(
    df: pd.DataFrame, roles: dict[str, list[str]], mode: str
) -> list[str]:
    """合并去重后的代码观察池。"""
    codes: list[str] = []
    for k in ("空间龙", "中军", "补涨"):
        codes.extend(roles.get(k, []))
    # 溢价过滤：relay 要求核心 ≥3% 或 dragon 允许分歧低开但要在龙/中军列表
    spot_ok = set()
    for _, row in df.iterrows():
        code = row["代码"]
        zdf = float(row.get("竞价涨跌幅", float("nan")))
        lb = float(row.get("昨日连板数") or 0)
        if code in roles.get("空间龙", []) or code in roles.get("中军", []):
            if mode == "relay":
                if zdf >= 3 or (pd.isna(zdf) and lb >= 2):
                    spot_ok.add(code)
            else:
                if zdf >= -3 or pd.isna(zdf):
                    spot_ok.add(code)
        elif code in roles.get("补涨", []):
            if zdf >= 3:
                spot_ok.add(code)
    ordered = []
    seen = set()
    for c in codes:
        if c in spot_ok and c not in seen:
            ordered.append(c)
            seen.add(c)
    # 若竞价数据缺失，保留角色池
    if not ordered:
        for c in codes:
            if c not in seen:
                ordered.append(c)
                seen.add(c)
    return ordered


def run_scan(trade_day: date, mode: str) -> dict[str, Any]:
    zt_raw = fetch_yesterday_zt_pool(trade_day)
    zt = filter_universe(zt_raw)
    spot = fetch_spot_tx()
    zt = attach_auction_premium(zt, spot)

    themes = score_themes(zt)
    main_theme = themes[0][0] if themes else "（无主题）"
    roles = pick_roles(zt, main_theme)
    watch = build_watchlist(zt, roles, mode)

    premium_rows = []
    for _, row in zt.iterrows():
        zdf = float(row.get("竞价涨跌幅", float("nan")))
        premium_rows.append(
            {
                "代码": row["代码"],
                "名称": row.get("名称", ""),
                "昨日连板数": row.get("昨日连板数"),
                "竞价涨跌幅": None if pd.isna(zdf) else round(zdf, 2),
                "溢价": premium_label(zdf, mode),
            }
        )
    premium_rows.sort(
        key=lambda x: (x["竞价涨跌幅"] is not None, x["竞价涨跌幅"] or -999),
        reverse=True,
    )

    return {
        "扫描时间": datetime.now(SH_TZ).strftime("%Y-%m-%d %H:%M:%S %Z"),
        "交易日": trade_day.isoformat(),
        "上一交易日": prev_trade_date(trade_day).isoformat(),
        "模式": mode,
        "昨涨停数量_过滤后": len(zt),
        "主题材": main_theme,
        "主题排名": [{"主题": t, "家数": n, "强度分": s} for t, n, s in themes[:8]],
        "角色": roles,
        "观察池代码": watch,
        "昨日涨停溢价": premium_rows,
        "数据源": {
            "昨涨停池": "eastmoney getYesterdayZTPool / akshare 备用",
            "竞价": "腾讯全 A  spot zdf（09:20 附近为集合竞价涨幅）",
        },
        "说明": "非投资建议；北交所/ST 已排除。若昨涨停池为空，请在本机网络重试或检查是否为交易日。",
    }


def print_report(result: dict[str, Any]) -> None:
    print(f"# A股短线题材扫描 · {result['扫描时间']}")
    print(f"交易日 {result['交易日']} | 模式 {result['模式']} | 昨涨停 {result['昨涨停数量_过滤后']} 只")
    if result["昨涨停数量_过滤后"] == 0:
        print("\n[警告] 昨涨停池为空：请在可访问东方财富的环境 09:20 运行，或检查 `--date` 是否为交易日。")
    print(f"\n## 主题材\n{result['主题材']}\n")
    print("## 主题强度")
    for t in result["主题排名"][:5]:
        print(f"  - {t['主题']}：{t['家数']} 家，强度 {t['强度分']:.0f}")
    print("\n## 角色 → 代码")
    for role, codes in result["角色"].items():
        print(f"  {role}: {','.join(codes) if codes else '—'}")
    print(f"\n## 观察池（合并）\n{','.join(result['观察池代码']) or '—'}")
    print("\n## 昨日涨停 · 竞价溢价（前 20）")
    for row in result["昨日涨停溢价"][:20]:
        z = row["竞价涨跌幅"]
        zs = f"{z:+.2f}%" if z is not None else "N/A"
        lb = row["昨日连板数"]
        print(
            f"  {row['代码']} {row['名称']}  连板{lb}  竞价{zs}  [{row['溢价']}]"
        )
    print(f"\n{result['说明']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="A股短线题材开盘前扫描")
    parser.add_argument(
        "--mode",
        choices=("relay", "dragon"),
        default="relay",
        help="relay=1～3板接力溢价；dragon=龙头分歧",
    )
    parser.add_argument(
        "--date",
        help="指定交易日 YYYY-MM-DD，默认按 Asia/Shanghai 当前日",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="输出 JSON（默认同时打印人类可读报告）",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="仅输出 JSON",
    )
    parser.add_argument(
        "--out",
        help="将 JSON 结果写入文件，例如 reports/premarket.json",
    )
    args = parser.parse_args()

    if args.date:
        as_of = date.fromisoformat(args.date)
    else:
        as_of = datetime.now(SH_TZ).date()

    trade_day = resolve_trade_date(as_of)
    result = run_scan(trade_day, args.mode)

    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        from pathlib import Path

        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(payload, encoding="utf-8")
    if args.json or args.json_only:
        print(payload)
    if not args.json_only:
        if args.json:
            print("\n---\n")
        print_report(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
