"""Deterministic checks for the bulk simulation and comparison contracts."""

from copy import deepcopy
import json
import math
import random
import unittest
from unittest.mock import patch

from bulk_simulation import build_configurations, run_bulk_batch, summarize_runs, wilson_interval, win_probability
from game_config import BETTING_MODES, BET_VALUES, TEST_MODE_MINE_CONFIG, WIN_MULTIPLIERS


def snapshot(**changes):
    result = {
        "starting_cash": 100.0, "target_profit": 5.0, "max_loss": 20.0,
        "max_rounds": 100, "mode": "normal", "betting_sequence": [1.0],
        "betting_modes": {**deepcopy(BETTING_MODES), "normal": [1.0]},
        "bet_values": list(BET_VALUES), "custom_mode": [],
        "max_picks": 1, "difficulty": "low", "grinding_enabled": False,
        "grinding_range": 0.0, "p_random": False,
        "win_multipliers": {difficulty: {picks: 2.0 for picks in multipliers}
                            for difficulty, multipliers in WIN_MULTIPLIERS.items()},
        "mine_config": {difficulty: 0 for difficulty in TEST_MODE_MINE_CONFIG},
    }
    result.update(changes)
    return result


def batch(settings, n=1, **options):
    callbacks = {"progress_cb": lambda *_: None, "log_cb": lambda _: None,
                 "stop_check": lambda: False, "show_logs": lambda: False}
    callbacks.update(options)
    return run_bulk_batch(build_configurations(settings), n, 1234, **callbacks)


