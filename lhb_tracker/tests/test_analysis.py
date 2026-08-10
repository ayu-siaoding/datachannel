import unittest
from unittest.mock import patch

import pandas as pd

from lhb_tracker import analysis


class TestDailyOverview(unittest.TestCase):
    def test_splits_institution_vs_non_institution_net_buy(self):
        detail = pd.DataFrame([
            {
                "代码": "000011", "名称": "深物业A", "上榜日": "2026-08-07",
                "收盘价": 8.54, "涨跌幅": 10.05, "龙虎榜净买额": 3_000_000.0,
                "上榜原因": "日涨幅偏离值达到7%的前5只证券",
            },
            {
                "代码": "600000", "名称": "浦发银行", "上榜日": "2026-08-07",
                "收盘价": 10.0, "涨跌幅": -5.0, "龙虎榜净买额": -1_000_000.0,
                "上榜原因": "日跌幅偏离值达到7%的前5只证券",
            },
        ])
        jgmmtj = pd.DataFrame([
            {"代码": "000011", "买方机构数": 1, "卖方机构数": 0,
             "机构买入总额": 2_000_000.0, "机构卖出总额": 0.0, "机构买入净额": 2_000_000.0},
        ])

        with patch.object(analysis.fetchers, "get_lhb_detail", return_value=detail), \
             patch.object(analysis.fetchers, "get_lhb_jgmmtj", return_value=jgmmtj):
            result = analysis.daily_overview("20260807")

        self.assertEqual(len(result), 2)
        row_a = result[result["代码"] == "000011"].iloc[0]
        self.assertEqual(row_a["机构买入净额"], 2_000_000.0)
        self.assertEqual(row_a["非机构净买额(游资/散户/北向)"], 1_000_000.0)

        row_b = result[result["代码"] == "600000"].iloc[0]
        self.assertEqual(row_b["机构买入净额"], 0.0)
        self.assertEqual(row_b["非机构净买额(游资/散户/北向)"], -1_000_000.0)

    def test_empty_detail_returns_empty(self):
        with patch.object(analysis.fetchers, "get_lhb_detail", return_value=pd.DataFrame()):
            result = analysis.daily_overview("20260807")
        self.assertTrue(result.empty)


class TestZtGameReport(unittest.TestCase):
    def test_computes_zhaban_rate_and_ladder(self):
        zt = pd.DataFrame([
            {"代码": "300001", "名称": "A股票", "连板数": 3, "封板资金": 5_000_000.0, "所属行业": "电子"},
            {"代码": "300002", "名称": "B股票", "连板数": 1, "封板资金": 1_000_000.0, "所属行业": "医药"},
            {"代码": "300003", "名称": "C股票", "连板数": 1, "封板资金": 2_000_000.0, "所属行业": "化工"},
        ])
        zb = pd.DataFrame([{"代码": "300004", "名称": "D股票"}])
        dt = pd.DataFrame(columns=["代码", "名称"])
        strong = pd.DataFrame([{"代码": "300005", "名称": "E股票"}])

        with patch.object(analysis.fetchers, "get_zt_pool", return_value=zt), \
             patch.object(analysis.fetchers, "get_zb_pool", return_value=zb), \
             patch.object(analysis.fetchers, "get_dt_pool", return_value=dt), \
             patch.object(analysis.fetchers, "get_strong_pool", return_value=strong):
            report = analysis.zt_game_report("20260807")

        self.assertEqual(report.zt_count, 3)
        self.assertEqual(report.zb_count, 1)
        self.assertEqual(report.dt_count, 0)
        self.assertAlmostEqual(report.zhaban_rate, 1 / 4)
        self.assertEqual(report.ladder, {3: 1, 1: 2})
        self.assertEqual(report.top_seal_amount.iloc[0]["代码"], "300001")
        md = report.to_markdown()
        self.assertIn("涨停家数: 3", md)


if __name__ == "__main__":
    unittest.main()
