"""Compare the financial recurrence with enumeration of all short paths."""

from itertools import product
import unittest

from analysis.collective_exact import WIN_PROBABILITY, collective_distribution


class CollectiveExactTest(unittest.TestCase):
    def test_brute_paths_and_accounting(self):
        for target in (.1, .5, 1):
            for cap in (1, 2, 4, 7):
                negative = zero = positive = profit = rounds = target_mass = 0.0
                for outcomes in product((False, True), repeat=cap):
                    weight = 1.0
                    balance = count = 0
                    reached = False
                    for won in outcomes:
                        weight *= WIN_PROBABILITY if won else 1 - WIN_PROBABILITY
                        if not reached:
                            balance += 58 if won else -10
                            count += 1
                            reached = balance >= round(target * 100)
                    negative += weight * (balance < 0)
                    zero += weight * (balance == 0)
                    positive += weight * (balance > 0)
                    profit += weight * balance / 100
                    rounds += weight * count
                    target_mass += weight * reached
                row = collective_distribution(target, (cap,), trim_threshold=0)[0]
                for name, expected in (("negative_probability", negative),
                                       ("zero_probability", zero),
                                       ("positive_probability", positive),
                                       ("mean_profit_eur", profit),
                                       ("expected_total_rounds", rounds),
                                       ("target_reached_probability", target_mass)):
                    self.assertAlmostEqual(row[name], expected, places=12)
                self.assertLess(row["mass_balance_error"], 1e-12)
                self.assertAlmostEqual(row["expected_gains_eur"] + row["expected_losses_eur"], profit)

    def test_zero_results_remain_separate_and_invalid_inputs_fail(self):
        row = collective_distribution(100, (34,), trim_threshold=0)[0]
        self.assertGreater(row["zero_probability"], 0)
        self.assertGreater(row["nonpositive_probability"], row["negative_probability"])
        with self.assertRaises(ValueError):
            collective_distribution(0)
        with self.assertRaises(ValueError):
            collective_distribution(1, (0,))

    def test_discarded_tail_bounds_the_numeric_approximation(self):
        full = collective_distribution(3, (300,), trim_threshold=0)[0]
        trimmed = collective_distribution(3, (300,), trim_threshold=1e-5)[0]
        difference = full["negative_probability"] - trimmed["negative_probability"]
        self.assertGreaterEqual(difference, -1e-12)
        self.assertLessEqual(difference, trimmed["omitted_probability_bound"] + 1e-12)
        self.assertLessEqual(abs(full["mean_profit_eur"] - trimmed["mean_profit_eur"]),
                             trimmed["mean_profit_error_bound_eur"] + 1e-12)


if __name__ == "__main__":
    unittest.main()
