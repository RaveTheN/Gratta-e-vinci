"""Check twenty-cent stakes, funding, configurable group targets and report thresholds."""

import unittest
from unittest.mock import patch

from analysis import collective_parallel as parallel
from analysis import medium_twenty_cents as twenty
from analysis.collective_validation import run_validation
from analysis.medium_two_verification import observed


class TwentyCentsTest(unittest.TestCase):
    def test_worker_pins_twenty_cent_stakes_and_restores_the_default(self):
        original = parallel.STAKE

        def inspect(**kwargs):
            self.assertEqual(parallel.STAKE, 20)
            self.assertEqual(kwargs, dict(months=7, days_per_month=30, picks=2, payout_cents=36,
                                         initial_bankroll_cents=4000, sessions_per_day=2,
                                         laptop_count=4, total_power_watts=240, target_cents=600))
            return "report"

        with patch.object(twenty.validation, "run_validation", side_effect=inspect):
            self.assertEqual(twenty.run_chunk((7, 12345, 4000, 600)), "report")
        self.assertEqual(parallel.STAKE, original)

    def test_each_round_debits_twenty_and_returns_thirty_six_only_on_a_win(self):
        timing = parallel.timing_from_settings({})
        for won, final in ((True, [0, 19, 36, 2016]), (False, [0, 19, 0, 1980])):
            with self.subTest(won=won), patch.object(parallel, "STAKE", 20), \
                 patch.object(parallel, "sample_round", return_value=(2, won)) as sample:
                result = parallel.simulate_day("twenty", timing, laptop_count=4,
                                               starting_cash_cents=[0, 19, 20, 2000],
                                               picks=2, payout_cents=36, round_cap=1)
            self.assertEqual(sample.call_count, 2)
            self.assertEqual(result["pc_rounds"], [0, 0, 1, 1])
            self.assertEqual(result["pc_minimum_cash_cents"], [0, 19, 0, 1980])
            self.assertEqual(result["pc_final_cash_cents"], final)
            self.assertEqual(round(result["profit"] * 100), sum(final) - 2039)

    def test_month_keeps_twenty_euro_capital_and_three_euro_group_target(self):
        with patch.object(parallel, "STAKE", 20), \
             patch.object(parallel, "sample_round", return_value=(2, True)):
            result = run_validation(months=1, days_per_month=1, picks=2, payout_cents=36,
                                    initial_bankroll_cents=2000, sessions_per_day=2, laptop_count=4)
        self.assertEqual(result["simulation"]["stake"], .2)
        self.assertEqual(result["simulation"]["multiplier"], 1.8)
        self.assertEqual(result["simulation"]["global_session_target"], 3)
        self.assertEqual(result["monthly_rows"][0]["final_cash_per_pc"], [21.6] * 4)
        self.assertEqual(result["monthly_rows"][0]["gross_profit"], 6.4)

    def test_forty_euro_capital_and_two_six_euro_targets_share_cash_and_time(self):
        calls = []

        def record(seed, timing, **kwargs):
            calls.append(kwargs)
            return parallel.simulate_day(seed, timing, **kwargs)

        timing = dict(play=1000.0, tile=0.0, reveal=0.0, after_loss=0.0, between=0.0)
        with patch.object(parallel, "STAKE", 20), \
             patch.object(parallel, "sample_round", return_value=(2, True)), \
             patch.object(twenty.validation, "timing_from_settings", return_value=timing), \
             patch.object(twenty.validation, "simulate_day", side_effect=record):
            report = run_validation(months=1, days_per_month=1, picks=2, payout_cents=36,
                                    initial_bankroll_cents=4000, sessions_per_day=2,
                                    laptop_count=4, target_cents=600)
        self.assertEqual([call["target_cents"] for call in calls], [600, 600])
        self.assertEqual([call["deadline_seconds"] for call in calls], [43200, 23200])
        self.assertEqual(calls[1]["starting_cash_cents"], [4160] * 4)
        self.assertEqual(report["simulation"]["global_daily_target"], 12)
        self.assertEqual(report["monthly_rows"][0]["final_cash_per_pc"], [43.2] * 4)
        self.assertEqual(report["monthly_rows"][0]["gross_profit"], 12.8)

    def test_losing_sessions_use_forty_and_160_euro_report_thresholds(self):
        counts = {}

        def sample(rng, picks):
            self.assertEqual(picks, 2)
            index = counts.get(rng, 0)
            counts[rng] = index + 1
            return (1, False) if index % 9 < 4 else (2, True)

        with patch.object(parallel, "STAKE", 20), \
             patch.object(parallel, "sample_round", side_effect=sample), \
             patch.object(twenty.validation, "timing_from_settings", return_value=parallel.timing_from_settings({})):
            report = run_validation(months=1, days_per_month=1, picks=2, payout_cents=36,
                                    initial_bankroll_cents=4000, sessions_per_day=2,
                                    laptop_count=4, target_cents=600)
        row = report["monthly_rows"][0]
        self.assertEqual(row["gross_profit"], -4.8)
        self.assertEqual(row["final_cash_per_pc"], [38.8] * 4)
        result = observed([report])
        self.assertEqual(result["days"]["months_with_a_day_closing_below_initial_group_capital"], 1)
        self.assertEqual([pc["months_finishing_below_initial_capital"] for pc in result["laptops"]], [1] * 4)
        self.assertEqual(result["sessions"]["not_reaching_session_target"], 2)

    def test_session_target_rejects_nonpositive_or_noninteger_cents(self):
        for target in (0, -1, True, 600.0):
            with self.subTest(target=target), self.assertRaises(ValueError):
                run_validation(months=1, days_per_month=1, target_cents=target)


if __name__ == "__main__":
    unittest.main()
