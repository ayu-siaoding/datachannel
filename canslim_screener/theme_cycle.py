"""题材周期判断：萌芽期 → 爆发期 → 分化期 → 退潮期。

实战原则：只在爆发期参与，退潮期再好的票也容易被埋。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import StockRecord, TdxResponse
from .parser import find_numeric_field, rows_to_records


class ThemePhase(str, Enum):
  SPROUT = "sprout"           # 萌芽期
  EXPLOSION = "explosion"     # 爆发期 — 唯一建议参与
  DIFFERENTIATION = "diff"    # 分化期
  RECESSION = "recession"     # 退潮期


PHASE_LABELS = {
  ThemePhase.SPROUT: "萌芽期",
  ThemePhase.EXPLOSION: "爆发期 ✅",
  ThemePhase.DIFFERENTIATION: "分化期 ⚠️",
  ThemePhase.RECESSION: "退潮期 ❌",
}


@dataclass
class ThemeCycleSnapshot:
  market_phase: ThemePhase
  continuous_board_count: int
  avg_board_days: float
  high_open_ratio: float
  summary: str

  def to_dict(self) -> dict:
    return {
      "market_phase": self.market_phase.value,
      "continuous_board_count": self.continuous_board_count,
      "avg_board_days": self.avg_board_days,
      "high_open_ratio": self.high_open_ratio,
      "summary": self.summary,
    }


def _limit_days(rec: StockRecord) -> int:
  for key in ("连续涨停天数", "连续涨停天数0#"):
    val = rec.extra.get(key)
    if val is not None and str(val) not in ("", "0"):
      try:
        return int(float(str(val)))
      except ValueError:
        pass
  boards = str(rec.extra.get("几天几板", ""))
  if "天" in boards and "板" in boards:
    try:
      return int(boards.split("天")[0])
    except ValueError:
      pass
  return 0


def _open_count(rec: StockRecord) -> int:
  val = rec.extra.get("涨停打开次数")
  if val is None or val == "":
    return 0
  try:
    return int(float(str(val)))
  except ValueError:
    return 0


def detect_stock_phase(code: str, pools: dict[str, dict[str, StockRecord]]) -> tuple[ThemePhase, list[str]]:
  """单股题材周期判定。"""
  reasons: list[str] = []

  board_rec = (
    pools.get("tc_continuous_board", {}).get(code)
    or pools.get("l_limit_up", {}).get(code)
    or pools.get("n_limit_up_story", {}).get(code)
  )
  strong_rec = pools.get("tc_strong_20d", {}).get(code)
  gene_rec = pools.get("lg_limit_gene", {}).get(code)

  days = _limit_days(board_rec) if board_rec else 0
  opens = _open_count(board_rec) if board_rec else 0
  chg = board_rec.change_pct if board_rec else None

  # 退潮期：连板断裂 + 大幅回落，或高位大量打开
  if board_rec and opens >= 5:
    reasons.append(f"涨停打开 {opens} 次，资金分歧加剧")
    return ThemePhase.RECESSION, reasons
  if board_rec and days >= 2 and chg is not None and chg < 3:
    reasons.append(f"原 {days} 连板，今日涨幅仅 {chg:.1f}%，连板断裂")
    return ThemePhase.RECESSION, reasons

  # 爆发期：连板 ≥ 2，或 20日强势 + 涨停
  if days >= 2:
    reasons.append(f"连板 {days} 天，题材爆发中")
    if opens <= 1:
      reasons.append("封板坚决，打开次数少")
    return ThemePhase.EXPLOSION, reasons

  if strong_rec and board_rec:
    gain = find_numeric_field(strong_rec, "涨幅")
    if gain is not None and gain >= 30:
      reasons.append(f"20日涨幅 {gain:.1f}% + 涨停，强势爆发")
      return ThemePhase.EXPLOSION, reasons

  # 分化期：有涨停但打开频繁，或连板仅 1 天且换手极高
  if board_rec and days == 1 and opens >= 2:
    reasons.append("首板但打开频繁，分化加剧")
    return ThemePhase.DIFFERENTIATION, reasons
  if board_rec and days == 1:
    reasons.append("首板阶段，龙头尚未确认")
    return ThemePhase.DIFFERENTIATION, reasons

  # 萌芽期：有涨停基因/技术启动，尚未形成连板
  if gene_rec:
    tags = str(gene_rec.extra.get("选股名称", ""))
    if "涨停" in tags or "放量" in tags:
      reasons.append("100天内经常涨停 + 放量启动，题材萌芽")
      return ThemePhase.SPROUT, reasons
    reasons.append("历史有涨停基因，等待爆发确认")
    return ThemePhase.SPROUT, reasons

  reasons.append("无明显题材周期信号")
  return ThemePhase.RECESSION, reasons


def analyze_theme_market(limit_up_resp: TdxResponse | None) -> ThemeCycleSnapshot:
  """全市场题材周期（基于涨停池统计）。"""
  if not limit_up_resp or not limit_up_resp.ok:
    return ThemeCycleSnapshot(
      ThemePhase.DIFFERENTIATION, 0, 0.0, 0.0, "涨停数据不可用，默认震荡分化"
    )

  records = rows_to_records(limit_up_resp)
  board_days = [_limit_days(r) for r in records]
  opens = [_open_count(r) for r in records]
  multi_board = [d for d in board_days if d >= 2]
  high_opens = [o for o in opens if o >= 3]

  avg_days = sum(board_days) / len(board_days) if board_days else 0.0
  high_open_ratio = len(high_opens) / len(records) if records else 0.0

  if len(multi_board) >= 5 and avg_days >= 2.0:
    phase = ThemePhase.EXPLOSION
    summary = f"市场题材爆发期：{len(multi_board)} 只连板股，均连板 {avg_days:.1f} 天"
  elif high_open_ratio >= 0.3 or (len(multi_board) <= 2 and len(records) > 20):
    phase = ThemePhase.DIFFERENTIATION
    summary = f"市场分化期：连板股 {len(multi_board)} 只，高打开占比 {high_open_ratio:.0%}"
  elif len(multi_board) == 0 and len(records) < 15:
    phase = ThemePhase.RECESSION
    summary = f"市场退潮期：涨停仅 {len(records)} 只，无连板"
  else:
    phase = ThemePhase.SPROUT
    summary = f"市场萌芽期：涨停 {len(records)} 只，连板股 {len(multi_board)} 只"

  return ThemeCycleSnapshot(
    market_phase=phase,
    continuous_board_count=len(multi_board),
    avg_board_days=round(avg_days, 1),
    high_open_ratio=round(high_open_ratio, 2),
    summary=summary,
  )
