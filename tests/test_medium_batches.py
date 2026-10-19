"""Compare synchronized array batches with a causal, one-round-at-a-time event queue."""

import heapq
import itertools
import random
import unittest
from unittest.mock import patch

import numpy as np

from analysis import medium_batches as batches
from analysis.collective_parallel import timing_from_settings


TIMING = timing_from_settings({})


class PatternRng:
    def __init__(self, values):
        self.values = itertools.cycle(values)
        self.calls = 0

    def random(self, size=None):
        self.calls += 1
        return next(self.values) if size is None else np.array([next(self.values) for _ in range(size)])


def reference(seed, timing, cash, batch_size, target=300, cap=4000, deadline=43200, drawdown=50000, mines=6):
    rngs = batches.make_rngs(seed, len(cash))
    cash, minimum = list(cash), list(cash)
    initial, count = sum(cash), len(cash)
    rounds, pending = [0] * count, [False] * count
    batch_start, ready, finished = [0] * count, [0.0] * count, [False] * count
    events = [(deadline, 0, -1, False), (0.0, 3, -1, False)]
    heapq.heapify(events)
    settled = peak = maximum = 0
    stopped = None
    now = 0.0
    while stopped is None or any(pending):
        at, kind, pc, won = heapq.heappop(events)
        if stopped is not None and kind != 1:
            continue
        now = at
        if kind == 0:
            stopped = "deadline"
            continue
        if kind == 3:
            batch_start = list(rounds)
            finished = [cash[p] < 10 or rounds[p] >= cap for p in range(count)]
            if all(finished):
                stopped = "insufficient_funds" if min(cash) < 10 else "round_cap_or_funds"
                continue
            for p in range(count):
                if not finished[p]:
                    heapq.heappush(events, (now, 2, p, False))
            continue
        if kind == 2:
            assert cash[pc] >= 10
            cash[pc] -= 10
            minimum[pc] = min(minimum[pc], cash[pc])
            rounds[pc] += 1
            pending[pc] = True
            draw = rngs[pc].random()
            won = draw < (25 - mines) * (24 - mines) / (25 * 24)
            opened = 1 if draw >= (25 - mines) / 25 else 2
            duration = timing["play"] * (1 + won) + opened * timing["tile"]
            heapq.heappush(events, (now + duration, 1, pc, won))
            continue
        pending[pc] = False
        cash[pc] += 18 if won else 0
        settled += 8 if won else -10
        peak = max(peak, settled)
        maximum = max(maximum, peak - settled)
        if stopped is not None:
            continue
        if peak - settled >= drawdown:
            stopped = "drawdown"
            continue
        ready[pc] = now + timing["reveal"] + timing["between"] + (0 if won else timing["after_loss"])
        finished[pc] = (rounds[pc] - batch_start[pc] >= batch_size or rounds[pc] >= cap or cash[pc] < 10)
        if not finished[pc]:
            heapq.heappush(events, (ready[pc], 2, pc, False))
        if all(finished) and not any(pending):
            if settled >= target:
                stopped = "target"
            elif all(cash[p] < 10 or rounds[p] >= cap for p in range(count)):
                stopped = "insufficient_funds" if min(cash) < 10 else "round_cap_or_funds"
            else:
                heapq.heappush(events, (max(ready), 3, -1, False))
    if stopped == "deadline" and settled >= target:
        stopped = "target"
    return {"cash": cash, "minimum": minimum, "rounds": rounds,
            "profit": settled, "status": stopped, "seconds": now, "drawdown": maximum}


