#!/usr/bin/env python3
"""从 Longbridge MCP 拉取日K并写入 sample_data/（需在 Cursor 中调用 MCP 后粘贴，或手动运行）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SYMBOLS = [
    "510300.SH",
    "510050.SH",
    "512890.SH",
    "600519.SH",
    "601318.SH",
    "600036.SH",
    "300750.SZ",
    "002594.SZ",
    "601899.SH",
]

OUT = Path(__file__).resolve().parent / "sample_data"


def save(symbol: str, data: list) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{symbol}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"saved {path} ({len(data)} bars)")


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python3 fetch_data.py <symbol>.json ...")
        print("或:   python3 fetch_data.py --stdin  # 从 stdin 读 {symbol: [...]} ")
        sys.exit(1)
    if sys.argv[1] == "--stdin":
        blob = json.load(sys.stdin)
        for sym, data in blob.items():
            save(sym, data)
        return
    for arg in sys.argv[1:]:
        p = Path(arg)
        sym = p.stem
        save(sym, json.loads(p.read_text()))


if __name__ == "__main__":
    main()
