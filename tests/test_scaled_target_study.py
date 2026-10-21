"""Target times use settled, carried balances and a strict daily time budget."""

import unittest
from unittest.mock import patch

from analysis import collective_parallel as parallel
from analysis import scaled_target_study as experiment


TIMING = parallel.timing_from_settings({})


class ScaledTargetStudyTest(unittest.TestCase):
    def test_electricity_rounds_half_up_once_on_total_activity(self):
        for seconds, cents in ((0, 0), (249, 0), (250, 1), (749, 1),
                               (750, 2), (1000, 2), (18000, 36)):
            with self.subTest(seconds=seconds):
                self.assertEqual(experiment.electricity_cents(seconds), cents)
        self.assertNotEqual(experiment.electricity_cents(249) * 4,
                            experiment.electricity_cents(249 * 4))

    def test_hit_excludes_initial_capital_and_deducts_cumulative_cost(self):
        timing = {key: value * 10 for key, value in TIMING.items()}
        with patch.object(experiment, "GOAL_CENTS", 320), \
             patch.object(parallel, "sample_round", return_value=(2, True)):
            row = experiment.run_path((123, 1, 2, timing))
        self.assertEqual(row["status"], "hit")
        self.assertEqual(row["hit_day"], 1)
        self.assertEqual(row["sessions_with_bets"], 2)
        self.assertEqual(row["previous_checkpoint_net_cents"], 319)
        self.assertEqual(row["net_profit_cents"], 637)
        self.assertEqual(row["final_cash_cents_per_pc"], [2160] * 4)
        self.assertEqual(row["total_rounds"], 80)
        self.assertLess(row["previous_checkpoint_net_cents"], 320)
        self.assertGreaterEqual(row["net_profit_cents"], 320)

    def test_individual_balances_carry_across_sessions_and_days(self):
        starts = []
        simulate = parallel.simulate_day

        def capture(seed, timing, **kwargs):
            starts.append(list(kwargs["starting_cash_cents"]))
            return simulate(seed, timing, **kwargs)

        with patch.object(experiment, "GOAL_CENTS", 620), \
             patch.object(parallel, "sample_round", return_value=(2, True)), \
             patch.object(parallel, "simulate_day", side_effect=capture):
            experiment.run_path((123, 1, 1, TIMING))
        self.assertEqual(starts, [[2000] * 4, [2080] * 4])

        starts.clear()
        slow = dict(play=0, tile=900, after_loss=0, reveal=0, between=0)
        with patch.object(experiment, "GOAL_CENTS", 500), \
             patch.object(parallel, "sample_round", return_value=(2, True)), \
             patch.object(parallel, "simulate_day", side_effect=capture):
            row = experiment.run_path((123, 1, 2, slow))
        self.assertEqual(starts, [[2000] * 4, [2072] * 4])
        self.assertEqual(row["hit_day"], 2)
        self.assertEqual(row["final_cash_cents_per_pc"], [2144] * 4)
        self.assertEqual(row["net_profit_cents"], 511)
        self.assertAlmostEqual(row["activity_hours"], 9)

    def test_daily_time_includes_completion_of_open_rounds(self):
        deadlines = []
        simulate = parallel.simulate_day

        def capture(seed, timing, **kwargs):
            deadlines.append(kwargs["deadline_seconds"])
            return simulate(seed, timing, **kwargs)

        with patch.object(parallel, "sample_round", return_value=(2, True)), \
             patch.object(parallel, "simulate_day", side_effect=capture):
            row = experiment.run_path((123, 1, 1, TIMING))
        self.assertEqual(row["status"], "horizon")
        self.assertIsNone(row["hit_day"])
        self.assertLessEqual(max(deadlines), 18000 - 6)
        self.assertLessEqual(row["maximum_daily_seconds"], 18000)
        self.assertLessEqual(row["activity_hours"], 5)
        gross = sum(row["final_cash_cents_per_pc"]) - 8000
        cost = experiment.electricity_cents(row["activity_hours"] * 3600)
        self.assertEqual(row["net_profit_cents"], gross - cost)

    def test_all_losses_end_when_all_laptops_are_unfunded(self):
        with patch.object(parallel, "sample_round", return_value=(1, False)):
            row = experiment.run_path((456, 1, 30, TIMING))
        self.assertEqual(row["status"], "all_unfunded")
        self.assertIsNone(row["hit_day"])
        self.assertEqual(row["sessions_with_bets"], 1)
        self.assertEqual(row["total_rounds"], 800)
        self.assertEqual(row["final_cash_cents_per_pc"], [0] * 4)
        self.assertEqual(row["minimum_cash_cents_per_pc"], [0] * 4)
        self.assertTrue(row["any_pc_unfunded_at_session_close"])
        cost = experiment.electricity_cents(row["activity_hours"] * 3600)
        self.assertEqual(row["net_profit_cents"], -8000 - cost)

    def test_scale_changes_money_but_preserves_session_target_and_drawdown(self):
        calls = []
        simulate = parallel.simulate_day

        def capture(seed, timing, **kwargs):
            calls.append((parallel.STAKE, kwargs))
            return simulate(seed, timing, **kwargs)

        with patch.object(experiment, "GOAL_CENTS", 1), \
             patch.object(parallel, "sample_round", return_value=(2, True)), \
             patch.object(parallel, "simulate_day", side_effect=capture):
            row = experiment.run_path((123, 5, 1, TIMING))
        stake, config = calls[0]
        self.assertEqual(stake, 50)
        self.assertEqual(config["starting_cash_cents"], [10000] * 4)
        self.assertEqual(config["payout_cents"], 90)
        self.assertEqual(config["target_cents"], 300)
        self.assertEqual(config["drawdown_cents"], 50000)
        self.assertEqual(config["round_cap"], 4000)
        self.assertEqual(config["laptop_count"], 4)
        self.assertEqual(config["picks"], 2)
        self.assertTrue(config["protected"])
        self.assertFalse(config["floor_lock"])
        self.assertEqual(row["scale"], 5)
        self.assertEqual(row["status"], "hit")
        self.assertGreater(row["total_rounds"], 0)

    def test_global_stake_is_restored_after_failure(self):
        with patch.object(parallel, "STAKE", 77):
            with patch.object(parallel, "sample_round", side_effect=RuntimeError("test")):
                with self.assertRaisesRegex(RuntimeError, "test"):
                    experiment.run_path((123, 5, 1, TIMING))
            self.assertEqual(parallel.STAKE, 77)
        self.assertEqual(parallel.STAKE, 10)

    def test_invalid_research_inputs_are_rejected_before_workers_start(self):
        invalid = ({"replicates": 0}, {"replicates": True}, {"workers": 0},
                   {"workers": True}, {"max_days": 0}, {"max_days": 1.5},
                   {"scales": ()}, {"scales": [0]}, {"scales": [True]},
                   {"scales": [1, 1]}, {"scales": [1.5]}, {"scales": "12"})
        with patch.object(experiment, "ProcessPoolExecutor",
                          side_effect=AssertionError("workers started before validation")):
            for kwargs in invalid:
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    experiment.run_research(**kwargs)


if __name__ == "__main__":
    unittest.main()
