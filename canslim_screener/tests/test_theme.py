"""题材周期、涨停基因、事件催化 单元测试。"""

from __future__ import annotations

from canslim_screener.models import TdxResponse
from canslim_screener.parser import parse_tdx_response
from canslim_screener.theme_cycle import ThemePhase, analyze_theme_market, detect_stock_phase
from canslim_screener.theme_scorer import coarse_filter_stock, _detect_catalysts
from canslim_screener.config import ThemeThresholds


def _pool(key: str, rows: list, headers: list) -> dict:
    resp = parse_tdx_response({"meta": {"code": 0, "total": len(rows)}, "headers": headers, "data": rows}, key)
    from canslim_screener.parser import rows_to_records
    return {r.code: r for r in rows_to_records(resp)}


def test_detect_explosion_phase():
    headers = ["POS", "market", "sec_code", "sec_name", "now_price", "chg", "所属行业",
               "连续涨停天数", "几天几板", "涨停打开次数", "涨停原因"]
    pools = {
        "tc_continuous_board": _pool("tc", [
            ["1", "1", "603758", "秦安股份", "13.95", "10.02", "@汽车零部件@", "4", "4天4板", "0", "人形机器人"],
        ], headers),
    }
    phase, reasons = detect_stock_phase("603758", pools)
    assert phase == ThemePhase.EXPLOSION
    assert any("连板" in r for r in reasons)


def test_detect_recession_high_opens():
    headers = ["POS", "market", "sec_code", "sec_name", "now_price", "chg", "所属行业",
               "连续涨停天数", "涨停打开次数"]
    pools = {
        "l_limit_up": _pool("l", [
            ["1", "1", "600272", "开开实业", "15.70", "10.02", "@医药商业@", "4", "35"],
        ], headers),
    }
    phase, _ = detect_stock_phase("600272", pools)
    assert phase == ThemePhase.RECESSION


def test_analyze_theme_market_explosion():
    headers = ["POS", "market", "sec_code", "sec_name", "now_price", "chg", "所属行业",
               "连续涨停天数", "涨停打开次数"]
    data = []
    for i, (code, name, days) in enumerate([
        ("603758", "秦安股份", "4"), ("300862", "蓝盾光电", "3"),
        ("000802", "北京文化", "3"), ("600683", "京投发展", "3"),
        ("605286", "同力天启", "3"), ("002248", "华东数控", "3"),
    ]):
        data.append([str(i+1), "1", code, name, "10.00", "10.00", "@测试@", days, "0"])
    resp = TdxResponse(meta={"code": 0, "total": 6}, headers=headers, data=data)
    snap = analyze_theme_market(resp)
    assert snap.market_phase == ThemePhase.EXPLOSION


def test_catalyst_detection():
    headers = ["POS", "market", "sec_code", "sec_name", "now_price", "chg", "所属行业", "涨停原因"]
    pools = {
        "l_limit_up": _pool("l", [
            ["1", "1", "603087", "甘李药业", "75.60", "10.00", "@生物制品@", "创新药.业绩预增"],
        ], headers),
        "ec_bid_win": _pool("b", [["1", "0", "603087", "甘李药业", "75.60", "0", "@生物制品@"]],
                            ["POS", "market", "sec_code", "sec_name", "now_price", "chg", "所属行业"]),
    }
    cats = _detect_catalysts("603087", pools)
    assert "业绩" in cats or "订单" in cats


def test_coarse_filter():
    headers_board = ["POS", "market", "sec_code", "sec_name", "now_price", "chg", "所属行业",
                     "连续涨停天数", "几天几板", "涨停打开次数", "涨停原因"]
    headers_gene = ["POS", "market", "sec_code", "sec_name", "now_price", "chg0#", "所属行业", "选股名称"]
    headers_turn = ["POS", "market", "sec_code", "sec_name", "now_price", "chg", "所属行业", "换手率(%)<br>2026.08.12"]
    pools = {
        "tc_continuous_board": _pool("tc", [
            ["1", "1", "603758", "秦安股份", "13.95", "10.02", "@汽车零部件@", "3", "3天3板", "0", "人形机器人"],
        ], headers_board),
        "lg_limit_gene": _pool("lg", [
            ["1", "1", "603758", "秦安股份", "13.95", "10.02", "@汽车零部件@", "【@100天内经常涨停@】"],
        ], headers_gene),
        "lg_turnover": _pool("lt", [
            ["1", "1", "603758", "秦安股份", "13.95", "10.02", "@汽车零部件@", "8.5"],
        ], headers_turn),
        "s_float_mcap": _pool("mc", [
            ["1", "1", "603758", "秦安股份", "13.95", "10.02", "@汽车零部件@", "5000000000.00"],
        ], ["POS", "market", "sec_code", "sec_name", "now_price", "chg", "所属行业", "最新流通市值(元)<br>2026.08.12"]),
        "l_limit_up": _pool("l", [
            ["1", "1", "603758", "秦安股份", "13.95", "10.02", "@汽车零部件@", "3", "3天3板", "0", "人形机器人.重组"],
        ], headers_board),
    }
    passed, notes = coarse_filter_stock("603758", pools, ThemeThresholds())
    assert passed
    assert any("爆发期" in n for n in notes)
