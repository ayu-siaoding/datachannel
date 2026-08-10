#!/usr/bin/env python3
"""Rough backtest: 30-minute momentum entry, hold 2-3 days (CN A-shares sample)."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent / "data"
ROUND_TRIP_COST = 0.0015  # ~0.15% round-trip (commission + stamp + slippage proxy)


@dataclass
class Bar:
    ts: datetime
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class Trade:
    symbol: str
    entry_ts: str
    exit_ts: str
    entry: float
    exit: float
    ret: float
    ret_net: float
    hold_days: int
    reason: str
    signal_ret: float


def parse_bars(raw: list[dict[str, Any]]) -> list[Bar]:
    bars: list[Bar] = []
    for r in raw:
        ts = datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00"))
        # A-share session timestamps are in UTC; convert to China date via +8h
        local = ts.astimezone(timezone.utc).replace(tzinfo=None)
        # Longbridge A-share intraday timestamps appear as UTC clock equal to Beijing wall clock minus 8h
        # e.g. 06:00Z = 14:00 Beijing. Use Beijing date.
        beijing_date = (ts.timestamp() + 8 * 3600)
        bj = datetime.utcfromtimestamp(beijing_date)
        bars.append(
            Bar(
                ts=ts,
                date=bj.strftime("%Y-%m-%d"),
                open=float(r["open"]),
                high=float(r["high"]),
                low=float(r["low"]),
                close=float(r["close"]),
                volume=float(r["volume"] or 0),
            )
        )
    bars.sort(key=lambda b: b.ts)
    return bars


def daily_closes(bars: list[Bar]) -> dict[str, float]:
    out: dict[str, float] = {}
    for b in bars:
        out[b.date] = b.close
    return out


def ma20_by_date(daily: dict[str, float]) -> dict[str, float]:
    dates = sorted(daily)
    closes = [daily[d] for d in dates]
    ma: dict[str, float] = {}
    for i, d in enumerate(dates):
        if i + 1 < 20:
            continue
        ma[d] = sum(closes[i - 19 : i + 1]) / 20
    return ma


def day_open_map(bars: list[Bar]) -> dict[str, float]:
    out: dict[str, float] = {}
    for b in bars:
        if b.date not in out:
            out[b.date] = b.open
    return out


def unique_dates_after(dates: list[str], start_date: str, n: int) -> str | None:
    """Return the date that is n trading days after start_date (0 = same day)."""
    if start_date not in dates:
        return None
    i = dates.index(start_date)
    j = i + n
    if j >= len(dates):
        return None
    return dates[j]


def simulate_symbol(
    symbol: str,
    bars: list[Bar],
    *,
    signal_pct: float,
    vol_mult: float,
    max_day_chg: float,
    use_ma_filter: bool,
    stop_loss: float | None,
    take_profit: float | None,
    hold_days: int,
    one_trade_per_day: bool,
) -> list[Trade]:
    if len(bars) < 40:
        return []

    daily = daily_closes(bars)
    dates = sorted(daily)
    ma20 = ma20_by_date(daily)
    day_opens = day_open_map(bars)

    # index bars by date for exit-at-day-close
    last_bar_idx_of_date: dict[str, int] = {}
    for i, b in enumerate(bars):
        last_bar_idx_of_date[b.date] = i

    trades: list[Trade] = []
    cooldown_until_idx = -1
    traded_dates: set[str] = set()

    vol_window = 20
    for i in range(vol_window, len(bars) - 1):
        if i < cooldown_until_idx:
            continue

        b = bars[i]
        bar_ret = (b.close / b.open - 1.0) if b.open > 0 else 0.0
        if bar_ret < signal_pct:
            continue

        avg_vol = sum(x.volume for x in bars[i - vol_window : i]) / vol_window
        if avg_vol <= 0 or b.volume < vol_mult * avg_vol:
            continue

        d_open = day_opens.get(b.date)
        if not d_open:
            continue
        day_chg = b.close / d_open - 1.0
        if day_chg > max_day_chg:
            continue

        if use_ma_filter:
            m = ma20.get(b.date)
            if m is None or b.close < m:
                continue

        if one_trade_per_day and b.date in traded_dates:
            continue

        # enter next bar open
        entry_bar = bars[i + 1]
        entry = entry_bar.open
        if entry <= 0:
            continue

        exit_date = unique_dates_after(dates, entry_bar.date, hold_days)
        if exit_date is None:
            continue
        exit_idx = last_bar_idx_of_date[exit_date]

        exit_price = bars[exit_idx].close
        reason = f"time_{hold_days}d"
        exit_ts = bars[exit_idx].ts.isoformat()

        # path check for stop / take-profit on subsequent bars
        for j in range(i + 1, exit_idx + 1):
            bj = bars[j]
            # intrabar stop/tp approximation: stop first if both hit (conservative)
            if stop_loss is not None and bj.low <= entry * (1 + stop_loss):
                exit_price = entry * (1 + stop_loss)
                reason = "stop"
                exit_ts = bj.ts.isoformat()
                exit_idx = j
                break
            if take_profit is not None and bj.high >= entry * (1 + take_profit):
                exit_price = entry * (1 + take_profit)
                reason = "take_profit"
                exit_ts = bj.ts.isoformat()
                exit_idx = j
                break

        ret = exit_price / entry - 1.0
        ret_net = ret - ROUND_TRIP_COST
        # actual hold calendar trading days from entry date to exit bar date
        actual_hold = dates.index(bars[exit_idx].date) - dates.index(entry_bar.date)

        trades.append(
            Trade(
                symbol=symbol,
                entry_ts=entry_bar.ts.isoformat(),
                exit_ts=exit_ts,
                entry=entry,
                exit=exit_price,
                ret=ret,
                ret_net=ret_net,
                hold_days=actual_hold,
                reason=reason,
                signal_ret=bar_ret,
            )
        )
        traded_dates.add(b.date)
        cooldown_until_idx = exit_idx  # no overlapping position per symbol
    return trades


def summarize(name: str, trades: list[Trade]) -> dict[str, Any]:
    if not trades:
        return {"name": name, "n": 0}
    rets = [t.ret_net for t in trades]
    wins = [r for r in rets if r > 0]
    losses = [r for r in rets if r <= 0]
    avg = sum(rets) / len(rets)
    # compounded if sequential equal-weight one-at-a-time globally is hard;
    # report avg trade + win rate + expectancy
    expectancy = avg
    gross = 1.0
    for r in rets:
        gross *= 1 + r
    # max drawdown on equity of sequential trades (order by entry)
    ordered = sorted(trades, key=lambda t: t.entry_ts)
    eq = 1.0
    peak = 1.0
    mdd = 0.0
    for t in ordered:
        eq *= 1 + t.ret_net
        peak = max(peak, eq)
        mdd = min(mdd, eq / peak - 1)
    reasons: dict[str, int] = {}
    for t in trades:
        reasons[t.reason] = reasons.get(t.reason, 0) + 1
    return {
        "name": name,
        "n": len(trades),
        "win_rate": len(wins) / len(rets),
        "avg_ret_net": avg,
        "median_ret_net": sorted(rets)[len(rets) // 2],
        "avg_win": (sum(wins) / len(wins)) if wins else 0.0,
        "avg_loss": (sum(losses) / len(losses)) if losses else 0.0,
        "expectancy": expectancy,
        "compound_all_trades": gross - 1,
        "max_dd_trade_seq": mdd,
        "exit_reasons": reasons,
        "best": max(rets),
        "worst": min(rets),
    }


def fmt_pct(x: float | None) -> str:
    if x is None:
        return "-"
    return f"{x * 100:.2f}%"


def main() -> None:
    files = sorted(DATA_DIR.glob("*.json"))
    universe: dict[str, list[Bar]] = {}
    for f in files:
        raw = json.loads(f.read_text())
        if not isinstance(raw, list) or not raw:
            continue
        universe[f.stem] = parse_bars(raw)

    configs = [
        dict(
            name="裸追30m涨≥1.5%/持有2日/无过滤无止损",
            signal_pct=0.015,
            vol_mult=0.0,
            max_day_chg=9.9,
            use_ma_filter=False,
            stop_loss=None,
            take_profit=None,
            hold_days=2,
            one_trade_per_day=True,
        ),
        dict(
            name="裸追30m涨≥1.5%/持有3日/无过滤无止损",
            signal_pct=0.015,
            vol_mult=0.0,
            max_day_chg=9.9,
            use_ma_filter=False,
            stop_loss=None,
            take_profit=None,
            hold_days=3,
            one_trade_per_day=True,
        ),
        dict(
            name="规则版A：放量+未疯涨+MA20/止损-3%/止盈+6%/持有3日",
            signal_pct=0.015,
            vol_mult=1.5,
            max_day_chg=0.07,
            use_ma_filter=True,
            stop_loss=-0.03,
            take_profit=0.06,
            hold_days=3,
            one_trade_per_day=True,
        ),
        dict(
            name="规则版B：更严信号≥2%+放量2x+MA20/止损-3%/止盈+8%/持有2日",
            signal_pct=0.02,
            vol_mult=2.0,
            max_day_chg=0.06,
            use_ma_filter=True,
            stop_loss=-0.03,
            take_profit=0.08,
            hold_days=2,
            one_trade_per_day=True,
        ),
        dict(
            name="规则版C：同A但仅持有2日",
            signal_pct=0.015,
            vol_mult=1.5,
            max_day_chg=0.07,
            use_ma_filter=True,
            stop_loss=-0.03,
            take_profit=0.06,
            hold_days=2,
            one_trade_per_day=True,
        ),
    ]

    all_results = []
    all_trades_dump: dict[str, list[dict[str, Any]]] = {}

    date_min = min(b.date for bars in universe.values() for b in bars)
    date_max = max(b.date for bars in universe.values() for b in bars)

    for cfg in configs:
        name = cfg.pop("name")
        trades: list[Trade] = []
        for sym, bars in universe.items():
            trades.extend(simulate_symbol(sym, bars, **cfg))
        cfg["name"] = name  # restore not needed
        summary = summarize(name, trades)
        summary["symbols"] = len(universe)
        summary["period"] = f"{date_min} ~ {date_max}"
        all_results.append(summary)
        all_trades_dump[name] = [
            {
                "symbol": t.symbol,
                "entry_ts": t.entry_ts,
                "exit_ts": t.exit_ts,
                "entry": t.entry,
                "exit": t.exit,
                "ret_net": t.ret_net,
                "reason": t.reason,
                "signal_ret": t.signal_ret,
            }
            for t in sorted(trades, key=lambda x: x.entry_ts)
        ]
        # put name back into cfg dict for clarity in loop - actually we popped name
        # re-add for next - no, each cfg is separate

    # restore names into configs list already consumed - fine

    out = {
        "universe": sorted(universe.keys()),
        "n_symbols": len(universe),
        "period": f"{date_min} ~ {date_max}",
        "assumptions": {
            "entry": "信号K线下一根30m开盘价",
            "cost_round_trip": ROUND_TRIP_COST,
            "stop_tp_model": "后续K线内先判止损再判止盈（偏保守）",
            "overlap": "单标的持仓不重叠；每天最多1次信号入场",
            "note": "样本池有限，非全市场；结果仅供方法验证，不构成投资建议",
        },
        "results": all_results,
    }

    out_path = Path(__file__).resolve().parent / "results_summary.json"
    trades_path = Path(__file__).resolve().parent / "results_trades.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    trades_path.write_text(json.dumps(all_trades_dump, ensure_ascii=False, indent=2))

    print("=" * 72)
    print(f"样本: {len(universe)} 只A股 | 区间: {date_min} ~ {date_max}")
    print(f"成本假设: 双边合计 {ROUND_TRIP_COST*100:.2f}%")
    print("=" * 72)
    for s in all_results:
        print(f"\n【{s['name']}】")
        if s["n"] == 0:
            print("  无交易")
            continue
        print(f"  交易次数: {s['n']}")
        print(f"  胜率: {fmt_pct(s['win_rate'])}")
        print(f"  平均单笔净收益: {fmt_pct(s['avg_ret_net'])}")
        print(f"  中位数净收益: {fmt_pct(s['median_ret_net'])}")
        print(f"  平均盈利 / 平均亏损: {fmt_pct(s['avg_win'])} / {fmt_pct(s['avg_loss'])}")
        print(f"  顺序复利(仅示意): {fmt_pct(s['compound_all_trades'])}")
        print(f"  交易序列最大回撤: {fmt_pct(s['max_dd_trade_seq'])}")
        print(f"  最好/最差: {fmt_pct(s['best'])} / {fmt_pct(s['worst'])}")
        print(f"  退出原因: {s['exit_reasons']}")
    print("\n结果已写入:", out_path)


if __name__ == "__main__":
    main()
