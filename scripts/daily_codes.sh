#!/usr/bin/env bash
# 每个交易日 09:20 运行：按 short-theme 方法输出观察池代码到文件
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export TZ=Asia/Shanghai
export PATH="${HOME}/.local/bin:${PATH}"
cd "$ROOT"

mkdir -p "$ROOT/outputs/logs"
DAY="$(date +%Y%m%d)"
LOG="$ROOT/outputs/logs/premarket_${DAY}.log"
OUT="$ROOT/outputs/codes_${DAY}.txt"
JSON="$ROOT/outputs/scan_${DAY}.json"

python3 -m pip install -q -r requirements.txt >>"$LOG" 2>&1 || true

{
  echo "=== $(date '+%F %T %Z') ==="
  python3 "$ROOT/scripts/premarket_scan.py" \
    --method short-theme \
    --mode "${MODE:-relay}" \
    --out "$JSON"
  python3 "$ROOT/scripts/premarket_scan.py" \
    --method short-theme \
    --mode "${MODE:-relay}" \
    --codes-only | tee "$OUT"
  echo
} >>"$LOG" 2>&1

echo "codes -> $OUT"
echo "log   -> $LOG"
echo "json  -> $JSON"
