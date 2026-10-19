"""Stress overrides restore shared globals and leave controller accounting intact."""

import unittest
from unittest.mock import patch

from analysis import collective_parallel as parallel
from analysis.collective_stress import all_red_case, stress_case


class CollectiveStressTest(unittest.TestCase):
    def setUp(self):
        self.timing = parallel.timing_from_settings({})

    def test_globals_restore_after_failed_stress(self):
        payout, factory = parallel.PAYOUT, parallel.random.Random
        with patch.object(parallel, "simulate_day", side_effect=RuntimeError("test failure")):
            with self.assertRaises(RuntimeError):
                stress_case(self.timing, 1, payout_cents=65, correlated=True)
        self.assertEqual(parallel.PAYOUT, payout)
        self.assertIs(parallel.random.Random, factory)

    def test_correlated_worlds_use_distinct_objects_and_matching_round_draws(self):
        rngs, values = [], []

        def sample(rng):
            rngs.append(rng)
            values.append(rng.random())
            return 6, True

        with patch.object(parallel, "sample_round", side_effect=sample):
            result = stress_case(self.timing, 1, correlated=True)
        self.assertEqual(len(set(rngs)), 4)
        self.assertEqual(len(set(values[:4])), 1)
        self.assertEqual(len(set(values[4:8])), 1)
        self.assertGreaterEqual(result["gross"]["average_profit"], 3)
        self.assertLess(result["after_energy"]["average_profit"], result["gross"]["average_profit"])

    def test_alternate_payout_uses_real_accounting_and_is_restored(self):
        with patch.object(parallel, "sample_round", return_value=(6, True)):
            result = stress_case(self.timing, 1, payout_cents=65)
        self.assertEqual(result["gross"]["average_profit"], 4.4)
        self.assertLess(result["expected_net_per_bet_before_energy"], 0)
        self.assertEqual(parallel.PAYOUT, 68)

    def test_all_red_drawdown_and_deadline_drain_keep_hard_limits(self):
        day = all_red_case(self.timing)
        self.assertEqual(day["pc_rounds"], [1250] * 4)
        self.assertEqual(day["profit"], -500)
        self.assertEqual(day["pc_final_cash"], [875] * 4)
        with patch.object(parallel, "sample_round", return_value=(1, False)):
            deadline = parallel.simulate_day("deadline-red", self.timing, laptop_count=4,
                                             deadline_seconds=2)
        self.assertEqual(deadline["pc_rounds"], [1] * 4)
        self.assertEqual(deadline["profit"], -.4)
        self.assertEqual(deadline["status"], "deadline")
        self.assertEqual(deadline["settlement_overrun_seconds"], 1)
        self.assertAlmostEqual(sum(deadline["pc_final_cash"]), 3999.6)


if __name__ == "__main__":
    unittest.main()
