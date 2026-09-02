"""题材周期 + 涨停基因 + 事件催化 评分与粗筛。"""

from __future__ import annotations

from .config import ThemeThresholds
from .models import DimensionScore, StockRecord
from .parser import find_numeric_field
from .theme_cycle import PHASE_LABELS, ThemePhase, detect_stock_phase

# 事件催化关键词（涨停原因 / 公告 / 主题）
CATALYST_KEYWORDS = {
    "业绩": ["业绩预增", "预增", "扭亏", "业绩大增", "财报高增长"],
    "订单": ["中标", "大单", "合同", "框架协议", "订单"],
    "政策": ["政策", "国资委", "国企改革", "扶持", "补贴"],
    "重组": ["并购", "重组", "资产注入", "收购", "注入", "控股权"],
    "涨价": ["涨价", "提价", "存储", "面板", "周期", "DDR", "NAND", "化工"],
    "产业": ["人形机器人", "AI", "低空经济", "出海", "芯片", "半导体", "创新药", "光伏", "储能"],
}


def _score_tc(
  code: str,
  pools: dict[str, dict[str, StockRecord]],
  max_score: float,
  tradable_only: bool = True,
) -> DimensionScore:
  phase, reasons = detect_stock_phase(code, pools)
  label = PHASE_LABELS[phase]

  if phase == ThemePhase.EXPLOSION:
    score, hit = max_score, True
  elif phase == ThemePhase.SPROUT:
    score, hit = max_score * 0.4, False
    reasons.insert(0, "萌芽期：观察为主，等爆发确认")
  elif phase == ThemePhase.DIFFERENTIATION:
    score, hit = max_score * 0.15, False
    reasons.insert(0, "分化期：只做最强龙头，其余不参与")
  else:
    score, hit = 0.0, False
    reasons.insert(0, "退潮期：不参与")

  if tradable_only and phase != ThemePhase.EXPLOSION:
    hit = False

  reasons.insert(0, f"题材周期：{label}")
  return DimensionScore("TC", hit, score, max_score, reasons)


def _score_lg(
  code: str,
  pools: dict[str, dict[str, StockRecord]],
  thresholds: ThemeThresholds,
  max_score: float,
) -> DimensionScore:
  reasons: list[str] = []
  score = 0.0
  hits = 0

  if code in pools.get("lg_limit_gene", {}):
    score += max_score * 0.4
    hits += 1
    reasons.append("涨停基因：100天内经常涨停")

  turn_rec = pools.get("lg_turnover", {}).get(code)
  if turn_rec:
    turnover = find_numeric_field(turn_rec, "换手率", "自由换手率")
    if turnover is not None:
      if thresholds.turnover_min <= turnover <= thresholds.turnover_max:
        score += max_score * 0.35
        hits += 1
        reasons.append(f"换手充分：{turnover:.1f}%（{thresholds.turnover_min:.0f}-{thresholds.turnover_max:.0f}%）")
      elif turnover > thresholds.turnover_max:
        reasons.append(f"换手率 {turnover:.1f}% 偏高，注意分歧")
      else:
        reasons.append(f"换手率 {turnover:.1f}% 偏低，股性待激活")

  mcap_rec = (
    pools.get("s_float_mcap", {}).get(code)
    or pools.get("c_combo", {}).get(code)
    or pools.get("lg_turnover", {}).get(code)
  )
  if mcap_rec:
    mcap = find_numeric_field(mcap_rec, "流通市值", "自由流通市值")
    if mcap is not None:
      mcap_yi = mcap / 1e8
      if thresholds.float_mcap_min_yi <= mcap_yi <= thresholds.float_mcap_max_yi:
        score += max_score * 0.25
        hits += 1
        reasons.append(f"流通盘适中：{mcap_yi:.1f} 亿")
      elif mcap_yi > thresholds.float_mcap_max_yi:
        reasons.append(f"流通盘 {mcap_yi:.0f} 亿偏大，拉升阻力大")
      else:
        reasons.append(f"流通盘 {mcap_yi:.1f} 亿偏小，易被控盘")

  hit = hits >= thresholds.lg_min_hits
  if not reasons:
    reasons.append("涨停基因不足")
  return DimensionScore("LG", hit, min(score, max_score), max_score, reasons)


def _detect_catalysts(code: str, pools: dict[str, dict[str, StockRecord]]) -> list[str]:
  found: list[str] = []
  texts: list[str] = []

  for key in ("ec_earnings_preview", "c_earnings_preview", "ec_bid_win", "ec_merger",
              "n_limit_up_story", "l_limit_up", "tc_continuous_board"):
    rec = pools.get(key, {}).get(code)
    if not rec:
      continue
    for field in ("涨停原因", "原因揭秘", "预告类型", "预警类型", "类型", "标的及交易简介", "短线主题名称"):
      val = str(rec.extra.get(field, ""))
      if val:
        texts.append(val)

  combined = " ".join(texts)
  for cat, keywords in CATALYST_KEYWORDS.items():
    if any(kw in combined for kw in keywords):
      found.append(cat)

  if code in pools.get("ec_bid_win", {}):
    if "订单" not in found:
      found.append("订单")
  if code in pools.get("ec_merger", {}):
    if "重组" not in found:
      found.append("重组")
  if code in pools.get("ec_earnings_preview", {}) or code in pools.get("c_earnings_preview", {}):
    if "业绩" not in found:
      found.append("业绩")

  return found


def _score_ec(
  code: str,
  pools: dict[str, dict[str, StockRecord]],
  max_score: float,
) -> DimensionScore:
  catalysts = _detect_catalysts(code, pools)
  reasons: list[str] = []
  score = 0.0

  cat_labels = {"业绩": "业绩预增/扭亏", "订单": "中标大单", "政策": "政策扶持",
                "重组": "并购重组/资产注入", "涨价": "行业涨价/景气", "产业": "产业趋势/新赛道"}
  per = max_score / max(len(CATALYST_KEYWORDS), 1)

  for cat in catalysts:
    score += per
    reasons.append(f"事件催化：{cat_labels.get(cat, cat)}")

  hit = len(catalysts) >= 1
  if not hit:
    reasons.append("无明显事件催化")
  return DimensionScore("EC", hit, min(score, max_score), max_score, reasons)


def coarse_filter_stock(
  code: str,
  pools: dict[str, dict[str, StockRecord]],
  thresholds: ThemeThresholds,
) -> tuple[bool, list[str]]:
  """粗筛：先机器过滤，再人工复核。"""
  notes: list[str] = []
  passed = True

  phase, phase_reasons = detect_stock_phase(code, pools)
  if thresholds.require_explosion_phase and phase != ThemePhase.EXPLOSION:
    passed = False
    notes.append(f"❌ 题材周期：{PHASE_LABELS[phase]}（仅爆发期参与）")
  else:
    notes.append(f"✅ 题材周期：{PHASE_LABELS[phase]}")

  lg = _score_lg(code, pools, thresholds, 10.0)
  if not lg.hit:
    passed = False
    notes.append(f"❌ 涨停基因：命中 {sum(1 for r in lg.reasons if '基因' in r or '换手' in r or '流通' in r)}/{thresholds.lg_min_hits} 项")
  else:
    notes.append("✅ 涨停基因：达标")

  ec = _score_ec(code, pools, 10.0)
  if not ec.hit:
    passed = False
    notes.append("❌ 事件催化：无明确催化")
  else:
    notes.append(f"✅ 事件催化：{', '.join(ec.reasons)}")

  notes.extend(phase_reasons)
  return passed, notes
