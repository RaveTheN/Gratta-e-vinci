from collections import Counter
import unittest
from unittest.mock import patch

from analysis import collective_parallel as parallel
from analysis import medium_fixed_two as fixed


class FixedTwoTest(unittest.TestCase):
    def test_fixed_tiles_open_in_order_on_a_complete_board(self):
        class Board:
            def __init__(self, mines):
                self.mines, self.requests = mines, []

            def sample(self, population, count):
                self.requests.append((list(population), count))
                return self.mines

        for mines, expected in (([0, 2, 3, 4, 5, 6], (1, False)),
                                ([1, 2, 3, 4, 5, 6], (2, False)),
                                ([2, 3, 4, 5, 6, 7], (2, True))):
            with self.subTest(mines=mines):
                board = Board(mines)
                self.assertEqual(fixed.fixed_board_round(board), expected)
                self.assertEqual(board.requests, [(list(range(25)), 6)])
        with self.assertRaises(ValueError):
            fixed.fixed_board_round(Board([]), 6)

    def test_every_pc_round_gets_a_new_board_and_cash_reconciles(self):
        calls = []

        def record(rng, picks=2):
            calls.append((rng, rng.getstate()))
            return fixed.fixed_board_round(rng, picks)

        timing = {"play": 1.0, "tile": 1.0, "reveal": 0.0, "between": 0.0, "after_loss": 0.0}
        with patch.object(parallel, "sample_round", side_effect=record):
            result = parallel.simulate_day("fixed-board-streams", timing, laptop_count=4,
                                           starting_cash_cents=[2000] * 4, picks=2, payout_cents=18,
                                           round_cap=3)
        self.assertEqual(sorted(Counter(rng for rng, _ in calls).values()), [3] * 4)
        self.assertEqual(len({state for _, state in calls}), 12)
        self.assertEqual(result["pc_rounds"], [3] * 4)
        self.assertEqual(sum(result["pc_final_cash_cents"]) - 8000, round(result["profit"] * 100))
        self.assertTrue(all(value >= 0 for value in result["pc_minimum_cash_cents"]))

    def test_unfunded_laptops_do_not_draw_or_inspect_a_board(self):
        timing = {"play": 1.0, "tile": 1.0, "reveal": 0.0, "between": 0.0, "after_loss": 0.0}
        with patch.object(parallel, "sample_round", return_value=(2, True)) as sample:
            result = parallel.simulate_day("no-peeking", timing, laptop_count=4,
                                           starting_cash_cents=[0, 9, 10, 20], picks=2,
                                           payout_cents=18, round_cap=1)
        self.assertEqual(sample.call_count, 2)
        self.assertEqual(result["pc_rounds"], [0, 0, 1, 1])
        self.assertEqual(result["pc_minimum_cash_cents"], [0, 9, 0, 10])
        self.assertEqual(result["pc_final_cash_cents"], [0, 9, 18, 28])

    def test_worker_pins_the_complete_plan_and_restores_the_sampler(self):
        original = parallel.sample_round

        def inspect(arguments):
            self.assertEqual(arguments, (7, 4, 2, 240))
            self.assertIs(parallel.sample_round, fixed.fixed_board_round)
            return "result"

        with patch.object(fixed.two, "run_chunk", side_effect=inspect):
            self.assertEqual(fixed.run_chunk(7), "result")
        self.assertIs(parallel.sample_round, original)


if __name__ == "__main__":
    unittest.main()
