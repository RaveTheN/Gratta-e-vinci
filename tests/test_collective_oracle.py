"""Independent board primitive agrees with all seven first-mine categories."""

import unittest

from analysis.collective_oracle import (SELECTED_TILES, financial_math, full_board_round,
                                        simultaneous_wilson, validate_boards)
from analysis.collective_parallel import SURVIVAL, sample_round


class CollectiveOracleTest(unittest.TestCase):
    def test_new_complete_board_and_all_first_mine_outcomes(self):
        self.assertEqual(len(set(SELECTED_TILES)), 6)
        boards = []

        class Board:
            def __init__(self, mines):
                self.mines = set(mines)
            def shuffle(self, board):
                self_check.assertEqual(len(board), 25)
                self_check.assertEqual(sum(board), 6)
                boards.append(board)
                board[:] = [tile in self.mines for tile in range(25)]

        class Draw:
            def __init__(self, value):
                self.value = value
            def random(self):
                return self.value

        self_check = self
        previous = 1.0
        for opened, probability in enumerate(SURVIVAL, 1):
            self.assertEqual(full_board_round(Board([opened - 1, 20, 21, 22, 23, 24])), (opened, False))
            self.assertEqual(sample_round(Draw((previous + probability) / 2)), (opened, False))
            previous = probability
        self.assertEqual(full_board_round(Board(range(6, 12))), (6, True))
        self.assertEqual(sample_round(Draw(SURVIVAL[-1] / 2)), (6, True))
        self.assertEqual(len({id(board) for board in boards}), 7)

    def test_financial_edge_rounding_and_intervals(self):
        money = financial_math()
        self.assertAlmostEqual(money["break_even_total_multiplier"], 6.527347781217751)
        self.assertGreater(money["expected_profit_if_actual_winning_payment_0_66_eur"], 0)
        self.assertLess(money["expected_profit_if_actual_winning_payment_0_65_eur"], 0)
        low, high = simultaneous_wilson(15, 100)
        self.assertLess(low, .15)
        self.assertGreater(high, .15)
        validation = validate_boards(40)
        self.assertEqual(sum(row["count"] for row in validation["outcomes"]), 40)
        self.assertAlmostEqual(sum(row["expected_probability"] for row in validation["outcomes"]), 1)
        with self.assertRaises(ValueError):
            validate_boards(0)


if __name__ == "__main__":
    unittest.main()
