#!/usr/bin/env python3
"""
A股 MA5 加速筛选器

基于 MA5 滚动窗口公式，筛选「T4 低价日即将滚出 + 短期趋势向上 +
涨停时 MA5 有望金叉 MA10」的标的。

用法:
    python ma5_screener.py                    # 全市场扫描
    python ma5_screener.py --code 601899      # 单股分析
    python ma5_screener.py --limit 200        # 仅扫描前200只（测试）
    python ma5_screener.py --min-score 5      # 最低得分过滤
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Optional

import baostock as bs
import pandas as pd


@dataclass
class ScreenResult:
    code: str
    name: str
    close: float
    ma5: float
    ma5_prev: float
    ma10: float
    t4: float
    t4_ratio: float
    accel_factor: float
    vol_ratio: float
    limit_up_price: float
    ma5_at_limit: float
    min_above_ma5_pct: float
    score: int
    signals: str


def limit_up_pct(code: str, name: str) -> float:
    """根据板块/ST 状态返回涨跌幅限制。"""
    num = code.split(".")[-1]
    if "ST" in name.upper():
        return 0.05
    if num.startswith(("688", "300")):
        return 0.20
    if num.startswith(("8", "4")):
        return 0.30
    return 0.10


def is_a_share(code: str) -> bool:
    """过滤指数，保留 A 股个股。"""
    num = code.split(".")[-1]
    if num.startswith(("000", "001", "002", "003", "300", "301")):
        return code.startswith("sz.")
    if num.startswith(("600", "601", "603", "605", "688")):
        return code.startswith("sh.")
    if num.startswith(("8", "4")):
        return code.startswith("bj.")
    return False


def calc_metrics(code: str, name: str, df: pd.DataFrame) -> Optional[ScreenResult]:
    """计算单只股票的 MA5 筛选指标。"""
    if len(df) < 10:
        return None

    closes = df["close"].astype(float).tolist()
    volumes = df["volume"].astype(float).tolist()

    t = closes[-1]
    t1, t2, t3, t4, t5 = closes[-2], closes[-3], closes[-4], closes[-5], closes[-6]

    ma5 = sum(closes[-5:]) / 5
    ma5_prev = sum(closes[-6:-1]) / 5
    ma10 = sum(closes[-10:]) / 10

    recent5 = closes[-5:]
    t4_is_lowest = t4 <= min(recent5)
    t4_ratio = t4 / t if t > 0 else 0
    accel_factor = (t - t4) / 5
    trend_up = t > t1 > t2
    ma5_rising = ma5 > ma5_prev
    above_ma5 = t > ma5

    vol_today = volumes[-1]
    vol_avg5 = sum(volumes[-5:]) / 5
    vol_ratio = vol_today / vol_avg5 if vol_avg5 > 0 else 0

    pct = limit_up_pct(code, name)
    limit_up = round(t * (1 + pct), 2)
    ma5_at_limit = (limit_up + t + t1 + t2 + t3) / 5

    min_above_ma5 = (t + t1 + t2 + t3) / 4
    min_above_ma5_pct = (min_above_ma5 - t) / t * 100 if t > 0 else 0

    signals: list[str] = []
    score = 0

    if t4_is_lowest:
        score += 2
        signals.append("T4最低")
    if t4_ratio < 0.97:
        score += 1
        signals.append("T4挤出")
    if trend_up:
        score += 2
        signals.append("三连涨")
    if ma5_rising:
        score += 1
        signals.append("MA5上升")
    if above_ma5:
        score += 1
        signals.append("站上MA5")
    if accel_factor > 0.2:
        score += 1
        signals.append("加速>0.2")
    if vol_ratio > 1.0:
        score += 1
        signals.append("放量")
    if ma5_at_limit > ma10:
        score += 2
        signals.append("涨停金叉MA10")

    return ScreenResult(
        code=code,
        name=name,
        close=round(t, 2),
        ma5=round(ma5, 2),
        ma5_prev=round(ma5_prev, 2),
        ma10=round(ma10, 2),
        t4=round(t4, 2),
        t4_ratio=round(t4_ratio, 4),
        accel_factor=round(accel_factor, 3),
        vol_ratio=round(vol_ratio, 2),
        limit_up_price=limit_up,
        ma5_at_limit=round(ma5_at_limit, 2),
        min_above_ma5_pct=round(min_above_ma5_pct, 2),
        score=score,
        signals=",".join(signals),
    )


def fetch_history(code: str, start: str, end: str) -> Optional[pd.DataFrame]:
    rs = bs.query_history_k_data_plus(
        code,
        "date,close,volume",
        start_date=start,
        end_date=end,
        frequency="d",
        adjustflag="3",
    )
    rows = []
    while rs.error_code == "0" and rs.next():
        rows.append(rs.get_row_data())
    if len(rows) < 10:
        return None
    df = pd.DataFrame(rows, columns=rs.fields)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    df = df.dropna(subset=["close"])
    return df if len(df) >= 10 else None


def get_stock_list(trade_date: str) -> list[tuple[str, str]]:
    rs = bs.query_all_stock(day=trade_date)
    stocks = []
    while rs.error_code == "0" and rs.next():
        code, status, name = rs.get_row_data()
        if status == "1" and is_a_share(code):
            stocks.append((code, name))
    return stocks


def scan_one(
    code: str, name: str, start: str, end: str, min_score: int
) -> Optional[ScreenResult]:
    df = fetch_history(code, start, end)
    if df is None:
        return None
    result = calc_metrics(code, name, df)
    if result is None or result.score < min_score:
        return None
    return result


def print_single(result: ScreenResult) -> None:
    print(f"\n{'='*50}")
    print(f"  {result.name} ({result.code})")
    print(f"{'='*50}")
    print(f"  收盘价 T      : {result.close}")
    print(f"  今 MA5        : {result.ma5}")
    print(f"  昨 MA5        : {result.ma5_prev}")
    print(f"  MA10          : {result.ma10}")
    print(f"  T4 (4天前)    : {result.t4}")
    print(f"  T4/T 比值     : {result.t4_ratio:.2%}")
    print(f"  加速系数      : {result.accel_factor}")
    print(f"  量比(5日)     : {result.vol_ratio}")
    print(f"  涨停价        : {result.limit_up_price}")
    print(f"  涨停时 MA5    : {result.ma5_at_limit}")
    print(f"  站上MA5最低涨幅: {result.min_above_ma5_pct:.2f}%")
    print(f"  得分          : {result.score}/11")
    print(f"  信号          : {result.signals}")
    print(f"{'='*50}\n")

    print("  精确反推目标价:")
    print(f"  MA5 持平 (T'=T4)   → {result.t4}")
    print(f"  涨停时 MA5         → {result.ma5_at_limit} (>MA10 {result.ma10})")


def run_batch(args: argparse.Namespace) -> pd.DataFrame:
    end_date = args.end or datetime.now().strftime("%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    start_date = (end_dt - timedelta(days=60)).strftime("%Y-%m-%d")

    lg = bs.login()
    if lg.error_code != "0":
        print(f"登录失败: {lg.error_msg}", file=sys.stderr)
        sys.exit(1)

    try:
        stocks = get_stock_list(end_date)
        if args.limit:
            stocks = stocks[: args.limit]

        print(f"扫描 {len(stocks)} 只股票 ({start_date} ~ {end_date}) ...")

        results: list[ScreenResult] = []
        total = len(stocks)
        for i, (code, name) in enumerate(stocks, 1):
            if i % 50 == 0 or i == total:
                print(f"  进度: {i}/{total}")
            try:
                r = scan_one(code, name, start_date, end_date, args.min_score)
                if r:
                    results.append(r)
            except Exception:
                pass
    finally:
        bs.logout()

    if not results:
        print("未找到符合条件的股票。")
        return pd.DataFrame()

    df = pd.DataFrame([asdict(r) for r in results])
    df = df.sort_values(["score", "accel_factor", "vol_ratio"], ascending=False)
    return df


def code_to_baostock(code: str) -> tuple[str, str]:
    """601899 / sh.601899 → (sh.601899, prefix)"""
    code = code.strip().lower()
    if code.startswith(("sh.", "sz.", "bj.")):
        return code, code.split(".")[0]
    if code.startswith("6"):
        return f"sh.{code}", "sh"
    if code.startswith(("0", "3")):
        return f"sz.{code}", "sz"
    if code.startswith(("8", "4")):
        return f"bj.{code}", "bj"
    raise ValueError(f"无法识别股票代码: {code}")


def run_single(args: argparse.Namespace) -> None:
    bs_code, _ = code_to_baostock(args.code)
    end_date = args.end or datetime.now().strftime("%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    start_date = (end_dt - timedelta(days=60)).strftime("%Y-%m-%d")

    lg = bs.login()
    if lg.error_code != "0":
        print(f"登录失败: {lg.error_msg}", file=sys.stderr)
        sys.exit(1)

    try:
        rs = bs.query_all_stock(day=end_date)
        name = args.code
        while rs.error_code == "0" and rs.next():
            c, _, n = rs.get_row_data()
            if c == bs_code:
                name = n
                break

        df = fetch_history(bs_code, start_date, end_date)
        if df is None:
            print(f"无法获取 {bs_code} 的历史数据")
            sys.exit(1)

        result = calc_metrics(bs_code, name, df)
        if result is None:
            print("数据不足，无法计算")
            sys.exit(1)

        print_single(result)

        # 详细反推
        closes = df["close"].astype(float).tolist()
        t, t1, t2, t3, t4 = (
            closes[-1],
            closes[-2],
            closes[-3],
            closes[-4],
            closes[-5],
        )
        print("  精确反推目标价:")
        print(f"  MA5 持平           → T' = T4 = {t4:.2f}")
        print(f"  收盘落在 MA5 上     → T' = {(t+t1+t2+t3)/4:.2f}")
        for target in [result.ma5, result.ma10, result.ma5 + 0.5]:
            tp = 5 * target - (t + t1 + t2 + t3)
            print(f"  明 MA5 = {target:.2f}      → T' = {tp:.2f}")
    finally:
        bs.logout()


def main() -> None:
    parser = argparse.ArgumentParser(description="A股 MA5 加速筛选器")
    parser.add_argument("--code", help="单股分析，如 601899")
    parser.add_argument("--end", help="截止日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--limit", type=int, help="限制扫描数量（测试用）")
    parser.add_argument("--min-score", type=int, default=5, help="最低得分，默认5")
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="保留参数（baostock 串行请求更稳定，默认1）",
    )
    parser.add_argument(
        "--output", "-o", default="ma5_screen_results.csv", help="结果输出文件"
    )
    args = parser.parse_args()

    if args.code:
        run_single(args)
        return

    df = run_batch(args)
    if df.empty:
        return

    df.to_csv(args.output, index=False, encoding="utf-8-sig")
    print(f"\n找到 {len(df)} 只符合条件的股票，已保存至 {args.output}\n")
    print("Top 20:")
    cols = ["code", "name", "close", "ma5", "ma10", "accel_factor", "vol_ratio", "score", "signals"]
    print(df[cols].head(20).to_string(index=False))


if __name__ == "__main__":
    main()
