"""Collective research reuses real simulation accounting and keeps zero days distinct."""

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from analysis.collective_bet_search import collective_settings, evaluate
from bulk_simulation import _new_run, _play_run


class CollectiveBetSearchTest(unittest.TestCase):
    def test_actual_core_payout_target_and_settings_unchanged(self):
        settings = collective_settings(.2, 50)
        settings["mine_config"]["medium"] = 0
        original = deepcopy(settings)
        first_win = deepcopy(settings)
        first_win["target_profit"] = .1
        run = _new_run(1, 3000, [])
        _play_run(first_win, run, [], lambda: False, lambda: None, "first-win")
        self.assertEqual(run["profit"], 1.16)
        self.assertEqual(run["rounds"], 1)
        result = evaluate(settings, 2)
        self.assertEqual(result["group"]["avg_profit"], 3.48)
        self.assertEqual(result["group"]["avg_rounds"], 3)
        self.assertEqual(result["group"]["stop_counts"]["target"], 2)
        self.assertEqual(settings, original)
        self.assertIsNone(result["group"]["avg_loss_on_negative_day"])

    def test_zero_negative_statistics_and_independent_streams(self):
        streams = []

        def play(settings, run, thresholds, stop, checkpoint, stream):
            streams.append(stream)
            run.update(profit=(0, -2, -10)[(len(streams) - 1) % 3],
                       rounds=1, wagered=.2, status="max_rounds")

        with patch("analysis.collective_bet_search._play_run", side_effect=play):
            result = evaluate(collective_settings(.2, 50), 3)
        group = result["group"]
        self.assertEqual(len(set(streams)), 3)
        self.assertEqual(group["zero_days"], 1)
        self.assertEqual(group["negative_days"], 2)
        self.assertAlmostEqual(group["negative_rate"], 200 / 3)
        self.assertEqual(group["nonpositive_rate"], 100)
        self.assertEqual(group["avg_loss_on_negative_day"], 6)
        self.assertEqual(group["loss_p95_on_negative_day"], 10)
        self.assertLess(group["negative_ci_low"], group["negative_rate"])
        self.assertGreater(group["negative_ci_high"], group["negative_rate"])
        json.dumps(result, allow_nan=False)
        with self.assertRaises(ValueError):
            evaluate(collective_settings(.2, 50), 0)


if __name__ == "__main__":
    unittest.main()
