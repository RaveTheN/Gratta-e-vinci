"""Seven-mine experiment uses the existing causal trigger, never a batch boundary."""

from fractions import Fraction
import itertools
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from analysis import seven_mine_trigger as experiment
from analysis import collective_parallel as parallel
from tests.test_medium_two_config import reference_session


TIMING = parallel.timing_from_settings({})
PLAN = {"laptop_count": 4, "picks": 2, "payout_cents": 18, "starting_cash_cents": [2000] * 4}


class SevenMineTriggerTest(unittest.TestCase):
    def test_seven_mine_thresholds_and_default_is_restored(self):
        original = parallel.SAFE_PREFIXES
        with patch.object(parallel, "SAFE_PREFIXES", experiment.SAFE_PREFIXES):
            for value, expected in ((0, (2, True)), (.509, (2, True)), (.51, (2, False)),
                                    (.719, (2, False)), (.72, (1, False))):
                with self.subTest(value=value):
                    rng = type("FixedDraw", (), {"random": lambda self: value})()
                    self.assertEqual(parallel.sample_round(rng, picks=2), expected)
        self.assertIs(parallel.SAFE_PREFIXES, original)
        self.assertEqual(parallel.SAFE_PREFIXES[1], .57)

    def test_trigger_stops_midway_through_a_fifty_game_lot_and_drains_open_bets(self):
        with patch.object(parallel, "sample_round", return_value=(2, True)):
            result = parallel.simulate_day("wins", TIMING, **PLAN)
        self.assertEqual(result["status"], "target")
        self.assertEqual(result["pc_rounds"], [10] * 4)
        self.assertEqual(result["target_stop_cash_floor"], 3.02)
        self.assertEqual(result["profit"], 3.20)
        self.assertEqual(result["pc_final_cash_cents"], [2080] * 4)

    def test_seven_mine_trigger_matches_independent_timer_scanning_reference(self):
        with patch.object(parallel, "SAFE_PREFIXES", experiment.SAFE_PREFIXES):
            for case in range(40):
                cash = [2000] * 4 if case % 2 else [0, 9, 10, 45]
                deadline = (2, 6, 100, 43200)[case % 4]
                target = (10, 30, 100, 300)[case % 4]
                expected = reference_session(case, TIMING, cash, target=target, deadline=deadline, cap=100)
                result = parallel.simulate_day(case, TIMING, laptop_count=4, starting_cash_cents=cash,
                                               target_cents=target, deadline_seconds=deadline,
                                               round_cap=100, picks=2, payout_cents=18)
                with self.subTest(case=case):
                    self.assertEqual(result["pc_final_cash_cents"], expected["cash"])
                    self.assertEqual(result["pc_minimum_cash_cents"], expected["lowest"])
                    self.assertEqual(result["pc_rounds"], expected["rounds"])
                    self.assertEqual(result["status"], expected["status"])
                    self.assertAlmostEqual(result["hours"] * 3600, expected["end"])

    def test_all_wins_carry_balances_and_reset_each_session_target(self):
        with patch.object(parallel, "sample_round", return_value=(2, True)):
            result = experiment.run_chunk((1, 123, 180, 7))
        row = result["monthly_rows"][0]
        self.assertEqual(result["simulation"]["mines"], 7)
        self.assertEqual(result["simulation"]["stop_policy"], "cash_reserved_trigger")
        self.assertIsNone(result["simulation"]["batch_size_per_laptop"])
        self.assertEqual(row["sessions_executed"], 60)
        self.assertEqual(row["gross_profit"], 192)
        self.assertEqual(row["final_cash_per_pc"], [68] * 4)

    def test_all_losses_exhaust_only_initial_capital_without_replenishment(self):
        with patch.object(parallel, "sample_round", return_value=(1, False)):
            result = experiment.run_chunk((1, 456, 180, 7))
        row = result["monthly_rows"][0]
        self.assertEqual(row["gross_profit"], -80)
        self.assertEqual(row["final_cash_per_pc"], [0] * 4)
        self.assertEqual(row["negative_days"], 1)
        self.assertEqual(row["zero_days"], 29)
        self.assertEqual(row["negative_sessions"], 1)
        self.assertEqual(row["non_target_sessions"][0]["pc_rounds"], [200] * 4)
        self.assertEqual(row["electricity_cost_example"], round(.240 * .30 * row["elapsed_hours"], 2))

    def test_184_millieuro_payment_and_fractional_cash_survive_the_full_month(self):
        starts = []
        simulate = parallel.simulate_day

        def capture(seed, timing, **kwargs):
            starts.append({**kwargs, "starting_cash_cents": list(kwargs["starting_cash_cents"])})
            return simulate(seed, timing, **kwargs)

        with patch.object(parallel, "sample_round", return_value=(2, True)), \
             patch.object(parallel, "simulate_day", side_effect=capture):
            result = experiment.run_chunk((1, 789, 184, 7))
        row = result["monthly_rows"][0]
        self.assertEqual(result["simulation"]["payout_on_win"], .184)
        self.assertEqual(result["simulation"]["multiplier"], 1.84)
        self.assertEqual(result["simulation"]["money_unit_eur"], .001)
        self.assertEqual(row["gross_profit"], 181.44)
        self.assertEqual(row["worst_session"], 3.024)
        self.assertEqual(row["final_cash_per_pc"], [65.36] * 4)
        self.assertEqual(starts[1]["starting_cash_cents"], [20756] * 4)
        self.assertEqual(starts[1]["target_cents"], 3000)
        self.assertEqual(starts[1]["drawdown_cents"], 500000)
        self.assertEqual(starts[1]["deadline_seconds"], 43200 - 62)
        self.assertEqual(parallel.STAKE, 10)

    def test_observed_does_not_round_fractional_losses_away(self):
        with patch.object(parallel, "sample_round", return_value=(2, True)):
            chunk = experiment.run_chunk((1, 321, 184, 7))
        row = chunk["monthly_rows"][0]
        row["minimum_daily_closing_total_cash"] = 79.998
        row["final_cash_per_pc"][0] = 19.998
        result = experiment.observed([chunk], units_per_eur=1000)
        self.assertEqual(result["days"]["months_with_a_day_closing_below_initial_group_capital"], 1)
        self.assertEqual(result["laptops"][0]["months_finishing_below_initial_capital"], 1)

    def test_five_mines_match_all_complete_boards(self):
        counts = [0, 0, 0]
        for board in itertools.combinations(range(25), 5):
            counts[0 if 0 in board else 1 if 1 in board else 2] += 1
        self.assertEqual(sum(counts), 53130)
        self.assertEqual([Fraction(count, sum(counts)) for count in counts],
                         [Fraction(1, 5), Fraction(1, 6), Fraction(19, 30)])

    def test_five_mines_use_changed_threshold_and_exact_154_millieuro_payment(self):
        # A draw of 0.6 wins with five mines and loses with seven, exercising the worker patch.
        with patch.object(parallel.random, "Random", side_effect=lambda seed: SimpleNamespace(random=lambda: .6)):
            chunk = experiment.run_chunk((1, 456, 154, 5))
        row = chunk["monthly_rows"][0]
        self.assertEqual(chunk["simulation"]["mines"], 5)
        self.assertEqual(chunk["simulation"]["payout_on_win"], .154)
        self.assertEqual(chunk["simulation"]["multiplier"], 1.54)
        self.assertEqual(row["gross_profit"], 181.44)
        self.assertEqual(row["worst_session"], 3.024)
        self.assertEqual(row["final_cash_per_pc"], [65.36] * 4)
        self.assertEqual(parallel.SAFE_PREFIXES[1], .57)
        self.assertEqual(parallel.STAKE, 10)

    def test_invalid_mine_counts_are_rejected_before_workers_start(self):
        for mines in (-1, 24, True, 5.0):
            with self.subTest(mines=mines), self.assertRaises(ValueError):
                experiment.run_research(months=1, workers=1, mines=mines)


if __name__ == "__main__":
    unittest.main()
