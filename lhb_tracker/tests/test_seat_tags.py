import unittest

from lhb_tracker.seat_tags import tag_seat


class TestSeatTags(unittest.TestCase):
    def test_institution_seat(self):
        tag = tag_seat("机构专用")
        self.assertEqual(tag.category, "机构")

    def test_northbound_seat(self):
        tag = tag_seat("深股通专用")
        self.assertEqual(tag.category, "北向")
        tag2 = tag_seat("沪股通专用")
        self.assertEqual(tag2.category, "北向")

    def test_known_hot_money_seat(self):
        tag = tag_seat("东方财富证券股份有限公司拉萨东环路第二证券营业部")
        self.assertEqual(tag.category, "游资")
        self.assertIn("拉萨", tag.label)

    def test_unknown_seat_defaults_to_pending(self):
        tag = tag_seat("某某证券股份有限公司某某路证券营业部")
        self.assertEqual(tag.category, "待定")

    def test_non_string_input(self):
        tag = tag_seat(None)
        self.assertEqual(tag.category, "待定")
        self.assertEqual(tag.label, "未知席位")


if __name__ == "__main__":
    unittest.main()
