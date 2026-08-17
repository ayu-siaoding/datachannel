#!/usr/bin/env python3
"""保存 Longbridge 周线 K 线到 sample_data/。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

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
