"""Enumerate short paths, including the profit floor latch and spending rule."""

from itertools import product
import unittest

from analysis.collective_exact import WIN_PROBABILITY, collective_distribution
from analysis.collective_floor_lock import floor_lock_distribution


class CollectiveFloorLockTest(unittest.TestCase):
    def test_all_short_paths_and_latched_principal(self):
        for target in (.02, .1, 1, 3):
            for cap in (1, 2, 4, 7):
                negative = zero = positive = profit = rounds = target_mass = floor_mass = latch_mass = 0.0
                for outcomes in product((False, True), repeat=cap):
                    balance = count = 0
                    weight = 1.0
                    latched = stopped = hit_target = stopped_floor = False
                    for won in outcomes:
                        weight *= WIN_PROBABILITY if won else 1 - WIN_PROBABILITY
                        if stopped:
                            continue
                        if latched:
                            self.assertGreaterEqual(balance - 10, 0)
                        balance += 58 if won else -10
                        count += 1
                        latched = latched or balance > 0
                        if latched:
                            self.assertGreaterEqual(balance, 0)
                            hit_target = balance >= round(target * 100)
                            stopped_floor = not hit_target and balance < 10
                            stopped = hit_target or stopped_floor
                    negative += weight * (balance < 0)
                    zero += weight * (balance == 0)
                    positive += weight * (balance > 0)
                    profit += weight * balance / 100
                    rounds += weight * count
                    target_mass += weight * hit_target
                    floor_mass += weight * stopped_floor
                    latch_mass += weight * latched
                row = floor_lock_distribution(target, (cap,), trim_threshold=0)[0]
                for name, expected in (("negative_probability", negative), ("zero_probability", zero),
                                       ("positive_probability", positive), ("mean_profit_eur", profit),
                                       ("expected_total_rounds", rounds), ("target_reached_probability", target_mass),
                                       ("floor_stop_probability", floor_mass), ("floor_activated_probability", latch_mass)):
                    self.assertAlmostEqual(row[name], expected, places=12)
                self.assertLess(row["mass_balance_error"], 1e-12)

    def test_negative_risk_equals_unlocked_first_positive_search(self):
        baseline = collective_distribution(.02, (200,), trim_threshold=0)[0]
        for target in (1, 3, 5, 10):
            row = floor_lock_distribution(target, (200,), trim_threshold=0)[0]
            self.assertAlmostEqual(row["negative_probability"], baseline["negative_probability"], places=12)
            self.assertGreater(row["zero_probability"], 0)
            self.assertGreaterEqual(row["mean_profit_eur"], baseline["mean_profit_eur"])
            self.assertEqual(row["minimum_possible_profit_after_floor_activation_eur"], 0)
        with self.assertRaises(ValueError):
            floor_lock_distribution(0)

    def test_first_phase_loss_limit_absorbs_early(self):
        cap, target, limit = 8, .1, .7
        negative = profit = rounds = loss_mass = 0.0
        for outcomes in product((False, True), repeat=cap):
            balance = count = 0
            weight = 1.0
            latched = stopped = hit_loss = False
            for won in outcomes:
                weight *= WIN_PROBABILITY if won else 1 - WIN_PROBABILITY
                if stopped:
                    continue
                balance += 58 if won else -10
                count += 1
                latched = latched or balance > 0
                hit_loss = not latched and balance <= -round(limit * 100)
                stopped = hit_loss or (latched and (balance < 10 or balance >= round(target * 100)))
            negative += weight * (balance < 0)
            profit += weight * balance / 100
            rounds += weight * count
            loss_mass += weight * hit_loss
        row = floor_lock_distribution(target, (cap,), trim_threshold=0, loss_limit=limit)[0]
        self.assertAlmostEqual(row["negative_probability"], negative, places=12)
        self.assertAlmostEqual(row["mean_profit_eur"], profit, places=12)
        self.assertAlmostEqual(row["expected_total_rounds"], rounds, places=12)
        self.assertAlmostEqual(row["loss_stop_probability"], loss_mass, places=12)
        self.assertGreater(row["loss_stop_probability"], 0)
        self.assertLess(row["mass_balance_error"], 1e-12)
        with self.assertRaises(ValueError):
            floor_lock_distribution(3, loss_limit=1)


if __name__ == "__main__":
    unittest.main()