class BulkSimulationTest(unittest.TestCase):
    def test_exact_large_and_fractional_thresholds(self):
        for target in (0.25, 5.25, 101, 101.25):
            with self.subTest(target=target):
                result = batch(snapshot(target_profit=target, max_loss=7.25, max_rounds=200), n=3)
                config = result["configurations"][0]
                self.assertEqual(config["profit_thresholds"][-1], target)
                self.assertTrue(all(value <= target for value in config["profit_thresholds"]))
                self.assertEqual(config["loss_thresholds"], [5.0, 7.25])
                self.assertTrue(all(count == 3 for row in config["success_counts"] for count in row))
                self.assertEqual(config["summary"]["target_rate"], 100)
                self.assertEqual(config["summary"]["completed_runs"], 3)
                self.assertEqual(result["status"], "completed")
                json.dumps(result, allow_nan=False)

    def test_custom_uses_every_steps_bet_picks_and_difficulty(self):
        settings = snapshot(mode="custom", target_profit=14.4, max_rounds=2,
                            custom_mode=[{"b": 1, "p": 1, "d": "low"},
                                         {"b": 2, "p": 4, "d": "high"}])
        settings["mine_config"]["low"] = 25
        settings["win_multipliers"]["high"][4] = 8.7
        config = batch(settings)["configurations"][0]
        run = config["runs"][0]
        self.assertEqual((run["status"], run["rounds"], run["profit"]), ("target", 2, 14.4))
        self.assertEqual(run["max_drawdown"], 1)
        self.assertEqual(run["threshold_drawdowns"], [1] * len(config["profit_thresholds"]))

    def test_medium_six_cells_uses_exact_probability_and_custom_payout(self):
        self.assertAlmostEqual(win_probability(6, 6), math.comb(19, 6) / math.comb(25, 6))
        self.assertEqual(WIN_MULTIPLIERS["medium"][4], 3.2)
        self.assertEqual(WIN_MULTIPLIERS["medium"][5], 4.6)
        settings = snapshot(mode="custom", target_profit=10.6, max_rounds=2,
                            win_multipliers=deepcopy(WIN_MULTIPLIERS),
                            custom_mode=[{"b": 1, "p": 1, "d": "low"},
                                         {"b": 2, "p": 6, "d": "medium"}])
        settings["mine_config"]["low"] = 25
        run = batch(settings)["configurations"][0]["runs"][0]
        self.assertEqual((run["status"], run["rounds"], run["profit"]), ("target", 2, 10.6))

    def test_medium_six_cells_and_legacy_four_cell_snapshot(self):
        settings = snapshot(difficulty="medium", max_picks=6, target_profit=5.8,
                            win_multipliers=deepcopy(WIN_MULTIPLIERS))
        run = batch(json.loads(json.dumps(settings)))["configurations"][0]["runs"][0]
        self.assertEqual((run["status"], run["rounds"], run["profit"]), ("target", 1, 5.8))
        legacy = deepcopy(settings)
        legacy["win_multipliers"]["medium"] = {p: value for p, value in WIN_MULTIPLIERS["medium"].items() if p <= 4}
        legacy["max_picks"] = 4
        self.assertTrue(batch(legacy)["configurations"][0]["runs"])
        for picks in (6, 7, 8):
            legacy["max_picks"] = picks
            with self.subTest(picks=picks), self.assertRaisesRegex(ValueError, "Moltiplicatore mancante"):
                batch(legacy)

    def test_medium_seven_and_eight_cells_pay_confirmed_minimum_stake_quotes(self):
        for picks, payout, profit in ((7, 1.0, 0.9), (8, 1.5, 1.4)):
            self.assertAlmostEqual(win_probability(6, picks), math.comb(19, picks) / math.comb(25, picks))
            for mode in ("normal", "custom"):
                settings = snapshot(mode=mode, difficulty="medium", max_picks=picks,
                                    target_profit=profit, max_rounds=1,
                                    betting_modes={**deepcopy(BETTING_MODES), "normal": [0.1]},
                                    custom_mode=[{"b": 0.1, "p": picks, "d": "medium"}],
                                    mine_config=deepcopy(TEST_MODE_MINE_CONFIG),
                                    win_multipliers=deepcopy(WIN_MULTIPLIERS))
                with self.subTest(picks=picks, mode=mode), patch("bulk_simulation.random.Random.random", return_value=0):
                    run = batch(json.loads(json.dumps(settings)))["configurations"][0]["runs"][0]
                self.assertEqual((run["status"], run["rounds"], run["profit"]), ("target", 1, profit))
                self.assertEqual(run["wagered"], 0.1)
                self.assertAlmostEqual(run["profit"] + run["wagered"], payout)
                self.assertEqual(run["final_cash"], 100 + profit)

    def test_unavailable_low_and_high_payouts_fail_before_any_play(self):
        for difficulty, picks in (("low", 5), ("high", 6), ("low", 8), ("high", 8)):
            for mode in ("normal", "custom"):
                settings = snapshot(mode=mode, difficulty=difficulty, max_picks=picks,
                                    custom_mode=[{"b": 1, "p": picks, "d": difficulty}])
                with self.subTest(difficulty=difficulty, picks=picks, mode=mode), \
                     patch("bulk_simulation._play_run") as play, \
                     self.assertRaisesRegex(ValueError, "Moltiplicatore mancante"):
                    batch(settings)
                play.assert_not_called()

    def test_stop_inside_second_run_excludes_partial_statistics(self):
        calls = 0

        def stop():
            nonlocal calls
            calls += 1
            return calls == 6

        progress = []
        result = batch(snapshot(target_profit=2), n=3, stop_check=stop,
                       progress_cb=lambda done, total: progress.append((done, total)))
        config = result["configurations"][0]
        self.assertEqual(result["status"], "interrupted")
        self.assertEqual([run["status"] for run in config["runs"]], ["target", "interrupted"])
        self.assertEqual(config["runs"][1]["rounds"], 1)
        self.assertEqual(config["summary"]["completed_runs"], 1)
        self.assertEqual(config["summary"]["interrupted_runs"], 1)
        self.assertEqual(config["summary"]["avg_profit"], 2)
        self.assertEqual(config["success_counts"], [[1, 1]] * 4)
        self.assertEqual(progress, [(1, 3)])

    def test_all_stop_causes_and_stop_before_any_run(self):
        losers = {difficulty: 25 for difficulty in TEST_MODE_MINE_CONFIG}
        cases = [
            (snapshot(target_profit=1), "target", 1),
            (snapshot(mine_config=losers, max_loss=2), "max_loss", 2),
            (snapshot(target_profit=10, max_rounds=2), "max_rounds", 2),
            (snapshot(starting_cash=0.5), "insufficient_funds", 0),
        ]
        for settings, status, rounds in cases:
            with self.subTest(status=status):
                run = batch(settings)["configurations"][0]["runs"][0]
                self.assertEqual((run["status"], run["rounds"]), (status, rounds))
        stopped = batch(snapshot(), stop_check=lambda: True)
        self.assertEqual(stopped["status"], "interrupted")
        self.assertEqual(stopped["configurations"][0]["runs"], [])
        self.assertIsNone(stopped["configurations"][0]["summary"]["target_rate"])

    def test_internal_rng_is_repeatable_without_exporting_its_state(self):
        settings = snapshot(mine_config=deepcopy(TEST_MODE_MINE_CONFIG), max_picks=3)
        before = random.getstate()
        first, second = batch(settings, 8), batch(settings, 8)
        self.assertEqual(before, random.getstate())
        self.assertEqual(first["configurations"], second["configurations"])
        self.assertNotIn("seed", first)
        self.assertTrue(all("seed" not in run for run in first["configurations"][0]["runs"]))
        restored = json.loads(json.dumps(settings))
        self.assertEqual(batch(restored, 8)["configurations"][0]["runs"],
                         first["configurations"][0]["runs"])

    def test_comparison_product_deduplicates_custom_picks_and_difficulty(self):
        settings = snapshot(custom_mode=[{"b": 1, "p": 4, "d": "high"}])
        original = deepcopy(settings)
        configurations = build_configurations(settings, modes=["normal", "custom", "normal"],
                                               difficulties=["low", "high"], picks=[1, 3],
                                               grinding=[False, True])
        self.assertEqual(len(configurations), 10)
        self.assertEqual(sum(snap["mode"] == "custom" for snap in configurations), 2)
        self.assertEqual(settings, original)
        configurations[0]["mine_config"]["low"] = 25
        self.assertEqual(configurations[1]["mine_config"]["low"], 0)
        with self.assertRaises(ValueError):
            build_configurations(settings, picks=[])

    def test_summary_percentiles_and_wilson_extremes(self):
        runs = [{"status": status, "profit": profit, "rounds": rounds, "max_drawdown": drawdown}
                for status, profit, rounds, drawdown in
                [("target", 2, 2, 0), ("max_loss", -1, 5, 3), ("max_rounds", 3, 4, 2),
                 ("insufficient_funds", 0, 1, 0), ("interrupted", 999, 999, 999)]]
        summary = summarize_runs(runs)
        self.assertEqual(summary["completed_runs"], 4)
        self.assertEqual(summary["interrupted_runs"], 1)
        self.assertEqual(summary["avg_profit"], 1)
        self.assertEqual(summary["median_profit"], 1)
        self.assertEqual(summary["avg_rounds"], 3)
        self.assertEqual(summary["target_rate"], 25)
        self.assertEqual(summary["positive_rate"], 50)
        self.assertAlmostEqual(summary["p05_profit"], -0.85)
        self.assertAlmostEqual(summary["p95_profit"], 2.85)
        self.assertEqual(summary["max_drawdown"], 3)
        self.assertEqual(wilson_interval(0, 0), (None, None))
        low, high = wilson_interval(0, 10)
        self.assertAlmostEqual(low, 0)
        self.assertAlmostEqual(high, 27.75328, places=4)
        low, high = wilson_interval(10, 10)
        self.assertAlmostEqual(low, 72.24672, places=4)
        self.assertAlmostEqual(high, 100)

    def test_periodic_checkpoint_preserves_current_session(self):
        checkpoints = []
        clock = iter(range(100))
        with patch("bulk_simulation.time.monotonic", side_effect=lambda: next(clock)):
            result = batch(snapshot(target_profit=20, max_rounds=10),
                           checkpoint_cb=lambda state: checkpoints.append(deepcopy(state)))
        partial = [state["configurations"][0] for state in checkpoints
                   if state["configurations"][0]["summary"]["interrupted_runs"]]
        self.assertTrue(partial)
        self.assertGreater(partial[0]["runs"][0]["rounds"], 0)
        self.assertEqual(partial[0]["summary"]["completed_runs"], 0)
        self.assertEqual(checkpoints[-1], result)

    def test_invalid_inputs_fail_before_simulation(self):
        cases = [{"starting_cash": float("nan")}, {"target_profit": float("inf")},
                 {"max_loss": 0}, {"max_rounds": 1.5}, {"max_picks": 9},
                 {"mode": "custom", "custom_mode": [{"b": 0.1, "p": 9, "d": "medium"}]},
                 {"mode": "custom", "custom_mode": []}, {"bet_values": []},
                 {"bet_values": [0.1]}, {"grinding_enabled": True, "bet_values": [1]}]
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                batch(snapshot(**changes))
        for invalid_mines in (-1, 26, float("nan"), 1.5):
            settings = snapshot()
            settings["mine_config"]["low"] = invalid_mines
            with self.subTest(mines=invalid_mines), self.assertRaises(ValueError):
                batch(settings)
        for invalid_multiplier in (0, -1, float("inf"), float("nan")):
            settings = snapshot()
            settings["win_multipliers"]["low"][1] = invalid_multiplier
            with self.subTest(multiplier=invalid_multiplier), self.assertRaises(ValueError):
                batch(settings)


if __name__ == "__main__":
    unittest.main()
