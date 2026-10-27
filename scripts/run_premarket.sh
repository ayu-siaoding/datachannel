#!/usr/bin/env bash
# 每个交易日 09:20（Asia/Shanghai）运行短线题材扫描
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export TZ=Asia/Shanghai
export PATH="${HOME}/.local/bin:${PATH}"
cd "$ROOT"
python3 -m pip install -q -r requirements.txt 2>/dev/null || true
python3 "$ROOT/scripts/premarket_scan.py" \
  --method "${METHOD:-short-theme}" \
  --mode "${MODE:-relay}" \
  "$@"