class MediumBatchesTest(unittest.TestCase):
    def test_crossing_three_euros_inside_a_batch_does_not_allow_stopping(self):
        with patch.object(batches, "make_rngs", return_value=[PatternRng([0] * 25 + [.9] * 25) for _ in range(4)]):
            result = batches.simulate_batch_day("retraced", TIMING, batch_size=50, round_cap=50)
        self.assertEqual(result["profit"], -2)
        self.assertEqual(result["status"], "round_cap_or_funds")
        self.assertEqual(result["pc_rounds"], [50] * 4)
        self.assertEqual(result["pc_final_cash_cents"], [1950] * 4)

    def test_fast_laptop_waits_for_slowest_and_for_technical_result_delays(self):
        with patch.object(batches, "make_rngs", return_value=[PatternRng([0]), PatternRng([.9])]):
            result = batches.simulate_batch_day("barrier", TIMING, batch_size=2, laptop_count=2, round_cap=4)
        self.assertEqual(result["pc_rounds"], [4, 4])
        self.assertEqual(result["pc_final_cash_cents"], [2032, 1960])
        self.assertEqual(result["hours"] * 3600, 27)

    def test_stake_funding_is_individual_and_pending_stakes_count_in_minimum(self):
        rngs = [PatternRng([0]) for _ in range(4)]
        with patch.object(batches, "make_rngs", return_value=rngs):
            result = batches.simulate_batch_day("funding", TIMING, batch_size=2,
                                                starting_cash_cents=[0, 9, 10, 2000], round_cap=2)
        self.assertEqual(result["pc_rounds"], [0, 0, 2, 2])
        self.assertEqual(result["pc_final_cash_cents"], [0, 9, 26, 2016])
        self.assertEqual(result["pc_minimum_cash_cents"], [0, 9, 0, 1990])
        self.assertEqual([rng.calls for rng in rngs], [0, 0, 1, 1])

    def test_deadline_admits_same_bets_regardless_of_future_duration_or_payment(self):
        for draw, end, cash in ((0, 6, 2008), (.9, 3, 1990)):
            with self.subTest(draw=draw), patch.object(batches, "make_rngs", return_value=[PatternRng([draw]) for _ in range(4)]):
                result = batches.simulate_batch_day("deadline", TIMING, batch_size=50, deadline_seconds=2)
            self.assertEqual(result["pc_rounds"], [1] * 4)
            self.assertEqual(result["pc_final_cash_cents"], [cash] * 4)
            self.assertEqual(result["hours"] * 3600, end)
            self.assertEqual(result["status"], "deadline")

    def test_500_euro_limit_does_not_protect_eighty_euro_capital(self):
        with patch.object(batches, "make_rngs", return_value=[PatternRng([.9]) for _ in range(4)]):
            result = batches.simulate_batch_day("empty", TIMING, batch_size=50)
        self.assertEqual(result["profit"], -80)
        self.assertEqual(result["status"], "insufficient_funds")
        self.assertEqual(result["pc_rounds"], [200] * 4)

    def test_rare_drawdown_stops_are_replayed_causally_and_drain_existing_games(self):
        with patch.object(batches, "make_rngs", return_value=[PatternRng([.9]) for _ in range(4)]):
            result = batches.simulate_batch_day("drawdown", TIMING, batch_size=50, drawdown_cents=10)
        self.assertEqual(result["status"], "drawdown")
        self.assertEqual(result["pc_rounds"], [1] * 4)
        self.assertEqual(result["profit"], -.4)

    def test_vectorized_paths_match_independent_round_by_round_reference(self):
        generator = random.Random(20261017)
        for case in range(350):
            count = generator.randint(1, 4)
            cash = [generator.choice([0, 9, 10, 19, 20, 45, 2000]) for _ in range(count)]
            size = generator.choice([1, 2, 5, 50, 100])
            cap = generator.choice([1, 3, 15, 100])
            target = generator.choice([10, 30, 100, 300])
            deadline = generator.choice([2, 3, 6, 15, 100, 43200])
            drawdown = generator.choice([10, 35, 50000])
            mines = 6 + case % 2
            expected = reference(case, TIMING, cash, size, target, cap, deadline, drawdown, mines)
            result = batches.simulate_batch_day(case, TIMING, batch_size=size, laptop_count=count,
                                                starting_cash_cents=cash, round_cap=cap,
                                                target_cents=target, deadline_seconds=deadline,
                                                drawdown_cents=drawdown, mines=mines)
            with self.subTest(case=case):
                self.assertEqual(result["pc_final_cash_cents"], expected["cash"])
                self.assertEqual(result["pc_minimum_cash_cents"], expected["minimum"])
                self.assertEqual(result["pc_rounds"], expected["rounds"])
                self.assertEqual(round(result["profit"] * 100), expected["profit"])
                self.assertEqual(result["status"], expected["status"])
                self.assertAlmostEqual(result["hours"] * 3600, expected["seconds"])
                self.assertEqual(round(result["max_settled_drawdown"] * 100), expected["drawdown"])

    def test_fresh_month_loop_carries_cash_and_resets_second_target(self):
        with patch.object(batches, "make_rngs", side_effect=lambda seed, count: [PatternRng([0]) for _ in range(count)]):
            report = batches.run_chunk((1, 50, 12345, 7))
        row = report["monthly_rows"][0]
        self.assertEqual(row["gross_profit"], 960)
        self.assertEqual(row["final_cash_per_pc"], [260] * 4)
        self.assertEqual(row["sessions_executed"], 60)
        self.assertAlmostEqual(row["elapsed_hours"] * 3600, 60 * 349)
        self.assertEqual(row["electricity_cost_example"], round(.240 * .30 * row["elapsed_hours"], 2))
        self.assertEqual(report["simulation"]["picks"], 2)
        self.assertEqual(report["simulation"]["payout_on_win"], .18)
        self.assertEqual(report["simulation"]["mines"], 7)
        self.assertEqual(report["simulation"]["difficulty"], "custom")

    def test_full_sized_sessions_match_the_round_reference(self):
        for size in (50, 100):
            for case in range(10):
                seed = f"full-batch:{size}:{case}"
                mines = 6 + case % 2
                expected = reference(seed, TIMING, [2000] * 4, size, mines=mines)
                result = batches.simulate_batch_day(seed, TIMING, batch_size=size, mines=mines)
                with self.subTest(size=size, case=case, mines=mines):
                    self.assertEqual(result["pc_final_cash_cents"], expected["cash"])
                    self.assertEqual(result["pc_minimum_cash_cents"], expected["minimum"])
                    self.assertEqual(result["pc_rounds"], expected["rounds"])
                    self.assertEqual(result["status"], expected["status"])
                    self.assertAlmostEqual(result["hours"] * 3600, expected["seconds"])

    def test_single_batch_theory_is_not_a_day_or_month_loss_probability(self):
        self.assertEqual(batches.batch_theory(50)["mean_group_profit_eur"], .52)
        self.assertEqual(batches.batch_theory(100)["mean_group_profit_eur"], 1.04)
        self.assertAlmostEqual(batches.batch_theory(50)["negative_group_batch_probability"], .3594788567)
        self.assertAlmostEqual(batches.batch_theory(100)["negative_group_batch_probability"], .2887562986)

    def test_seven_mines_match_complete_board_enumeration(self):
        counts = [0, 0, 0]
        for board in itertools.combinations(range(25), 7):
            counts[0 if 0 in board else 1 if 1 in board else 2] += 1
        total = sum(counts)
        self.assertEqual([count / total for count in counts], [.28, .21, .51])
        for size in (50, 100):
            theory = batches.batch_theory(size, mines=7)
            self.assertEqual(theory["win_probability"], counts[2] / total)
            self.assertEqual(theory["expected_profit_per_game_cents"], -.82)
            self.assertEqual(theory["return_to_player_percent"], 91.8)
            self.assertEqual(theory["mean_group_profit_eur"], -1.64 if size == 50 else -3.28)

    def test_seven_mine_thresholds_change_payments_and_click_times(self):
        rngs = [PatternRng([value]) for value in (.509, .51, .719, .72)]
        with patch.object(batches, "make_rngs", return_value=rngs):
            result = batches.simulate_batch_day("thresholds", TIMING, batch_size=1, round_cap=1, mines=7)
        self.assertEqual(result["pc_final_cash_cents"], [2008, 1990, 1990, 1990])
        self.assertEqual(result["profit"], -.22)
        self.assertEqual(result["hours"] * 3600, 6)

    def test_invalid_mine_counts_are_rejected(self):
        for mines in (-1, 26, True, 7.0):
            with self.subTest(mines=mines), self.assertRaises(ValueError):
                batches.simulate_batch_day("invalid", TIMING, batch_size=50, mines=mines)
            with self.subTest(theory_mines=mines), self.assertRaises(ValueError):
                batches.batch_theory(50, mines=mines)


if __name__ == "__main__":
    unittest.main()
