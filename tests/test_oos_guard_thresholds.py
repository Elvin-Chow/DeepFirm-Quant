import unittest

import numpy as np

from backend.main import _select_oos_guard_weights


class OOSGuardThresholdTests(unittest.TestCase):
    """Boundary tests for the OOS guard policy selection rule."""

    def setUp(self) -> None:
        self.prior_weights = np.array([0.60, 0.40])
        self.raw_weights = np.array([0.20, 0.80])

    def _metrics(self, final_return: float) -> dict:
        return {"cumulative_returns": [0.0, final_return]}

    def test_disabled_guard_returns_raw_regardless_of_evidence(self) -> None:
        weights, policy = _select_oos_guard_weights(
            self.prior_weights,
            self.raw_weights,
            self._metrics(0.04),
            self._metrics(-0.10),
            prior_score=70.0,
            raw_score=30.0,
            enabled=False,
            raw_excess_return=-0.05,
            raw_information_ratio=-1.0,
        )

        self.assertEqual(policy, "raw")
        np.testing.assert_allclose(weights, self.raw_weights)

    def test_matching_weights_skip_blending(self) -> None:
        weights, policy = _select_oos_guard_weights(
            self.prior_weights,
            self.prior_weights.copy(),
            self._metrics(0.04),
            self._metrics(0.04),
            prior_score=70.0,
            raw_score=70.0,
            enabled=True,
        )

        self.assertEqual(policy, "raw")
        np.testing.assert_allclose(weights, self.prior_weights)

    def test_defensive_blend_requires_both_score_and_return_underperformance(self) -> None:
        weights, policy = _select_oos_guard_weights(
            self.prior_weights,
            self.raw_weights,
            self._metrics(0.05),
            self._metrics(0.03),
            prior_score=80.0,
            raw_score=72.0,
            enabled=True,
        )

        self.assertEqual(policy, "defensive_blend")
        np.testing.assert_allclose(
            weights,
            self.prior_weights * 0.40 + self.raw_weights * 0.60,
        )

    def test_balanced_blend_for_moderate_underperformance(self) -> None:
        weights, policy = _select_oos_guard_weights(
            self.prior_weights,
            self.raw_weights,
            self._metrics(0.05),
            self._metrics(0.04),
            prior_score=70.0,
            raw_score=66.0,
            enabled=True,
        )

        self.assertEqual(policy, "balanced_blend")
        np.testing.assert_allclose(
            weights,
            self.prior_weights * 0.50 + self.raw_weights * 0.50,
        )

    def test_benchmark_underperformance_triggers_balanced_blend(self) -> None:
        weights, policy = _select_oos_guard_weights(
            self.prior_weights,
            self.raw_weights,
            self._metrics(0.0200),
            self._metrics(0.0205),
            prior_score=59.5,
            raw_score=59.0,
            enabled=True,
            raw_excess_return=-0.006,
            raw_information_ratio=-0.25,
        )

        self.assertEqual(policy, "balanced_blend")
        np.testing.assert_allclose(
            weights,
            self.prior_weights * 0.50 + self.raw_weights * 0.50,
        )

    def test_severe_benchmark_underperformance_triggers_defensive_blend(self) -> None:
        weights, policy = _select_oos_guard_weights(
            self.prior_weights,
            self.raw_weights,
            self._metrics(0.040),
            self._metrics(0.025),
            prior_score=58.0,
            raw_score=49.0,
            enabled=True,
            raw_excess_return=-0.016,
            raw_information_ratio=-0.70,
        )

        self.assertEqual(policy, "defensive_blend")
        np.testing.assert_allclose(
            weights,
            self.prior_weights * 0.40 + self.raw_weights * 0.60,
        )

    def test_score_only_loss_does_not_trigger_blend(self) -> None:
        weights, policy = _select_oos_guard_weights(
            self.prior_weights,
            self.raw_weights,
            self._metrics(0.05),
            self._metrics(0.06),
            prior_score=80.0,
            raw_score=70.0,
            enabled=True,
        )

        self.assertEqual(policy, "raw")
        np.testing.assert_allclose(weights, self.raw_weights)

    def test_return_only_loss_does_not_trigger_blend(self) -> None:
        weights, policy = _select_oos_guard_weights(
            self.prior_weights,
            self.raw_weights,
            self._metrics(0.05),
            self._metrics(0.03),
            prior_score=70.0,
            raw_score=72.0,
            enabled=True,
        )

        self.assertEqual(policy, "raw")
        np.testing.assert_allclose(weights, self.raw_weights)

    def test_marginal_outperformance_keeps_raw(self) -> None:
        weights, policy = _select_oos_guard_weights(
            self.prior_weights,
            self.raw_weights,
            self._metrics(0.04),
            self._metrics(0.043),
            prior_score=70.0,
            raw_score=72.0,
            enabled=True,
        )

        self.assertEqual(policy, "raw")
        np.testing.assert_allclose(weights, self.raw_weights)

    def test_clear_outperformance_keeps_raw(self) -> None:
        weights, policy = _select_oos_guard_weights(
            self.prior_weights,
            self.raw_weights,
            self._metrics(0.04),
            self._metrics(0.06),
            prior_score=70.0,
            raw_score=78.0,
            enabled=True,
        )

        self.assertEqual(policy, "raw")
        np.testing.assert_allclose(weights, self.raw_weights)


if __name__ == "__main__":
    unittest.main()
