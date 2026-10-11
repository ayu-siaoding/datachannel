#!/usr/bin/env bash
# 盘前/盘中手动或 cron 调用
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec python3 scripts/gex_heatmap_daily.py --json "$@"
