import asyncio
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from backend import main as api
from backend import market_snapshot
from backend.market_snapshot import build_market_snapshot


class FakeMarketSnapshotFetcher:
    def __init__(self, failed_symbol: str | None = None, single_row_symbol: str | None = None) -> None:
        self.failed_symbol = failed_symbol
        self.single_row_symbol = single_row_symbol
        self.calls: list[str] = []
        self.last_source = "cache"
        self.last_source_detail = "cache (test)"
        self.data_warnings: list[str] = []
        self.cache_disabled = False

    def disable_cache(self) -> None:
        self.cache_disabled = True

    def fetch_us_equity(self, symbol, start_date, end_date):
        self.calls.append(symbol)
        if symbol == self.failed_symbol:
            raise RuntimeError("provider unavailable")
        dates = ["2026-05-12"] if symbol == self.single_row_symbol else ["2026-05-11", "2026-05-12"]
        closes = [103.0] if symbol == self.single_row_symbol else [100.0, 103.0]
        frame = pd.DataFrame(
            {
                "Date": pd.to_datetime(dates),
                "Close": closes,
            }
        )
        self.last_source = "cache"
        self.last_source_detail = f"cache ({symbol})"
        return SimpleNamespace(data=frame)


class MarketSnapshotTests(unittest.TestCase):
    def test_hk_snapshot_uses_requested_market_indices(self) -> None:
        fetcher = FakeMarketSnapshotFetcher()

        result = build_market_snapshot(
            "hk",
            fetcher,
            now_utc=datetime(2026, 5, 12, 4, 30, tzinfo=timezone.utc),
        )

        self.assertEqual(fetcher.calls, ["^HSI", "HSTECH.HK", "^HSCE"])
        self.assertEqual(result.market, "hk")
        self.assertEqual(result.session_status, "lunch_break")
        self.assertEqual(result.indices[0].name_zh, "恒生指数")
        self.assertEqual(result.indices[0].price, 103.0)
        self.assertEqual(result.indices[0].change_percent, 3.0)

    def test_snapshot_degrades_failed_index_without_failing_response(self) -> None:
        fetcher = FakeMarketSnapshotFetcher(failed_symbol="HSTECH.HK")

        result = build_market_snapshot(
            "hk",
            fetcher,
            now_utc=datetime(2026, 5, 12, 2, 0, tzinfo=timezone.utc),
        )

        self.assertEqual(len(result.indices), 3)
        failed = [index for index in result.indices if index.symbol == "HSTECH.HK"][0]
        self.assertEqual(failed.status, "unavailable")
        self.assertIn("provider unavailable", failed.warning)

    def test_single_row_index_uses_chart_previous_close_metadata(self) -> None:
        fetcher = FakeMarketSnapshotFetcher(single_row_symbol="HSTECH.HK")

        with patch.object(
            market_snapshot,
            "_fetch_yahoo_chart_meta",
            return_value={"regularMarketPrice": 103.0, "chartPreviousClose": 100.0},
        ):
            result = build_market_snapshot(
                "hk",
                fetcher,
                now_utc=datetime(2026, 5, 12, 2, 0, tzinfo=timezone.utc),
            )

        hstech = [index for index in result.indices if index.symbol == "HSTECH.HK"][0]
        self.assertEqual(hstech.price, 103.0)
        self.assertEqual(hstech.change, 3.0)
        self.assertEqual(hstech.change_percent, 3.0)

    def test_force_refresh_prefers_chart_metadata_quote(self) -> None:
        fetcher = FakeMarketSnapshotFetcher()

        with patch.object(
            market_snapshot,
            "_fetch_yahoo_chart_meta",
            return_value={
                "regularMarketPrice": 108.0,
                "regularMarketPreviousClose": 102.0,
                "regularMarketChange": 6.0,
                "regularMarketChangePercent": 5.882,
                "regularMarketTime": 1778580000,
                "exchangeTimezoneName": "Asia/Hong_Kong",
            },
        ):
            result = build_market_snapshot(
                "hk",
                fetcher,
                now_utc=datetime(2026, 5, 12, 2, 0, tzinfo=timezone.utc),
                force_refresh=True,
            )

        hstech = [index for index in result.indices if index.symbol == "HSTECH.HK"][0]
        self.assertEqual(hstech.price, 108.0)
        self.assertEqual(hstech.change, 8.0)
        self.assertEqual(hstech.change_percent, 8.0)
        self.assertEqual(hstech.source, "yahoo_chart")
        self.assertIn(":", hstech.asof_date or "")

    def test_endpoint_returns_market_snapshot_contract(self) -> None:
        fetcher = FakeMarketSnapshotFetcher()

        with patch.object(api, "_make_fetcher", return_value=fetcher):
            result = asyncio.run(api.get_market_snapshot("hk"))

        self.assertEqual(result.market, "hk")
        self.assertEqual([index.symbol for index in result.indices], ["^HSI", "HSTECH.HK", "^HSCE"])

    def test_endpoint_force_refresh_disables_fetcher_cache(self) -> None:
        fetcher = FakeMarketSnapshotFetcher()

        with patch.object(api, "_make_fetcher", return_value=fetcher):
            result = asyncio.run(api.get_market_snapshot("hk", force_refresh=True))

        self.assertEqual(result.market, "hk")
        self.assertTrue(fetcher.cache_disabled)


if __name__ == "__main__":
    unittest.main()
