"""Independent checks of the 4-laptop plan: medium, 2 cells, 0.18 EUR total win, two +3 EUR sessions."""

from fractions import Fraction
import itertools
import json
import math
import random
import unittest
from unittest.mock import patch

from analysis import medium_two_sessions
from analysis.collective_parallel import ROOT, SAFE_PREFIXES, STAKE, sample_round, simulate_day, timing_from_settings
from analysis.collective_validation import run_validation
from analysis.medium_two_verification import (EXACT, compare_generators, exact_board_outcomes,
                                              full_board_round, reach_upper_bound, session_cap_theory)


TIMING = timing_from_settings(json.loads((ROOT / "gratta_settings.json").read_text(encoding="utf-8")))
FIXED_TIMING = {"play": 1.0, "tile": 2.0, "after_loss": 1.0, "reveal": 1.0, "between": 0.0}
PLAN = {"laptop_count": 4, "picks": 2, "payout_cents": 18}
WIN, LOSE_FIRST, LOSE_SECOND = (2, True), (1, False), (2, False)


def scripted(*patterns):
    """Cycle one outcome pattern per laptop; each new random stream (next session) restarts it."""
    streams = {}

    def sample(rng, picks=6):
        if picks != 2:
            raise AssertionError("the plan must open two cells")
        state = streams.setdefault(rng, [len(streams) % len(patterns), 0])
        pattern = patterns[state[0]]
        state[1] += 1
        return pattern[(state[1] - 1) % len(pattern)]
    return sample


def reference_session(seed, timing, cash, target=300, deadline=43200.0, cap=4000, picks=2, payout=18):
    """Second implementation of the session rules: scan every timer instead of using a heap."""
    count = len(cash)
    rngs = [random.Random(f"{seed}:laptop:{pc}") for pc in range(count)]
    cash, initial = list(cash), sum(cash)
    rounds, lowest = [0] * count, list(cash)
    next_start, open_game = [0.0] * count, [None] * count
    status = stopped_at = None
    now = 0.0

    def blocked():
        return (all(rounds[p] >= cap or cash[p] < STAKE for p in range(count))
                and all(game is None for game in open_game))

    while True:
        timers = [(game[0], 1, pc) for pc, game in enumerate(open_game) if game]
        if status is None:
            timers += [(deadline, 0, -1)] + [(at, 2, pc) for pc, at in enumerate(next_start) if at is not None]
        if not timers:
            break
        now, kind, pc = min(timers)
        if kind == 0:
            status, stopped_at = "deadline", now
        elif kind == 2:
            next_start[pc] = None
            if rounds[pc] >= cap:
                continue
            if cash[pc] < STAKE:
                if blocked():
                    status, stopped_at = "insufficient_funds", now
                continue
            cash[pc] -= STAKE
            lowest[pc] = min(lowest[pc], cash[pc])
            rounds[pc] += 1
            opened, won = sample_round(rngs[pc], picks)
            open_game[pc] = (now + timing["play"] * (1 + won) + timing["tile"] * opened, won)
        else:
            won = open_game[pc][1]
            open_game[pc] = None
            cash[pc] += payout if won else 0
            if status is None:
                if sum(cash) - initial >= target:
                    status, stopped_at = "target", now
                elif blocked():
                    status, stopped_at = ("insufficient_funds" if min(cash) < STAKE else "round_cap_or_funds"), now
                else:
                    next_start[pc] = now + timing["reveal"] + timing["between"] + (0 if won else timing["after_loss"])
    return {"status": status, "cash": cash, "rounds": rounds, "lowest": lowest, "end": now, "stop": stopped_at}


def recording(calls, results):
    def run(seed, timing, **kwargs):
        calls.append(kwargs)
        results.append(simulate_day(seed, timing, **kwargs))
        return results[-1]
    return run


