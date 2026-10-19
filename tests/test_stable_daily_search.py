"""Three-laptop daily research keeps streams and accounting independent."""

from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from analysis.stable_daily_search import best_screening, candidates, evaluate, evaluate_collective


class StableDailySearchTest(unittest.TestCase):
    def test_independent_streams_and_zero_daily_profit(self):
        streams = []

        def play(settings, run, thresholds, stop, checkpoint, stream):
            streams.append(stream)
            run.update(profit=(.1, -.2, .1)[(len(streams) - 1) % 3], rounds=1,
                       wagered=.1, status="max_rounds")

        with patch("analysis.stable_daily_search._play_run", side_effect=play):
            result = evaluate(candidates()[0], 2, keep_days=True)
        self.assertEqual(len(set(streams)), 6)
        self.assertEqual(result["group"]["negative_rate"], 0)
        self.assertEqual(result["group"]["nonpositive_rate"], 100)
        self.assertEqual(result["group"]["zero_days"], 2)
        self.assertEqual(result["group"]["avg_profit"], 0)
        self.assertEqual(result["group"]["avg_rounds"], 3)
        self.assertEqual(result["laptops"][1]["avg_profit"], -.2)
        json.dumps(result, allow_nan=False)

    def test_actual_engine_supports_six_and_freezes_screen_choice(self):
        settings = deepcopy(candidates()[0])
        settings.update(target_profit=.2, max_rounds=2)
        settings["mine_config"]["medium"] = 0
        result = evaluate(settings, 2)
        self.assertEqual(result["group"]["avg_profit"], 1.74)
        self.assertEqual(result["laptops"][0]["avg_rounds"], 1)
        self.assertGreater(result["group"]["negative_ci_high"], 0)
        other = deepcopy(result)
        other["group"].update(negative_rate=1, avg_profit=10)
        self.assertIs(best_screening([other, result]), result)
        with self.assertRaises(ValueError):
            evaluate(settings, 0)
        collective = evaluate_collective(settings, 2)
        self.assertEqual(collective["settings"]["starting_cash"], 3000)
        self.assertEqual(collective["settings"]["max_rounds"], 6)
        self.assertEqual(collective["group"]["avg_profit"], 3.48)
        self.assertFalse(collective["implemented_in_real_bot"])


if __name__ == "__main__":
    unittest.main()
