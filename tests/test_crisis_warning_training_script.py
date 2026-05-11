import argparse
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from models.crisis_warning_engine import CrisisWarningEngine
from scripts import train_crisis_warning_model as trainer


class CrisisWarningTrainingScriptTests(unittest.TestCase):
    def _args(self, **overrides):
        values = {
            "domain_preset": "single",
            "market": "us",
            "tickers": "AAPL,MSFT",
            "weights": "0.5,0.5",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def _label_frame(self, rows: int, positives: int) -> pd.DataFrame:
        index = pd.date_range("2024-01-02", periods=rows, freq="B")
        frame = pd.DataFrame(0.01, index=index, columns=CrisisWarningEngine.feature_columns)
        frame["future_horizon_return"] = np.linspace(-0.04, 0.04, rows)
        frame["tail_threshold"] = -0.02
        events = np.zeros(rows, dtype=int)
        events[:positives] = 1
        frame["tail_event"] = events
        return frame

    def test_single_domain_requires_tickers(self) -> None:
        with self.assertRaisesRegex(ValueError, "--tickers"):
            trainer.resolve_training_portfolios(self._args(tickers=""))

    def test_diversified_preset_contains_multiple_markets(self) -> None:
        portfolios = trainer.resolve_training_portfolios(
            self._args(domain_preset="diversified_global", tickers="")
        )

        markets = {portfolio.market for portfolio in portfolios}
        self.assertGreaterEqual(len(portfolios), 3)
        self.assertIn("us", markets)
        self.assertIn("hk", markets)
        self.assertIn("cn", markets)

    def test_domain_training_frame_combines_portfolio_rows(self) -> None:
        frame_a = self._label_frame(80, 6)
        frame_b = self._label_frame(80, 6)
        detail_a = {"name": "a", "market": "us", "n_observations": 100}
        detail_b = {"name": "b", "market": "hk", "n_observations": 100}

        with patch.object(
            trainer,
            "build_portfolio_training_frame",
            side_effect=[(frame_a, detail_a), (frame_b, detail_b)],
        ):
            combined, details, skipped = trainer.build_domain_training_frame(
                portfolios=[
                    trainer.TrainingPortfolio("a", "us", ["AAPL"], []),
                    trainer.TrainingPortfolio("b", "hk", ["0005.HK"], []),
                ],
                risk_engine=object(),
                start_date=pd.Timestamp("2024-01-01").date(),
                end_date=pd.Timestamp("2024-12-31").date(),
                horizon=5,
                tail_quantile=0.05,
                target_method="dynamic_quantile",
                fixed_threshold=None,
                allow_domain_partial=False,
                min_domain_portfolios=2,
            )

        self.assertEqual(len(combined), 160)
        self.assertEqual(len(details), 2)
        self.assertEqual(skipped, [])
        self.assertGreaterEqual(int(combined["tail_event"].sum()), 10)

    def test_domain_training_frame_can_skip_failed_portfolio(self) -> None:
        frame = self._label_frame(140, 12)
        detail = {"name": "usable", "market": "us", "n_observations": 180}

        with patch.object(
            trainer,
            "build_portfolio_training_frame",
            side_effect=[ValueError("provider unavailable"), (frame, detail)],
        ):
            combined, details, skipped = trainer.build_domain_training_frame(
                portfolios=[
                    trainer.TrainingPortfolio("failed", "cn", ["600519"], []),
                    trainer.TrainingPortfolio("usable", "us", ["AAPL"], []),
                ],
                risk_engine=object(),
                start_date=pd.Timestamp("2024-01-01").date(),
                end_date=pd.Timestamp("2024-12-31").date(),
                horizon=5,
                tail_quantile=0.05,
                target_method="dynamic_quantile",
                fixed_threshold=None,
                allow_domain_partial=True,
                min_domain_portfolios=1,
            )

        self.assertEqual(len(combined), 140)
        self.assertEqual(len(details), 1)
        self.assertEqual(skipped[0]["name"], "failed")


if __name__ == "__main__":
    unittest.main()
