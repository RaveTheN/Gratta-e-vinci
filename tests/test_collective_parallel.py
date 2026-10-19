"""Check pending-bet accounting and deadline decisions without future outcomes."""

import math
import unittest
from unittest.mock import patch

from analysis.collective_parallel import simulate_day, ideal_day, summarize, timing_from_settings, sample_round, SURVIVAL


class CollectiveParallelTest(unittest.TestCase):
    def setUp(self):
        self.timing = timing_from_settings({})

    def scripted_streams(self):
        streams = {}
        counts = {}

        def sample(rng):
            if rng not in streams:
                streams[rng] = len(streams)
                counts[rng] = 0
            pc, index = streams[rng], counts[rng]
            counts[rng] += 1
            return (6, True) if pc == 0 else (1 if index == 0 else 6, False)
        return sample

    def test_raw_target_three_can_finish_below_three_but_protected_cannot(self):
        self.timing["between"] = 1.0
        with patch("analysis.collective_parallel.sample_round", side_effect=self.scripted_streams()):
            raw = simulate_day("scripted", self.timing, protected=False)
        with patch("analysis.collective_parallel.sample_round", side_effect=self.scripted_streams()):
            protected = simulate_day("scripted", self.timing, protected=True)
        self.assertEqual(raw["status"], "target")
        self.assertEqual(raw["profit"], 2.84)
        self.assertGreaterEqual(protected["target_stop_cash_floor"], 3)
        self.assertGreaterEqual(protected["profit"], 3)
        self.assertAlmostEqual(sum(protected["pc_final_cash"]) - 3000, protected["profit"])

    def test_deadline_starts_same_three_bets_regardless_of_future_outcomes(self):
        with patch("analysis.collective_parallel.sample_round", return_value=(6, True)):
            winners = simulate_day("deadline", self.timing, deadline_seconds=2)
        with patch("analysis.collective_parallel.sample_round", return_value=(1, False)):
            losers = simulate_day("deadline", self.timing, deadline_seconds=2)
        self.assertEqual(winners["pc_rounds"], [1, 1, 1])
        self.assertEqual(losers["pc_rounds"], [1, 1, 1])
        self.assertEqual(winners["settlement_overrun_seconds"], 12)
        self.assertEqual(losers["settlement_overrun_seconds"], 1)
        self.assertEqual(winners["status"], "deadline")
        self.assertEqual(losers["profit"], -.3)

    def test_pc_random_streams_are_distinct_and_not_cloned(self):
        streams = []
        values = []

        def capture(rng):
            streams.append(rng)
            values.append(rng.random())
            return 6, True
        with patch("analysis.collective_parallel.sample_round", side_effect=capture):
            result = simulate_day("independent", self.timing, round_cap=1)
        self.assertEqual(len(set(streams)), 3)
        self.assertEqual(len(set(values)), 3)
        self.assertEqual(result["pc_rounds"], [1, 1, 1])
        self.assertEqual(result["status"], "round_cap_or_funds")

    def test_four_laptops_account_for_all_funds_and_have_distinct_worlds(self):
        streams, draws = [], []

        def sample(rng):
            streams.append(rng)
            draws.append(rng.random())
            return 6, True
        with patch("analysis.collective_parallel.sample_round", side_effect=sample):
            day = simulate_day("four_worlds", self.timing, laptop_count=4, round_cap=1)
        self.assertEqual(len(set(streams)), 4)
        self.assertEqual(len(set(draws)), 4)
        self.assertEqual(day["pc_rounds"], [1] * 4)
        self.assertEqual(day["profit"], 2.32)
        self.assertAlmostEqual(sum(day["pc_final_cash"]), 4002.32)
        summary = summarize([day])
        self.assertEqual(summary["initial_total_bankroll"], 4000)
        self.assertEqual(len(summary["average_rounds_per_pc"]), 4)
        with patch("analysis.collective_parallel.sample_round", return_value=(6, True)):
            ideal = ideal_day("four_ideal", laptop_count=4, round_cap=1)
            deadline = simulate_day("four_deadline", self.timing, laptop_count=4, deadline_seconds=2)
        self.assertEqual(ideal["profit"], 2.32)
        self.assertEqual(deadline["pc_rounds"], [1] * 4)
        self.assertEqual(deadline["profit"], 2.32)
        self.assertEqual(deadline["status"], "deadline")

    def test_four_laptop_floor_lock_drawdown_bound_and_invalid_counts(self):
        with patch("analysis.collective_parallel.sample_round", return_value=(1, False)):
            day = simulate_day("four_drawdown", self.timing, laptop_count=4,
                               floor_lock=True, drawdown_cents=5000)
        self.assertEqual(day["status"], "drawdown")
        self.assertGreaterEqual(day["profit"], -50.40)
        self.assertFalse(day["capital_protected"])
        for count in (True, 0, -1, 2.5):
            with self.subTest(count=count), self.assertRaises(ValueError):
                simulate_day("invalid_count", self.timing, laptop_count=count)

    def test_starting_balances_carry_forward_without_resetting_daily_target(self):
        starting = [100000, 120000, 90000, 80000]
        original = list(starting)
        with patch("analysis.collective_parallel.sample_round", return_value=(6, True)):
            first = simulate_day("carry_day_one", self.timing, laptop_count=4,
                                 starting_cash_cents=starting)
            second = simulate_day("carry_day_two", self.timing, laptop_count=4,
                                  starting_cash_cents=first["pc_final_cash_cents"])
        self.assertEqual(starting, original)
        self.assertEqual(first["profit"], 4.64)
        self.assertEqual(second["profit"], 4.64)
        self.assertEqual(second["pc_rounds"], [2] * 4)
        self.assertEqual(second["pc_starting_cash"], first["pc_final_cash"])
        self.assertEqual(second["pc_profits"], [1.16] * 4)
        self.assertEqual(sum(second["pc_final_cash_cents"]) - sum(starting), 928)

    def test_empty_balances_stop_immediately_and_invalid_starting_cash_is_rejected(self):
        with patch("analysis.collective_parallel.sample_round") as sample:
            day = simulate_day("empty_bank", self.timing, laptop_count=4,
                               starting_cash_cents=[0] * 4)
        sample.assert_not_called()
        self.assertEqual(day["status"], "insufficient_funds")
        self.assertEqual(day["hours"], 0)
        self.assertEqual(day["pc_unfunded_at_close"], [True] * 4)
        for balances in ([100000] * 3, [-1] * 4, [True] * 4, [100000.0] * 4):
            with self.subTest(balances=balances), self.assertRaises(ValueError):
                simulate_day("invalid_cash", self.timing, laptop_count=4, starting_cash_cents=balances)

    def test_small_medium_two_balances_never_borrow_from_other_pcs(self):
        for won, starting, expected_cash, expected_rounds in (
                (False, [0, 9, 10, 25], [0, 9, 0, 5], [0, 0, 1, 2]),
                (True, [0, 9, 10, 20], [0, 9, 18, 28], [0, 0, 1, 1])):
            with self.subTest(won=won), patch("analysis.collective_parallel.sample_round", return_value=(2, won)):
                day = simulate_day("small_balances", self.timing, laptop_count=4,
                                   starting_cash_cents=starting, picks=2, payout_cents=18,
                                   round_cap=1 if won else 4000)
            self.assertEqual(day["pc_final_cash_cents"], expected_cash)
            self.assertEqual(day["pc_rounds"], expected_rounds)
            self.assertEqual(day["pc_unfunded_at_close"][:2], [True, True])
            self.assertGreaterEqual(min(day["pc_minimum_cash_cents"]), 0)
            self.assertEqual(sum(expected_cash) - sum(starting), round(day["profit"] * 100))

    def test_medium_two_target_reserves_pending_stakes_at_small_balances(self):
        timing = {**self.timing, "reveal": 0, "after_loss": 0}

        def scripted():
            streams, counts = {}, {}

            def sample(rng, picks):
                self.assertEqual(picks, 2)
                if rng not in streams:
                    streams[rng], counts[rng] = len(streams), 0
                pc, index = streams[rng], counts[rng]
                counts[rng] += 1
                return 2, pc != 0 or index < 9
            return sample

        rows = []
        for protected in (False, True):
            with patch("analysis.collective_parallel.sample_round", side_effect=scripted()):
                rows.append(simulate_day("pending_two", timing, protected=protected,
                                         laptop_count=4, starting_cash_cents=[10] * 4,
                                         picks=2, payout_cents=18))
        raw, protected = rows
        self.assertEqual(raw["status"], "target")
        self.assertEqual(raw["profit"], 2.92)
        self.assertEqual(protected["status"], "target")
        self.assertGreaterEqual(protected["target_stop_cash_floor"], 3)
        self.assertGreaterEqual(protected["profit"], 3)
        for row in rows:
            self.assertEqual(sum(row["pc_final_cash_cents"]) - 40, round(row["profit"] * 100))
            self.assertGreaterEqual(min(row["pc_minimum_cash_cents"]), 0)

    def test_medium_two_small_balances_obey_caps_and_drain_deadline_rounds(self):
        for won in (False, True):
            with self.subTest(won=won), patch("analysis.collective_parallel.sample_round", return_value=(2, won)):
                capped = simulate_day("small_cap", self.timing, laptop_count=4,
                                      starting_cash_cents=[10] * 4, picks=2, payout_cents=18, round_cap=1)
                deadline = simulate_day("small_deadline", self.timing, laptop_count=4,
                                        starting_cash_cents=[10] * 4, picks=2, payout_cents=18,
                                        deadline_seconds=2)
            for row in (capped, deadline):
                self.assertEqual(row["pc_rounds"], [1] * 4)
                self.assertEqual(row["pc_final_cash_cents"], [18 if won else 0] * 4)
                self.assertEqual(row["pc_minimum_cash_cents"], [0] * 4)
                self.assertEqual(sum(row["pc_final_cash_cents"]) - 40, round(row["profit"] * 100))
            self.assertEqual(deadline["status"], "deadline")
            self.assertEqual(deadline["stop_hours"] * 3600, 2)
            self.assertEqual(deadline["settlement_overrun_seconds"], 4 if won else 3)

    def test_medium_two_thirty_day_small_balances_carry_without_topups(self):
        for won in (False, True):
            bank, profit_cents, total_rounds = [10] * 4, 0, 0
            with self.subTest(won=won), patch("analysis.collective_parallel.sample_round", return_value=(2, won)):
                for day_index in range(30):
                    before = list(bank)
                    day = simulate_day(f"small_month:{day_index}", self.timing, laptop_count=4,
                                       starting_cash_cents=bank, picks=2, payout_cents=18)
                    bank = day["pc_final_cash_cents"]
                    self.assertEqual(day["pc_starting_cash"], [value / 100 for value in before])
                    self.assertEqual(sum(bank) - sum(before), round(day["profit"] * 100))
                    self.assertGreaterEqual(min(day["pc_minimum_cash_cents"]), 0)
                    profit_cents += round(day["profit"] * 100)
                    total_rounds += sum(day["pc_rounds"])
            self.assertEqual(bank, [2410 if won else 0] * 4)
            self.assertEqual(total_rounds, 1200 if won else 4)
            self.assertEqual(sum(bank) - 40, profit_cents)

    def test_first_mine_sampler_matches_safe_prefix_boundaries(self):
        class Draw:
            def __init__(self, value):
                self.value = value
            def random(self):
                return self.value
        self.assertEqual(sample_round(Draw(SURVIVAL[0])), (1, False))
        self.assertEqual(sample_round(Draw(SURVIVAL[5])), (6, False))
        self.assertEqual(sample_round(Draw(0)), (6, True))

    def test_requested_picks_use_their_safe_prefix_and_collect_duration(self):
        class Draw:
            def __init__(self, value):
                self.value = value
            def random(self):
                return self.value

        for picks, payout, expected in ((2, 18, .32), (7, 100, 3.60), (8, 150, 5.60)):
            with self.subTest(picks=picks):
                probability = math.comb(19, picks) / math.comb(25, picks)
                self.assertEqual(sample_round(Draw(probability), picks), (picks, False))
                self.assertEqual(sample_round(Draw(0), picks), (picks, True))
                with patch("analysis.collective_parallel.sample_round", return_value=(picks, True)) as sample:
                    day = simulate_day("requested_picks", self.timing, laptop_count=4,
                                       picks=picks, payout_cents=payout,
                                       target_cents=20 if picks == 2 else 300)
                self.assertEqual(day["profit"], expected)
                self.assertEqual(day["pc_rounds"], [1] * 4)
                self.assertEqual(day["hours"] * 3600, 2 + 2 * picks)
                self.assertEqual(day["status"], "target")
                self.assertTrue(all(call.args[1] == picks for call in sample.call_args_list))
        for picks in (True, 0, 9, 2.5):
            with self.subTest(picks=picks), self.assertRaises(ValueError):
                simulate_day("invalid_picks", self.timing, picks=picks)
            with self.subTest(picks=picks), self.assertRaises(ValueError):
                sample_round(Draw(0), picks)
        for payout in (True, 0, -1, 18.0):
            with self.subTest(payout=payout), self.assertRaises(ValueError):
                simulate_day("invalid_payout", self.timing, payout_cents=payout)
        with patch("analysis.collective_parallel.sample_round", return_value=(8, True)):
            adverse = simulate_day("payment_below_stake", self.timing, laptop_count=4,
                                   picks=8, payout_cents=5, round_cap=1)
        self.assertEqual(adverse["profit"], -.20)
        self.assertEqual(adverse["status"], "round_cap_or_funds")

    def test_eight_pick_carryover_keeps_the_next_daily_target_relative_to_start(self):
        with patch("analysis.collective_parallel.sample_round", return_value=(8, True)):
            first = simulate_day("eight_day_one", self.timing, laptop_count=4,
                                 picks=8, payout_cents=150)
            second = simulate_day("eight_day_two", self.timing, laptop_count=4,
                                  picks=8, payout_cents=150,
                                  starting_cash_cents=first["pc_final_cash_cents"])
        self.assertEqual(first["profit"], 5.60)
        self.assertEqual(second["profit"], 5.60)
        self.assertEqual(second["pc_rounds"], [1] * 4)
        self.assertEqual(second["pc_starting_cash"], first["pc_final_cash"])
        self.assertEqual(second["pc_final_cash_cents"], [100280] * 4)

    def test_initial_losses_do_not_lock_negative_capital(self):
        with patch("analysis.collective_parallel.sample_round", return_value=(1, False)):
            day = simulate_day("initial_losses", self.timing, floor_lock=True, deadline_seconds=9)
        self.assertFalse(day["capital_protected"])
        self.assertIsNone(day["first_lock_cash_floor"])
        self.assertLess(day["profit"], 0)

    def test_drawdown_stops_initial_losses_and_drains_within_conservative_bound(self):
        with patch("analysis.collective_parallel.sample_round", return_value=(1, False)):
            day = simulate_day("initial_drawdown", self.timing, floor_lock=True, drawdown_cents=5000)
        self.assertFalse(day["capital_protected"])
        self.assertEqual(day["status"], "drawdown")
        self.assertGreaterEqual(day["profit"], -50.30)
        self.assertLessEqual(day["profit"], -50)

    def test_after_lock_many_losses_never_consume_global_principal(self):
        streams = {}
        counts = {}

        def sample(rng):
            if rng not in streams:
                streams[rng] = len(streams)
                counts[rng] = 0
            pc, index = streams[rng], counts[rng]
            counts[rng] += 1
            return (6, True) if pc == 0 and index < 5 else (6, False)
        with patch("analysis.collective_parallel.sample_round", side_effect=sample):
            day = simulate_day("lock_losses", self.timing, floor_lock=True, target_cents=10000)
        self.assertTrue(day["capital_protected"])
        self.assertEqual(day["status"], "protected_floor")
        self.assertEqual(day["profit"], 0)
        self.assertEqual(day["minimum_cash_floor_after_lock"], 0)
        self.assertAlmostEqual(sum(day["pc_final_cash"]), 3000)

    def test_waiting_for_an_actual_pending_win_resumes_and_target_is_safe(self):
        self.timing["between"] = 1.0
        with patch("analysis.collective_parallel.sample_round", side_effect=self.scripted_streams()):
            day = simulate_day("lock_wait", self.timing, floor_lock=True)
        self.assertTrue(day["capital_protected"])
        self.assertGreaterEqual(day["floor_waits"], 2)
        self.assertGreaterEqual(day["floor_resumptions"], 2)
        self.assertEqual(day["status"], "target")
        self.assertGreaterEqual(day["minimum_cash_floor_after_lock"], 0)
        self.assertGreaterEqual(day["target_stop_cash_floor"], 3)
        self.assertGreaterEqual(day["profit"], 3)


if __name__ == "__main__":
    unittest.main()
