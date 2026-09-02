"""加载 AI 科技观察池配置。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - optional at import time
    yaml = None  # type: ignore[assignment]

CONFIG_PATH = Path(__file__).resolve().parent / "config" / "watchlist.yaml"


def load_config(path: Path | None = None) -> dict[str, Any]:
    """读取 watchlist.yaml，返回字典。"""
    cfg_path = path or CONFIG_PATH
    text = cfg_path.read_text(encoding="utf-8")
    if yaml is None:
        raise ImportError("需要 PyYAML：pip install pyyaml")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"配置文件格式错误: {cfg_path}")
    return data


def iter_symbols(
    config: dict[str, Any] | None = None,
    *,
    market: str | None = None,
    layer: str | None = None,
    bucket: str | None = None,
) -> list[dict[str, Any]]:
    """
    扁平化遍历标的。

    market: us | cn
    layer: compute | model_platform | terminal_scenario | infrastructure
    bucket: core | elastic | hedge（infrastructure 层可能有 hedge）
    """
    cfg = config or load_config()
    results: list[dict[str, Any]] = []

    markets = [market] if market else ["us", "cn"]
    for mkt in markets:
        mkt_data = cfg.get(mkt, {})
        if not isinstance(mkt_data, dict):
            continue
        layers = [layer] if layer else list(mkt_data.keys())
        for lyr in layers:
            lyr_data = mkt_data.get(lyr, {})
            if not isinstance(lyr_data, dict):
                continue
            buckets = [bucket] if bucket else list(lyr_data.keys())
            for bkt in buckets:
                items = lyr_data.get(bkt, [])
                if not isinstance(items, list):
                    continue
                for item in items:
                    if not isinstance(item, dict) or "symbol" not in item:
                        continue
                    results.append(
                        {
                            **item,
                            "market": mkt,
                            "layer": lyr,
                            "bucket": bkt,
                        }
                    )
    return results


def symbols_for_strategy(strategy: str, config: dict[str, Any] | None = None) -> list[str]:
    """按 strategy_defaults 返回 symbol 列表。"""
    cfg = config or load_config()
    defaults = cfg.get("strategy_defaults", {}).get(strategy)
    if not defaults:
        raise KeyError(f"未知策略: {strategy}")

    symbols: list[str] = []
    for mkt in defaults.get("markets", []):
        for lyr in defaults.get("layers", []):
            for pri in defaults.get("priority", ["core"]):
                for item in iter_symbols(cfg, market=mkt, layer=lyr, bucket=pri):
                    sym = item["symbol"]
                    if sym not in symbols:
                        symbols.append(sym)
    return symbols


def to_longbridge_batch(config: dict[str, Any] | None = None) -> dict[str, list[str]]:
    """按市场分组，便于 Longbridge quote 批量查询。"""
    grouped: dict[str, list[str]] = {"us": [], "cn": []}
    for item in iter_symbols(config):
        mkt = item["market"]
        sym = item["symbol"]
        if sym not in grouped[mkt]:
            grouped[mkt].append(sym)
    return grouped


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="AI 科技观察池")
    parser.add_argument(
        "--strategy",
        help="按策略筛选，如 emotion_cycle / options_iv",
    )
    parser.add_argument(
        "--market",
        choices=["us", "cn"],
        help="按市场筛选",
    )
    parser.add_argument(
        "--layer",
        help="按产业链分层筛选",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="JSON 输出",
    )
    args = parser.parse_args()

    if args.strategy:
        syms = symbols_for_strategy(args.strategy)
        if args.json:
            print(json.dumps(syms, ensure_ascii=False, indent=2))
        else:
            for s in syms:
                print(s)
        return

    items = iter_symbols(market=args.market, layer=args.layer)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        for item in items:
            print(
                f"{item['symbol']}\t{item.get('name', '')}\t"
                f"{item['market']}/{item['layer']}/{item['bucket']}"
            )


if __name__ == "__main__":
    main()
