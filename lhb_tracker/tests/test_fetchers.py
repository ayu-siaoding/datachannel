import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from lhb_tracker import fetchers


class TestNoDataHandling(unittest.TestCase):
    """akshare 对"当天/当期没有数据"（非交易日/节假日/数据尚未发布）的部分接口，
    不会返回空 DataFrame，而是内部抛出 TypeError("...NoneType..."）。
    这里验证 fetchers 会把这种情况转换成空 DataFrame，而不是让整个任务报错退出。
    """

    def test_no_data_type_error_becomes_empty_dataframe(self):
        def _raise_no_data(*args, **kwargs):
            raise TypeError("'NoneType' object is not subscriptable")

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(fetchers, "CACHE_DIR", Path(tmp)):
                result = fetchers._cached_call("fake", "20260101", _raise_no_data)
        self.assertTrue(result.empty)

    def test_cached_empty_result_reads_back_as_empty_dataframe(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(fetchers, "CACHE_DIR", Path(tmp)):
                def _raise_no_data(*args, **kwargs):
                    raise TypeError("'NoneType' object is not subscriptable")

                first = fetchers._cached_call("fake2", "20260101", _raise_no_data, ttl_days=None)
                self.assertTrue(first.empty)

                # 第二次应命中缓存，不再调用 fn，同样返回空表而不报错。
                def _should_not_be_called(*args, **kwargs):
                    raise AssertionError("不应该重新发起请求")

                second = fetchers._cached_call("fake2", "20260101", _should_not_be_called, ttl_days=None)
                self.assertTrue(second.empty)

    def test_genuine_network_error_still_raises_after_retries(self):
        def _raise_network_error(*args, **kwargs):
            raise ConnectionError("boom")

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(fetchers, "CACHE_DIR", Path(tmp)):
                with patch.object(fetchers.time, "sleep", return_value=None):
                    with self.assertRaises(RuntimeError):
                        fetchers._cached_call("fake3", "20260101", _raise_network_error, retries=2)


if __name__ == "__main__":
    unittest.main()
