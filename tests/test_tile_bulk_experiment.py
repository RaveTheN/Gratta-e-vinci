"""Research comparisons must not learn the tested board before choosing."""

from copy import deepcopy
import random
import unittest
from unittest.mock import Mock

from analysis.tile_bulk_experiment import SyntheticTileOutcomes, compare_settings
from game_config import WIN_MULTIPLIERS
from test_bulk_simulation import snapshot


class TileExperimentTest(unittest.TestCase):
    def test_previous_history_only_and_financial_engine_parity(self):
        counts = {d: [0, 0] + [10]*23 for d in ("low", "medium", "high")}
        source = SyntheticTileOutcomes({"low": 3, "medium": 6, "high": 10}, counts, True, "world", "selection")
        source.selection.shuffle = Mock(side_effect=lambda order: None)
        source.world.sample = Mock(return_value=[0, 3, 4] + [i for i in range(25) if i not in (0, 3, 4)])
        # Choosing before the update selects tile0 and loses; learning first would
        # falsely choose tile1 and win against the already-known board.
        self.assertEqual(source(3, 1), 0)
        self.assertEqual(counts["low"][0], 0)
        self.assertEqual(source.counts["low"][0], 1)
        settings = snapshot(starting_cash=10, target_profit=2,
                            mine_config={"low": 0, "medium": 6, "high": 10})
        settings["win_multipliers"] = deepcopy(WIN_MULTIPLIERS)
        settings["win_multipliers"]["low"][1] = 2
        previous = random.getstate()
        result = compare_settings([settings], 4)["configurations"][0]
        self.assertEqual(random.getstate(), previous)
        self.assertEqual(result["random"]["avg_profit"], 2)
        self.assertEqual(result["history"]["avg_profit"], 2)
        self.assertEqual(result["mean_profit_difference"], 0)
