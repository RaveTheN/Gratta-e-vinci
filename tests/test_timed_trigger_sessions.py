"""Repeated sessions respect a shared deadline and carry individual balances."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import unittest
from unittest.mock import patch

from analysis import collective_parallel as parallel
from analysis import timed_trigger_sessions as experiment


TIMING = parallel.timing_from_settings({})


class TimedTriggerSessionsTest(unittest.TestCase):
    def test_all_wins_repeat_more_than_two_sessions_and_drain_at_deadline(self):
        starts = []
        simulate = parallel.simulate_day

        def capture(seed, timing, **kwargs):
            starts.append({**kwargs, "starting_cash_cents": list(kwargs["starting_cash_cents"])})
            return simulate(seed, timing, **kwargs)

        with patch.object(parallel, "sample_round", return_value=(2, True)), \
             patch.object(parallel, "simulate_day", side_effect=capture):
            rows = experiment.run_chunk((1, 123, 199 / 3600, 2, TIMING))
        row = rows[0]
        # Each full all-win session takes 69 seconds; the last session receives 61 seconds.
        self.assertEqual(row["sessions_with_bets"], 6)
        self.assertEqual(row["target_sessions"], 4)
        self.assertEqual(row["session_status_counts"], {"target": 4, "deadline": 2})
        self.assertEqual(row["gross_profit"], 18.56)
        self.assertEqual(row["final_cash_per_pc"], [24.64] * 4)
        self.assertEqual(row["active_days"], 2)
        self.assertEqual(row["idle_days_after_funds_exhausted"], 0)
        self.assertEqual(row["settlement_overrun_days"], 2)
        self.assertAlmostEqual(row["maximum_daily_hours"] * 3600, 200)
        self.assertEqual(starts[1]["starting_cash_cents"], [2080] * 4)
        self.assertAlmostEqual(starts[1]["deadline_seconds"], 130)
        self.assertAlmostEqual(starts[2]["deadline_seconds"], 61)
        self.assertEqual(starts[3]["starting_cash_cents"], [2232] * 4)
        self.assertEqual(row["electricity_cost_example"], round(.240 * .30 * row["elapsed_hours"], 2))

    def test_all_losses_stop_once_then_count_idle_days_separately(self):
        with patch.object(parallel, "sample_round", return_value=(1, False)):
            row = experiment.run_chunk((1, 456, 4, 30, TIMING))[0]
        self.assertEqual(row["gross_profit"], -80)
        self.assertEqual(row["final_cash_per_pc"], [0] * 4)
        self.assertEqual(row["sessions_with_bets"], 1)
        self.assertEqual(row["negative_sessions"], 1)
        self.assertEqual(row["session_attempts_without_bets"], 0)
        self.assertEqual(row["active_days"], 1)
        self.assertEqual(row["idle_days_after_funds_exhausted"], 29)
        self.assertEqual(row["negative_days"], 1)
        self.assertEqual(row["last_active_day"], 1)
        self.assertEqual(row["first_all_unfunded_day"], 1)
        self.assertEqual(row["pc_rounds"], [200] * 4)

    def test_tiny_deadline_still_drains_previously_started_games(self):
        with patch.object(parallel, "sample_round", return_value=(2, True)):
            row = experiment.run_chunk((1, 999, 1 / 3600, 1, TIMING))[0]
        self.assertEqual(row["sessions_with_bets"], 1)
        self.assertEqual(row["pc_rounds"], [1] * 4)
        self.assertEqual(row["gross_profit"], .32)
        self.assertAlmostEqual(row["elapsed_hours"] * 3600, 6)
        self.assertAlmostEqual(row["maximum_settlement_overrun_seconds"], 5)

    def test_round_cap_resets_each_session_without_a_daily_round_cap(self):
        starts = []
        simulate = parallel.simulate_day

        def capped(seed, timing, **kwargs):
            starts.append(kwargs["round_cap"])
            return simulate(seed, timing, **{**kwargs, "round_cap": 1})

        with patch.object(parallel, "sample_round", return_value=(2, True)), \
             patch.object(parallel, "simulate_day", side_effect=capped):
            row = experiment.run_chunk((1, 123, 20 / 3600, 1, TIMING))[0]
        self.assertEqual(starts, [4000] * 4)
        self.assertEqual(row["pc_rounds"], [4] * 4)
        self.assertEqual(row["target_sessions"], 0)
        self.assertEqual(row["gross_profit"], 1.28)

    def test_research_reads_timing_without_writing_personal_settings(self):
        settings_path = parallel.ROOT / "gratta_settings.json"
        before = hashlib.sha256(settings_path.read_bytes()).digest()
        with patch.object(parallel, "sample_round", return_value=(2, True)), \
             patch.object(experiment, "ProcessPoolExecutor", ThreadPoolExecutor):
            report = experiment.run_research(months=1, workers=1, hours=1 / 3600, days=1)
        self.assertEqual(before, hashlib.sha256(settings_path.read_bytes()).digest())
        self.assertEqual(parallel.STAKE, 10)
        self.assertEqual(parallel.SAFE_PREFIXES[1], .57)
        plan = report["simulation"]
        self.assertEqual((plan["mines"], plan["picks"], plan["payout_on_win"], plan["stake"]), (6, 2, .18, .1))
        self.assertIsNone(plan["daily_round_cap_per_pc"])
        self.assertIsNone(plan["global_daily_target"])
        self.assertEqual(plan["round_cap_per_session_per_pc"], 4000)
        self.assertEqual(report["theoretical_calculations"]["expected_profit_per_game_eur"], .0026)
        self.assertEqual(report["theoretical_calculations"]["return_to_player_percent"], 102.6)
        self.assertEqual(report["timing_seconds"], parallel.timing_from_settings(
            experiment.json.loads(settings_path.read_text(encoding="utf-8"))))
        self.assertEqual(report["independent_seed_chunks"][0]["months"], 1)
        self.assertIsNone(report["observed_simulation"]["monthly_gross"]["standard_error_of_mean"])

    def test_distribution_has_sample_uncertainty_and_activity_counts(self):
        with patch.object(parallel, "sample_round", return_value=(2, True)):
            rows = experiment.run_chunk((2, 123, 1 / 3600, 1, TIMING))
        summary = experiment.summarize(rows, 1)
        self.assertEqual(summary["monthly_gross"]["count"], 2)
        self.assertEqual(summary["monthly_gross"]["standard_error_of_mean"], 0)
        self.assertEqual(summary["monthly_gross"]["approximate_95_percent_confidence_interval_of_mean"], [.32, .32])
        self.assertEqual(summary["sessions_with_bets"], 2)
        self.assertEqual(summary["mean_sessions_per_calendar_day"], 1)

    def test_invalid_counts_rejected_before_workers_start(self):
        for kwargs in ({"months": 0}, {"months": True}, {"days": 0}, {"hours": 0},
                       {"hours": float("nan")}, {"hours": True}, {"workers": 0}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                experiment.run_research(**kwargs)


if __name__ == "__main__":
    unittest.main()
