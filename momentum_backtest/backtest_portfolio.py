#!/usr/bin/env python3
"""Portfolio-level simulation: at most N new entries per day, fixed fraction each."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backtest_30m_hold import (
    DATA_DIR,
    ROUND_TRIP_COST,
    Bar,
    parse_bars,
    daily_closes,
    ma20_by_date,
    day_open_map,
    unique_dates_after,
)


@dataclass
class Signal:
    symbol: str
    signal_idx: int
    signal_ts: str
    signal_date: str
    signal_ret: float
    entry_idx: int
    entry: float


def collect_signals(
    symbol: str,
    bars: list[Bar],
    *,
    signal_pct: float,
    vol_mult: float,
    max_day_chg: float,
    use_ma_filter: bool,
) -> list[Signal]:
    daily = daily_closes(bars)
    ma20 = ma20_by_date(daily)
    day_opens = day_open_map(bars)
    out: list[Signal] = []
    vol_window = 20
    for i in range(vol_window, len(bars) - 1):
        b = bars[i]
        bar_ret = b.close / b.open - 1.0 if b.open > 0 else 0.0
        if bar_ret < signal_pct:
            continue
        avg_vol = sum(x.volume for x in bars[i - vol_window : i]) / vol_window
        if avg_vol <= 0 or b.volume < vol_mult * avg_vol:
            continue
        d_open = day_opens.get(b.date)
        if not d_open:
            continue
        if b.close / d_open - 1.0 > max_day_chg:
            continue
        if use_ma_filter:
            m = ma20.get(b.date)
            if m is None or b.close < m:
                continue
        entry_bar = bars[i + 1]
        out.append(
            Signal(
                symbol=symbol,
                signal_idx=i,
                signal_ts=b.ts.isoformat(),
                signal_date=b.date,
                signal_ret=bar_ret,
                entry_idx=i + 1,
                entry=entry_bar.open,
            )
        )
    return out


def simulate_trade_path(
    bars: list[Bar],
    entry_idx: int,
    entry: float,
    hold_days: int,
    stop_loss: float | None,
    take_profit: float | None,
) -> tuple[float, str, str, int]:
    daily = daily_closes(bars)
    dates = sorted(daily)
    last_bar_idx_of_date: dict[str, int] = {}
    for i, b in enumerate(bars):
        last_bar_idx_of_date[b.date] = i
    entry_date = bars[entry_idx].date
    exit_date = unique_dates_after(dates, entry_date, hold_days)
    if exit_date is None:
        return 0.0, "no_exit", "", 0
    exit_idx = last_bar_idx_of_date[exit_date]
    exit_price = bars[exit_idx].close
    reason = f"time_{hold_days}d"
    exit_ts = bars[exit_idx].ts.isoformat()
    for j in range(entry_idx, exit_idx + 1):
        bj = bars[j]
        if stop_loss is not None and bj.low <= entry * (1 + stop_loss):
            return entry * (1 + stop_loss) / entry - 1.0, "stop", bj.ts.isoformat(), dates.index(bj.date) - dates.index(entry_date)
        if take_profit is not None and bj.high >= entry * (1 + take_profit):
            return entry * (1 + take_profit) / entry - 1.0, "take_profit", bj.ts.isoformat(), dates.index(bj.date) - dates.index(entry_date)
    ret = exit_price / entry - 1.0
    hold = dates.index(bars[exit_idx].date) - dates.index(entry_date)
    return ret, reason, exit_ts, hold


def run_portfolio(
    universe: dict[str, list[Bar]],
    *,
    name: str,
    signal_pct: float,
    vol_mult: float,
    max_day_chg: float,
    use_ma_filter: bool,
    stop_loss: float | None,
    take_profit: float | None,
    hold_days: int,
    max_new_per_day: int,
    position_pct: float,
) -> dict[str, Any]:
    all_signals: list[Signal] = []
    for sym, bars in universe.items():
        all_signals.extend(
            collect_signals(
                sym,
                bars,
                signal_pct=signal_pct,
                vol_mult=vol_mult,
                max_day_chg=max_day_chg,
                use_ma_filter=use_ma_filter,
            )
        )

    by_day: dict[str, list[Signal]] = defaultdict(list)
    for s in all_signals:
        by_day[s.signal_date].append(s)

    # active positions: symbol -> exit_date(str from bars date)
    open_pos: dict[str, str] = {}
    equity = 1.0
    peak = 1.0
    mdd = 0.0
    curve = []
    trade_rets = []
    monthly = defaultdict(list)

    for day in sorted(by_day):
        # free symbols whose exit day passed
        open_pos = {sym: ed for sym, ed in open_pos.items() if ed > day}

        cands = sorted(by_day[day], key=lambda x: x.signal_ret, reverse=True)
        taken = 0
        for sig in cands:
            if taken >= max_new_per_day:
                break
            if sig.symbol in open_pos:
                continue
            bars = universe[sig.symbol]
            ret, reason, exit_ts, hold = simulate_trade_path(
                bars,
                sig.entry_idx,
                sig.entry,
                hold_days,
                stop_loss,
                take_profit,
            )
            if reason == "no_exit":
                continue
            ret_net = ret - ROUND_TRIP_COST
            # portfolio impact with fixed fraction
            equity *= 1 + position_pct * ret_net
            peak = max(peak, equity)
            mdd = min(mdd, equity / peak - 1)
            trade_rets.append(ret_net)
            monthly[day[:7]].append(ret_net)
            # approximate exit date = entry date + hold_days trading (store signal day + hold as lock)
            # lock symbol until calendar exit date string from exit_ts
            exit_date = exit_ts[:10] if exit_ts else day
            # exit_ts is UTC iso; better use bars date
            # recompute exit date from hold
            dates = sorted(daily_closes(bars))
            ed = unique_dates_after(dates, bars[sig.entry_idx].date, hold_days) or day
            if reason in ("stop", "take_profit"):
                # unlock sooner using exit_ts beijing-ish date from bar timestamp
                try:
                    ts = datetime.fromisoformat(exit_ts.replace("Z", "+00:00"))
                    bj = datetime.fromtimestamp(ts.timestamp() + 8 * 3600, tz=timezone.utc)
                    ed = bj.strftime("%Y-%m-%d")
                except Exception:
                    pass
            open_pos[sig.symbol] = ed
            taken += 1
            curve.append({"date": day, "equity": equity, "ret_net": ret_net, "symbol": sig.symbol, "reason": reason})

    wins = [r for r in trade_rets if r > 0]
    month_stats = {}
    for m, rs in sorted(monthly.items()):
        month_stats[m] = {
            "n": len(rs),
            "avg": sum(rs) / len(rs),
            "win_rate": sum(1 for r in rs if r > 0) / len(rs),
            "sum_proxy": sum(rs),
        }

    return {
        "name": name,
        "n_trades": len(trade_rets),
        "win_rate": (len(wins) / len(trade_rets)) if trade_rets else 0,
        "avg_trade": (sum(trade_rets) / len(trade_rets)) if trade_rets else 0,
        "final_equity": equity,
        "total_return": equity - 1,
        "max_dd": mdd,
        "position_pct": position_pct,
        "max_new_per_day": max_new_per_day,
        "monthly": month_stats,
        "curve_tail": curve[-5:],
    }


def main() -> None:
    universe: dict[str, list[Bar]] = {}
    for f in sorted(DATA_DIR.glob("*.json")):
        raw = json.loads(f.read_text())
        if isinstance(raw, list) and raw:
            universe[f.stem] = parse_bars(raw)

    setups = [
        dict(
            name="实盘近似-裸追/每天最多2只/各25%仓/持有2日",
            signal_pct=0.015,
            vol_mult=0.0,
            max_day_chg=9.9,
            use_ma_filter=False,
            stop_loss=None,
            take_profit=None,
            hold_days=2,
            max_new_per_day=2,
            position_pct=0.25,
        ),
        dict(
            name="实盘近似-规则B/每天最多2只/各25%仓",
            signal_pct=0.02,
            vol_mult=2.0,
            max_day_chg=0.06,
            use_ma_filter=True,
            stop_loss=-0.03,
            take_profit=0.08,
            hold_days=2,
            max_new_per_day=2,
            position_pct=0.25,
        ),
        dict(
            name="实盘近似-规则A/每天最多1只/50%仓/持有3日",
            signal_pct=0.015,
            vol_mult=1.5,
            max_day_chg=0.07,
            use_ma_filter=True,
            stop_loss=-0.03,
            take_profit=0.06,
            hold_days=3,
            max_new_per_day=1,
            position_pct=0.5,
        ),
        dict(
            name="实盘近似-规则B/每天最多1只/30%仓/更克制",
            signal_pct=0.02,
            vol_mult=2.0,
            max_day_chg=0.06,
            use_ma_filter=True,
            stop_loss=-0.03,
            take_profit=0.08,
            hold_days=2,
            max_new_per_day=1,
            position_pct=0.3,
        ),
    ]

    results = [run_portfolio(universe, **s) for s in setups]
    out = Path(__file__).resolve().parent / "results_portfolio.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2))

    print("=" * 72)
    print("组合层回测（固定仓位，每天限信号数）")
    print("=" * 72)
    for r in results:
        print(f"\n【{r['name']}】")
        print(f"  交易次数: {r['n_trades']}")
        print(f"  胜率: {r['win_rate']*100:.2f}%")
        print(f"  平均单笔: {r['avg_trade']*100:.2f}%")
        print(f"  组合总收益: {r['total_return']*100:.2f}%")
        print(f"  最大回撤: {r['max_dd']*100:.2f}%")
        print("  分月(平均单笔/胜率/笔数):")
        for m, ms in r["monthly"].items():
            print(
                f"    {m}: avg={ms['avg']*100:.2f}% win={ms['win_rate']*100:.1f}% n={ms['n']}"
            )


if __name__ == "__main__":
    main()
