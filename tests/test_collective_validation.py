"""Validate whole-month bankroll conservation and the illustrative power bill."""

import unittest
from unittest.mock import patch

from analysis.collective_validation import distribution, run_validation
from analysis.medium_bankroll import combine


class CollectiveValidationTest(unittest.TestCase):
    def test_month_carries_bankroll_and_monthly_replicas_remain_independent(self):
        timing = {"play": 1800.0, "tile": .001, "reveal": 1.0,
                  "between": 0.0, "after_loss": 1.0}
        with patch("analysis.collective_validation.timing_from_settings", return_value=timing), \
             patch("analysis.collective_parallel.sample_round", return_value=(6, True)):
            report = run_validation(months=2, days_per_month=2)
        self.assertEqual(report["summary"]["daily_count"], 4)
        for month in report["monthly_rows"]:
            self.assertEqual(month["gross_profit"], 9.28)
            self.assertEqual(month["final_cash_per_pc"], [1002.32] * 4)
            self.assertEqual(month["electricity_cost_example"], .29)
            self.assertEqual(month["net_profit_after_example_electricity"], 8.99)
            self.assertEqual(month["days_with_insufficient_pc_funds"], 0)
        self.assertEqual(report["summary"]["monthly_net_after_example_electricity"]["mean"], 8.99)
        self.assertEqual(report["summary"]["negative_net_months"], 0)

    def test_percentiles_and_invalid_replica_counts(self):
        self.assertEqual(distribution([1, 3])["p50"], 2)
        self.assertEqual(distribution([5])["p1"], 5)
        for args in ({"months": True}, {"months": 0}, {"days_per_month": 0}, {"days_per_month": 1.5}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                run_validation(**args)

    def test_eight_pick_month_reports_requested_payment_and_preserves_cent_balances(self):
        with patch("analysis.collective_parallel.sample_round", return_value=(8, True)):
            report = run_validation(months=2, days_per_month=2, picks=8, payout_cents=150)
        self.assertEqual(report["simulation"]["picks"], 8)
        self.assertEqual(report["simulation"]["payout_on_win"], 1.5)
        self.assertEqual(report["simulation"]["multiplier"], 15)
        for month in report["monthly_rows"]:
            self.assertEqual(month["gross_profit"], 11.20)
            self.assertEqual(month["final_cash_per_pc"], [1002.80] * 4)
        for args in ({"picks": 9}, {"picks": True}, {"payout_cents": 0}, {"payout_cents": 18.0}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                run_validation(months=1, days_per_month=1, **args)

    def test_initial_capital_is_carried_and_any_unfunded_pc_marks_an_interrupted_month(self):
        with patch("analysis.collective_parallel.sample_round", return_value=(2, True)):
            winning = run_validation(months=1, days_per_month=2, picks=2,
                                     payout_cents=18, initial_bankroll_cents=100)
        self.assertEqual(winning["simulation"]["initial_bankroll_per_laptop"], 1)
        self.assertEqual(winning["monthly_rows"][0]["gross_profit"], 6.40)
        self.assertEqual(winning["monthly_rows"][0]["final_cash_per_pc"], [2.60] * 4)
        self.assertEqual(winning["monthly_rows"][0]["minimum_daily_closing_cash_per_pc"], [1] * 4)
        with patch("analysis.collective_parallel.sample_round", return_value=(1, False)):
            exhausted = run_validation(months=1, days_per_month=2, picks=2,
                                       payout_cents=18, initial_bankroll_cents=10)
        self.assertEqual(exhausted["summary"]["months_with_insufficient_pc_funds"], 1)
        self.assertEqual(exhausted["summary"]["days_with_insufficient_pc_funds"], 2)
        self.assertEqual(exhausted["monthly_rows"][0]["final_cash_per_pc"], [0] * 4)
        self.assertEqual(exhausted["monthly_rows"][0]["gross_profit"], -.40)
        for capital in (True, -1, 100.0):
            with self.subTest(capital=capital), self.assertRaises(ValueError):
                run_validation(months=1, initial_bankroll_cents=capital)

    def test_two_sessions_carry_cash_and_reset_each_target_without_resetting_the_day(self):
        with patch("analysis.collective_parallel.sample_round", return_value=(2, True)):
            report = run_validation(months=1, days_per_month=2, picks=2, payout_cents=18,
                                    initial_bankroll_cents=2000, sessions_per_day=2)
        row, summary = report["monthly_rows"][0], report["summary"]
        self.assertEqual(row["gross_profit"], 12.80)
        self.assertEqual(row["final_cash_per_pc"], [23.20] * 4)
        self.assertEqual(summary["session_count"], 4)
        self.assertEqual(summary["daily_count"], 2)
        self.assertEqual(summary["mean_daily_gross_profit"], 6.40)
        self.assertEqual(report["simulation"]["daily_round_cap_per_pc"], 8000)
        self.assertEqual(report["simulation"]["global_session_target"], 3)
        self.assertIsNone(report["simulation"]["global_daily_drawdown_limit"])

    @staticmethod
    def fake_session(kwargs, profit_cents, elapsed_seconds, status):
        starting = kwargs["starting_cash_cents"]
        bank = list(starting)
        bank[0] += profit_cents
        return {"pc_final_cash_cents": bank, "profit": profit_cents / 100,
                "hours": elapsed_seconds / 3600, "status": status,
                "pc_rounds": [1] * 4, "pc_minimum_cash_cents": [value - 10 for value in starting],
                "pc_unfunded_at_close": [value < 10 for value in bank]}

    def test_second_session_uses_only_remaining_time_and_runs_after_a_loss(self):
        calls = []

        def simulate(seed, timing, **kwargs):
            calls.append((seed, kwargs))
            if len(calls) == 1:
                return self.fake_session(kwargs, -100, 40000, "round_cap_or_funds")
            return self.fake_session(kwargs, 300, 3210, "deadline")

        with patch("analysis.collective_validation.simulate_day", side_effect=simulate):
            report = run_validation(months=1, days_per_month=1, picks=2, payout_cents=18,
                                    initial_bankroll_cents=2000, sessions_per_day=2)
        self.assertEqual(calls[0][1]["deadline_seconds"], 43200)
        self.assertEqual(calls[1][1]["deadline_seconds"], 3200)
        self.assertEqual(calls[1][1]["starting_cash_cents"], [1900, 2000, 2000, 2000])
        self.assertEqual([call[1]["target_cents"] for call in calls], [300, 300])
        self.assertEqual([call[1]["round_cap"] for call in calls], [4000, 4000])
        self.assertNotEqual(calls[0][0], calls[1][0])
        self.assertEqual(report["summary"]["negative_sessions"], 1)
        self.assertEqual(report["summary"]["negative_days"], 0)
        self.assertEqual(report["summary"]["maximum_settlement_overrun_seconds"], 10)
        self.assertEqual(report["monthly_rows"][0]["gross_profit"], 2)

    def test_first_session_drain_exhausts_shared_time_and_skips_the_second(self):
        def simulate(seed, timing, **kwargs):
            return self.fake_session(kwargs, 300, 43205, "target")

        with patch("analysis.collective_validation.simulate_day", side_effect=simulate) as run:
            report = run_validation(months=1, days_per_month=1, sessions_per_day=2)
        self.assertEqual(run.call_count, 1)
        self.assertEqual(report["summary"]["session_count"], 1)
        self.assertEqual(report["summary"]["sessions_skipped_daily_time_budget"], 1)
        self.assertEqual(report["summary"]["negative_sessions"], 0)
        self.assertEqual(report["summary"]["maximum_settlement_overrun_seconds"], 5)
        self.assertEqual(report["summary"]["daily_status_counts"], {"deadline": 1})
        for count in (True, 0, 3, 2.0):
            with self.subTest(count=count), self.assertRaises(ValueError):
                run_validation(months=1, sessions_per_day=count)

    def test_one_laptop_requires_38_wins_per_target_and_uses_only_its_own_cash(self):
        with patch("analysis.collective_parallel.sample_round", return_value=(2, True)):
            report = run_validation(months=1, days_per_month=1, picks=2, payout_cents=18,
                                    initial_bankroll_cents=2000, sessions_per_day=2,
                                    laptop_count=1, total_power_watts=50)
        row = report["monthly_rows"][0]
        self.assertEqual(row["gross_profit"], 6.08)
        self.assertEqual(row["final_cash_per_pc"], [26.08])
        self.assertEqual(report["summary"]["mean_daily_rounds_all_laptops"], 76)
        self.assertEqual(report["summary"]["session_status_counts"], {"target": 2})
        self.assertFalse(report["simulation"]["separate_master_pc"])
        self.assertEqual(report["electricity_example"]["total_power_watts"], 50)
        self.assertEqual(report["electricity_example"]["powered_computer_count"], 1)
        self.assertNotIn("total_power_watts_all_five_pcs", report["electricity_example"])
        self.assertEqual(row["electricity_cost_example"], round(.050 * .30 * row["elapsed_hours"], 2))
        merged = combine([report])
        self.assertEqual(len(merged["minimum_cash_per_pc_including_open_stakes"]), 1)
        self.assertEqual(len(merged["months_finishing_below_initial_per_pc"]), 1)
        self.assertEqual(merged["mean_daily_minutes"], row["elapsed_hours"] * 60)
        with patch("analysis.collective_parallel.sample_round", return_value=(1, False)):
            exhausted = run_validation(months=1, days_per_month=1, picks=2, payout_cents=18,
                                       initial_bankroll_cents=20, laptop_count=1, total_power_watts=50)
        self.assertEqual(exhausted["monthly_rows"][0]["gross_profit"], -.20)
        self.assertEqual(exhausted["monthly_rows"][0]["final_cash_per_pc"], [0])
        self.assertEqual(exhausted["summary"]["months_with_insufficient_pc_funds"], 1)
        for count in (True, 0, -1, 1.5):
            with self.subTest(count=count), self.assertRaises(ValueError):
                run_validation(months=1, laptop_count=count)
        for power in (True, 0, -1, float("nan"), float("inf"), "50"):
            with self.subTest(power=power), self.assertRaises(ValueError):
                run_validation(months=1, total_power_watts=power)


if __name__ == "__main__":
    unittest.main()
