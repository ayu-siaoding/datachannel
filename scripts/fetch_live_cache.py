#!/usr/bin/env python3
"""通过单次 MCP 拉取写入 _live_batch.json（由 Agent 调用后执行）。"""

from __future__ import annotations

import json
from pathlib import Path

# 此文件由 Agent 在 MCP 拉取后更新
LIVE_BATCH: dict = {}

if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "data" / "cache" / "_live_batch.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(LIVE_BATCH, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(LIVE_BATCH)} queries to {out}")
