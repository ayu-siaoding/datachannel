#!/usr/bin/env python3
"""美股期权盘前/盘中扫描：PCR、标的价、财报窗口、简易信号。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "config" / "universe.yaml"
RULES = ROOT / "config" / "rules.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    if yaml is None:
        raise ImportError("需要 PyYAML：pip install pyyaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _symbols(cfg: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for bucket in cfg.get("symbols", {}).values():
        if not isinstance(bucket, list):
            continue
        for item in bucket:
            if isinstance(item, dict) and "symbol" in item:
                sym = item["symbol"]
                if sym not in out:
                    out.append(sym)
    return out


def _meta(cfg: dict[str, Any], symbol: str) -> dict[str, Any]:
    for bucket in cfg.get("symbols", {}).values():
        if not isinstance(bucket, list):
            continue
        for item in bucket:
            if isinstance(item, dict) and item.get("symbol") == symbol:
                return item
    return {}


def _pcr_signal(pcr: float, thresholds: dict[str, float]) -> str:
    if pcr <= thresholds.get("bullish_crowded", 0.45):
        return "call_crowded"
    if pcr >= thresholds.get("hedge_elevated", 0.75):
        return "put_heavy"
    if pcr >= thresholds.get("neutral_high", 0.65):
        return "slightly_hedged"
    return "neutral"


def _suggest(meta: dict[str, Any], pcr: float | None, signal: str, spot: float | None) -> list[str]:
    notes: list[str] = []
    sym = meta.get("symbol", "")
    earnings = meta.get("earnings")
    if earnings:
        notes.append(f"财报 {earnings}：7 日内优先 calendar / 减 naked short")

    if sym == "TSLA.US" and signal == "call_crowded" and spot:
        notes.append("Call 拥挤 + 盘后偏强：可考虑 bear call spread 或 wait 回踩再 debit call")
    if sym == "NVDA.US" and signal in ("neutral", "slightly_hedged") and spot:
        notes.append("锚定标：优先 7–14 DTE iron condor / put credit spread，不追裸买 call")
    if sym == "MRVL.US" and spot:
        notes.append("正股波动大；期权用价差，DTE>14 或等财报窗口")
    if sym == "AMD.US" and signal == "put_heavy" and spot:
        notes.append("Put 放量但正股偏强：多为对冲；慎追空，可看 7–14 DTE put credit spread")
    if sym == "SOXX.US" and signal == "put_heavy":
        notes.append("半导体 ETF put 偏厚：板块对冲情绪；单名 spread 可略放宽 put 侧")
    if sym in ("COHR.US", "GLW.US", "AAOI.US"):
        notes.append("光模块接力链：LITE 涨后看补涨；只做 spread，单日大涨不追 call")
        if signal == "call_crowded":
            notes.append("Call 拥挤：优先 bear call spread 或等回调")
    if pcr is not None and signal == "put_heavy" and sym not in ("AMD.US", "SOXX.US"):
        notes.append("Put 放量：检查是否对冲；慎追空，可看 put spread 是否过贵")
    if not notes:
        notes.append("无强信号；盘前仅观察 PCR 与标的 gap")
    return notes


def build_report(api_data: dict[str, Any]) -> dict[str, Any]:
    """api_data: {symbol: {quote, option_volume: {c,p}, meta}}"""
    cfg = _load_yaml(CONFIG)
    thresholds = cfg.get("pcr_volume", {})
    rows = []
    for sym, pack in api_data.items():
        q = pack.get("quote") or {}
        ov = pack.get("option_volume") or {}
        c = float(ov.get("c") or 0)
        p = float(ov.get("p") or 0)
        pcr = (p / c) if c > 0 else None
        signal = _pcr_signal(pcr, thresholds) if pcr is not None else "unknown"
        spot = float(q["last_done"]) if q.get("last_done") else None
        meta = pack.get("meta") or {}
        rows.append(
            {
                "symbol": sym,
                "spot": spot,
                "post_market": (q.get("post_market") or {}).get("last_done"),
                "overnight": (q.get("overnight") or {}).get("last_done"),
                "call_volume": int(c),
                "put_volume": int(p),
                "pcr_volume": round(pcr, 3) if pcr is not None else None,
                "pcr_signal": signal,
                "role": meta.get("role"),
                "suggestions": _suggest(meta, pcr, signal, spot),
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_note": "US 收盘后/盘前用；option_quote 需账户期权行情权限",
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="美股期权扫描（需外部注入数据或扩展 MCP 调用）")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--demo", action="store_true", help="演示模式（离线样例）")
    parser.add_argument(
        "--input",
        type=Path,
        help="JSON 文件：{symbol: {quote, option_volume, meta?}}，由 Agent 经 MCP 写入",
    )
    args = parser.parse_args()

    cfg = _load_yaml(CONFIG)

    if args.demo:
        demo = {
            "NVDA.US": {
                "quote": {"last_done": "225.30", "post_market": {"last_done": "225.43"}, "overnight": {"last_done": "225.12"}},
                "option_volume": {"c": "1598078", "p": "829320"},
                "meta": _meta(cfg, "NVDA.US"),
            },
            "TSLA.US": {
                "quote": {"last_done": "339.96", "post_market": {"last_done": "341.51"}, "overnight": {"last_done": "340.27"}},
                "option_volume": {"c": "1330305", "p": "704917"},
                "meta": _meta(cfg, "TSLA.US"),
            },
            "AMD.US": {
                "quote": {"last_done": "483.01", "post_market": {"last_done": "486.85"}, "overnight": {"last_done": "484.56"}},
                "option_volume": {"c": "174212", "p": "147550"},
                "meta": _meta(cfg, "AMD.US"),
            },
            "MRVL.US": {
                "quote": {"last_done": "222.18", "post_market": {"last_done": "224.50"}, "overnight": {"last_done": "223.50"}},
                "option_volume": {"c": "149024", "p": "61325"},
                "meta": _meta(cfg, "MRVL.US"),
            },
            "SOXX.US": {
                "quote": {"last_done": "550.74", "post_market": {"last_done": "552.30"}, "overnight": {"last_done": "549.98"}},
                "option_volume": {"c": "27161", "p": "32447"},
                "meta": _meta(cfg, "SOXX.US"),
            },
            "COHR.US": {
                "quote": {"last_done": "332.73", "post_market": {"last_done": "329.44"}, "overnight": {"last_done": "327.00"}},
                "option_volume": {"c": "120000", "p": "85000"},
                "meta": _meta(cfg, "COHR.US"),
            },
            "GLW.US": {
                "quote": {"last_done": "165.17", "post_market": {"last_done": "158.54"}, "overnight": {"last_done": "159.00"}},
                "option_volume": {"c": "45000", "p": "38000"},
                "meta": _meta(cfg, "GLW.US"),
            },
            "AAOI.US": {
                "quote": {"last_done": "149.74", "post_market": {"last_done": "132.46"}, "overnight": {"last_done": "131.39"}},
                "option_volume": {"c": "980000", "p": "420000"},
                "meta": _meta(cfg, "AAOI.US"),
            },
        }
        report = build_report(demo)
    elif args.input:
        raw = json.loads(args.input.read_text(encoding="utf-8"))
        for sym in raw:
            if "meta" not in raw[sym]:
                raw[sym]["meta"] = _meta(cfg, sym)
        report = build_report(raw)
    else:
        print("请使用 --demo、--input data.json，或让 Agent 调用 Longbridge MCP 后写入 JSON")
        print("符号列表:", ", ".join(_symbols(cfg)))
        return

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"生成时间 UTC: {report['generated_at']}\n")
        for row in report["rows"]:
            print(f"=== {row['symbol']} ({row.get('role')}) ===")
            print(f"  现价/盘后/夜盘: {row['spot']} / {row['post_market']} / {row['overnight']}")
            print(f"  期权量 C/P: {row['call_volume']:,} / {row['put_volume']:,}  PCR={row['pcr_volume']} [{row['pcr_signal']}]")
            for s in row["suggestions"]:
                print(f"  → {s}")
            print()


if __name__ == "__main__":
    main()
