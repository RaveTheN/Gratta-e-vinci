"""Funded paths identify every lower-capital month interruption, not group loss."""

import math
import unittest

from analysis.medium_bankroll import combine, mathematical_bound, required_capital_cents, run_chunk


class MediumBankrollTest(unittest.TestCase):
    def test_reserved_stakes_and_daily_closes_both_constrain_initial_cash(self):
        month = {"minimum_cash_per_pc": [997.00, 999, 998, 999],
                 "minimum_daily_closing_cash_per_pc": [999, 998, 997, 999]}
        self.assertEqual(required_capital_cents(month), 310)
        month["minimum_cash_per_pc"][0] = 996.5
        self.assertEqual(required_capital_cents(month), 350)
        month = {"minimum_cash_per_pc": [999.90] * 4,
                 "minimum_daily_closing_cash_per_pc": [1000] * 4}
        self.assertEqual(required_capital_cents(month), 10)

    def test_direct_paired_low_cash_matches_fully_funded_reference_classification(self):
        seed = 987654321
        reference = run_chunk((2, 3000, seed))
        required = [required_capital_cents(row, 3000) for row in reference["monthly_rows"]]
        for capital in (10, 100, 500, 3000):
            actual = run_chunk((2, capital, seed))
            flags = [row["days_with_insufficient_pc_funds"] > 0 for row in actual["monthly_rows"]]
            self.assertEqual(flags, [value > capital for value in required])
            self.assertEqual(actual["simulation"]["initial_bankroll_per_laptop"], capital / 100)
        merged = combine([reference, reference])
        self.assertEqual(merged["months"], 4)
        self.assertEqual(merged["days"], 120)

    def test_positive_adjustment_root_and_twenty_euro_bound(self):
        result = mathematical_bound(20)
        rate = result["adjustment_rate_per_eur"]
        self.assertAlmostEqual(.57 * math.exp(-rate * .08) + .43 * math.exp(rate * .10), 1)
        self.assertGreater(rate, .65)
        self.assertLess(result["any_of_four_unfunded_ever_upper_probability"], .00001)


if __name__ == "__main__":
    unittest.main()