class MediumTwoConfigTest(unittest.TestCase):
    def assert_same_session(self, actual, expected, start_cash):
        self.assertEqual(actual["status"], expected["status"])
        self.assertEqual(actual["pc_final_cash_cents"], expected["cash"])
        self.assertEqual(actual["pc_rounds"], expected["rounds"])
        self.assertEqual(actual["pc_minimum_cash_cents"], expected["lowest"])
        self.assertEqual(round(actual["profit"] * 100), sum(expected["cash"]) - sum(start_cash))
        self.assertAlmostEqual(actual["hours"] * 3600, expected["end"], places=6)
        self.assertAlmostEqual(actual["stop_hours"] * 3600, expected["stop"], places=6)

    def test_complete_25_cell_boards_match_the_fast_generator_exactly(self):
        expected = {LOSE_FIRST: math.comb(24, 5), LOSE_SECOND: math.comb(23, 5), WIN: math.comb(23, 6)}
        for cells in ((0, 1), (24, 0), (7, 13)):
            with self.subTest(cells=cells):
                self.assertEqual(dict(exact_board_outcomes(cells)), expected)
        total = math.comb(25, 6)
        self.assertEqual(sum(expected.values()), total)
        self.assertEqual({key: Fraction(count, total) for key, count in expected.items()}, EXACT)
        self.assertEqual(EXACT[WIN], Fraction(57, 100))
        self.assertAlmostEqual(1 - SAFE_PREFIXES[0], 6 / 25, places=15)
        self.assertAlmostEqual(SAFE_PREFIXES[0] - SAFE_PREFIXES[1], 19 / 100, places=15)
        self.assertAlmostEqual(SAFE_PREFIXES[1], 57 / 100, places=15)

    def test_complete_board_generator_and_sampled_frequencies(self):
        class Board:
            def __init__(self, mines, cells):
                self.draws, self.requests = [mines, cells], []

            def sample(self, population, count):
                self.requests.append((len(population), count))
                return self.draws.pop(0)

        for cells, outcome in (([0, 6], LOSE_FIRST), ([6, 5], LOSE_SECOND), ([6, 24], WIN)):
            board = Board([0, 1, 2, 3, 4, 5], cells)
            with self.subTest(cells=cells):
                self.assertEqual(full_board_round(board), outcome)
                self.assertEqual(board.requests, [(25, 6), (25, 2)])
        result = compare_generators(200000, "unit-test")
        for name in ("fast_vs_exact", "complete_boards_vs_exact", "fast_vs_complete_boards"):
            with self.subTest(name=name):
                self.assertGreater(result[name]["p_value"], .001)

    def test_one_game_win_returns_18_cents_total_and_a_loss_costs_10(self):
        for outcome, final, profit in ((WIN, 2008, .32), (LOSE_FIRST, 1990, -.40), (LOSE_SECOND, 1990, -.40)):
            with self.subTest(outcome=outcome), \
                 patch("analysis.collective_parallel.sample_round", return_value=outcome):
                day = simulate_day("one_game", TIMING, starting_cash_cents=[2000] * 4, round_cap=1, **PLAN)
            self.assertEqual(day["pc_final_cash_cents"], [final] * 4)
            # The minimum shows the stake already left before the board was opened, even for wins.
            self.assertEqual(day["pc_minimum_cash_cents"], [1990] * 4)
            self.assertEqual(day["profit"], profit)
            self.assertEqual(day["pc_rounds"], [1] * 4)

    def test_identical_laptops_draw_from_separate_streams(self):
        draws = []

        def capture(rng, picks=6):
            draws.append(rng.random())
            return WIN

        with patch("analysis.collective_parallel.sample_round", side_effect=capture):
            simulate_day("separate", TIMING, starting_cash_cents=[2000] * 4, round_cap=1, **PLAN)
        self.assertEqual(len(set(draws)), 4)

    def test_laptops_below_one_stake_never_play_or_borrow(self):
        for outcome, cash, rounds in ((LOSE_FIRST, [1970, 9, 0, 1970], [3, 0, 1, 3]),
                                      (WIN, [2024, 9, 34, 2024], [3, 0, 3, 3])):
            with self.subTest(outcome=outcome), \
                 patch("analysis.collective_parallel.sample_round", return_value=outcome):
                day = simulate_day("no_borrowing", TIMING, starting_cash_cents=[2000, 9, 10, 2000],
                                   round_cap=3, **PLAN)
            self.assertEqual(day["pc_final_cash_cents"], cash)
            self.assertEqual(day["pc_rounds"], rounds)
            self.assertEqual(day["pc_minimum_cash_cents"][1], 9)
            self.assertGreaterEqual(min(day["pc_minimum_cash_cents"]), 0)
            self.assertEqual(day["status"], "insufficient_funds")

    def test_500_euro_drawdown_limit_cannot_protect_the_80_euro_capital(self):
        with patch("analysis.collective_parallel.sample_round", return_value=LOSE_FIRST):
            day = simulate_day("all_losses", TIMING, starting_cash_cents=[2000] * 4, drawdown_cents=50000, **PLAN)
        self.assertEqual(day["status"], "insufficient_funds")
        self.assertEqual(day["profit"], -80)
        self.assertEqual(day["pc_final_cash_cents"], [0] * 4)
        self.assertEqual(day["pc_rounds"], [200] * 4)

    def test_plus_three_is_for_the_group_not_for_each_laptop(self):
        with patch("analysis.collective_parallel.sample_round",
                   side_effect=scripted([LOSE_FIRST], [WIN], [WIN], [WIN])):
            day = simulate_day("group_target", TIMING, starting_cash_cents=[2000] * 4, **PLAN)
        self.assertEqual(day["status"], "target")
        self.assertGreaterEqual(day["profit"], 3)
        self.assertLess(day["pc_profits"][0], 0)
        self.assertTrue(all(0 < value < 3 for value in day["pc_profits"][1:]))
        self.assertEqual(round(sum(day["pc_profits"]) * 100), round(day["profit"] * 100))

    def test_stop_counts_open_stakes_ignores_their_outcome_and_finishes_them(self):
        # Wins and second-cell losses both take 2 s here, so only the unseen payment differs.
        timing = {"play": 0.0, "tile": 1.0, "reveal": 0.0, "after_loss": 0.0, "between": 0.0}
        rows = []
        for last in (WIN, LOSE_SECOND):
            with patch("analysis.collective_parallel.sample_round",
                       side_effect=scripted([WIN], [WIN], [WIN], [WIN] * 9 + [last])):
                rows.append(simulate_day("open_stakes", timing, starting_cash_cents=[2000] * 4, **PLAN))
        for row in rows:
            self.assertEqual(row["status"], "target")
            # At laptop 3's tenth settlement laptop 4 still has an open stake: 3.20 - 0.18 = 3.02.
            self.assertEqual(row["target_stop_cash_floor"], 3.02)
            self.assertAlmostEqual(row["stop_hours"] * 3600, 20)
            self.assertAlmostEqual(row["hours"] * 3600, 20)
            self.assertEqual(row["pc_rounds"], [10] * 4)
        self.assertEqual([row["profit"] for row in rows], [3.20, 3.02])
        # Ignoring open stakes would stop one settlement earlier and can finish below +3 EUR.
        outcomes = scripted([WIN], [WIN], [WIN] * 9 + [LOSE_SECOND], [WIN] * 9 + [LOSE_SECOND])
        with patch("analysis.collective_parallel.sample_round", side_effect=outcomes):
            raw = simulate_day("open_stakes", timing, starting_cash_cents=[2000] * 4, protected=False, **PLAN)
        outcomes = scripted([WIN], [WIN], [WIN] * 9 + [LOSE_SECOND], [WIN] * 9 + [LOSE_SECOND])
        with patch("analysis.collective_parallel.sample_round", side_effect=outcomes):
            reserved = simulate_day("open_stakes", timing, starting_cash_cents=[2000] * 4, **PLAN)
        self.assertEqual((raw["status"], raw["profit"]), ("target", 2.84))
        self.assertEqual((reserved["status"], reserved["profit"]), ("target", 3.16))

    def test_second_session_gets_only_the_time_left_by_the_first(self):
        timing = {"play": 2000.0, "tile": 0.0, "reveal": 0.0, "after_loss": 0.0, "between": 0.0}
        calls, results = [], []
        with patch("analysis.collective_validation.timing_from_settings", return_value=timing), \
             patch("analysis.collective_validation.simulate_day", side_effect=recording(calls, results)), \
             patch("analysis.collective_parallel.sample_round", return_value=WIN):
            report = run_validation(months=1, days_per_month=1, picks=2, payout_cents=18,
                                    initial_bankroll_cents=2000, sessions_per_day=2, laptop_count=4)
        first, second = results
        self.assertEqual((first["status"], first["profit"], first["pc_final_cash_cents"]), ("target", 3.20, [2080] * 4))
        self.assertAlmostEqual(first["hours"] * 3600, 40000)
        self.assertEqual(calls[0]["deadline_seconds"], 43200)
        self.assertAlmostEqual(calls[1]["deadline_seconds"], 3200)
        self.assertEqual(calls[1]["starting_cash_cents"], first["pc_final_cash_cents"])
        self.assertEqual([call["target_cents"] for call in calls], [300, 300])
        self.assertEqual((second["status"], second["profit"], second["pc_rounds"]), ("deadline", .32, [1] * 4))
        row = report["monthly_rows"][0]
        self.assertEqual(row["gross_profit"], 3.52)
        self.assertAlmostEqual(row["elapsed_hours"] * 3600, 44000)
        # 240 W for all five computers over elapsed time only: 0.88 EUR, not four times that.
        self.assertEqual(row["electricity_cost_example"], .88)
        self.assertEqual(row["net_profit_after_example_electricity"], 2.64)
        self.assertEqual([(miss["session"], miss["status"]) for miss in row["non_target_sessions"]], [(2, "deadline")])
        self.assertAlmostEqual(row["non_target_sessions"][0]["start_hours"] * 3600, 40000)
        self.assertAlmostEqual(report["summary"]["maximum_settlement_overrun_seconds"], 800)

    def test_second_session_still_runs_after_a_losing_first_and_the_day_can_close_below_80(self):
        calls, results = [], []
        with patch("analysis.collective_validation.timing_from_settings", return_value=FIXED_TIMING), \
             patch("analysis.collective_validation.simulate_day", side_effect=recording(calls, results)), \
             patch("analysis.collective_parallel.sample_round", side_effect=scripted([LOSE_FIRST] * 4 + [WIN] * 5)):
            report = run_validation(months=1, days_per_month=1, picks=2, payout_cents=18,
                                    initial_bankroll_cents=2000, sessions_per_day=2, laptop_count=4)
        first, second = results
        self.assertEqual((first["status"], first["profit"], first["pc_rounds"]), ("round_cap_or_funds", -1.60, [4000] * 4))
        self.assertAlmostEqual(first["hours"] * 3600, 24438)
        self.assertAlmostEqual(calls[1]["deadline_seconds"], 43200 - 24438)
        self.assertEqual(calls[1]["starting_cash_cents"], [1960] * 4)
        self.assertEqual(calls[1]["target_cents"], 300)
        self.assertEqual((second["status"], second["profit"], second["pc_rounds"]), ("deadline", -.80, [3071] * 4))
        row = report["monthly_rows"][0]
        self.assertEqual((row["gross_profit"], row["negative_days"], row["negative_sessions"]), (-2.40, 1, 2))
        self.assertEqual(row["minimum_daily_closing_total_cash"], 77.60)
        self.assertEqual([miss["status"] for miss in row["non_target_sessions"]], ["round_cap_or_funds", "deadline"])

    def test_two_session_runner_pins_two_cells_and_18_cent_total_payment(self):
        with patch("analysis.medium_two_sessions.run_validation", return_value={}) as run:
            medium_two_sessions.run_chunk((5, 4, 2, 240))
        run.assert_called_once_with(months=5, picks=2, payout_cents=18, initial_bankroll_cents=2000,
                                    sessions_per_day=2, laptop_count=4, total_power_watts=240)

    def test_independent_reimplementation_matches_the_session_simulator(self):
        generator = random.Random(20261015)
        statuses = set()
        for case in range(1500):
            count = generator.randint(1, 4)
            cash = [generator.choice((0, 9, 10, 19, 20, 28, 45, 80, 2000)) for _ in range(count)]
            timing = {"play": generator.choice((.5, 1.0)), "tile": generator.choice((.5, 2.0)),
                      "reveal": generator.choice((0.0, 1.0)), "after_loss": generator.choice((0.0, 1.0)),
                      "between": 0.0}
            cap = generator.randint(1, 50)
            deadline = generator.choice((.5, 4.0, 30.0, 120.0, 43200.0))
            target = generator.choice((8, 18, 60, 150, 300))
            expected = reference_session(f"reference:{case}", timing, cash, target, deadline, cap)
            actual = simulate_day(f"reference:{case}", timing, laptop_count=count, starting_cash_cents=cash,
                                  picks=2, payout_cents=18, target_cents=target, deadline_seconds=deadline,
                                  round_cap=cap)
            with self.subTest(case=case):
                self.assert_same_session(actual, expected, cash)
            statuses.add(expected["status"])
        self.assertEqual(statuses, {"target", "deadline", "insufficient_funds", "round_cap_or_funds"})
        for case, deadline in enumerate((43200.0, 1800.0, 600.0) * 4):
            expected = reference_session(f"full:{case}", TIMING, [2000] * 4, deadline=deadline)
            actual = simulate_day(f"full:{case}", TIMING, starting_cash_cents=[2000] * 4,
                                  deadline_seconds=deadline, **PLAN)
            with self.subTest(full=case):
                self.assert_same_session(actual, expected, [2000] * 4)

    def test_month_loop_matches_reference_sessions_carried_day_by_day(self):
        master = 123456789
        with patch("analysis.collective_validation.secrets.randbits", return_value=master):
            report = run_validation(months=2, days_per_month=3, picks=2, payout_cents=18,
                                    initial_bankroll_cents=2000, sessions_per_day=2, laptop_count=4)
        for month, row in enumerate(report["monthly_rows"], 1):
            bank, lowest, hours, worst = [2000] * 4, [2000] * 4, 0.0, None
            for day in range(1, 4):
                before, elapsed = sum(bank), 0.0
                for session in (1, 2):
                    result = reference_session(f"{master}:month:{month}:day:{day}:session:{session}",
                                               TIMING, bank, deadline=43200 - elapsed)
                    bank, elapsed = result["cash"], elapsed + result["end"]
                    lowest = [min(pair) for pair in zip(lowest, result["lowest"])]
                hours += elapsed / 3600
                worst = (sum(bank) - before) if worst is None else min(worst, sum(bank) - before)
            with self.subTest(month=month):
                self.assertEqual(row["final_cash_per_pc"], [value / 100 for value in bank])
                self.assertEqual(row["minimum_cash_per_pc"], [value / 100 for value in lowest])
                self.assertEqual(row["gross_profit"], (sum(bank) - 8000) / 100)
                self.assertEqual(row["worst_day"], worst / 100)
                self.assertAlmostEqual(row["elapsed_hours"], hours, places=9)

    def test_session_recurrence_matches_brute_force_enumeration(self):
        games, barrier = 12, 16
        miss = negative = 0.0
        for sequence in itertools.product((True, False), repeat=games):
            profit = peak = 0
            probability = 1.0
            for won in sequence:
                profit += 8 if won else -10
                probability *= .57 if won else .43
                peak = max(peak, profit)
            if peak < barrier:
                miss += probability
                negative += probability if profit < 0 else 0
        theory = session_cap_theory(barrier, games=games, trim=0)
        self.assertAlmostEqual(theory["miss_probability"], miss, places=12)
        self.assertAlmostEqual(theory["miss_and_negative_probability"], negative, places=12)
        self.assertAlmostEqual(theory["target_reached_probability"] + miss, 1, places=12)

    def test_lower_win_payment_bounds_the_chance_of_ever_reaching_plus_three(self):
        self.assertIsNone(reach_upper_bound(18))
        for payout in (17, 17.5):
            bound = reach_upper_bound(payout)
            rate = -math.log(bound) / 300
            with self.subTest(payout=payout):
                self.assertAlmostEqual(.57 * math.exp(rate * (payout - 10)) + .43 * math.exp(-rate * 10), 1, places=12)
        self.assertLess(reach_upper_bound(17), .08)
        self.assertGreater(reach_upper_bound(17.5), reach_upper_bound(17))


if __name__ == "__main__":
    unittest.main()
