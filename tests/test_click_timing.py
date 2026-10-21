"""Click order, timing migration and safe interruption without physical mouse use."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from client_store import ClientStore, default_calibration, validate_calibration
from game_engine import GameEngine, PreparationStopped, ScreenAdapter
from mine_protocol import DEFAULT_CONFIG
from tests.test_lan_system import calibration


class ClickTimingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "laptop.sqlite3"
        self.store = ClientStore(self.path)
        self.c = calibration()
        self.emergency, self.stop = threading.Event(), threading.Event()
        self.trace = []
        self.adapter = type("FakeScreen", (), {})()
        self.adapter.size = lambda: (100, 100)
        self.adapter.click = lambda point: self.trace.append(("click", point))
        self.adapter.color = lambda tile: "blue"
        self.adapter.board = lambda: ["blue"] * 19 + ["red"] * 6
        self.engine = GameEngine(self.store, self.emergency, self.stop, adapter_factory=lambda c: self.adapter)
        self.grant = {"id": "round", "status": "reserved", "config": {**DEFAULT_CONFIG, "selection": "fixed"}}
        self.store.update(round=deepcopy(self.grant))

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def record_waits(self):
        self.engine.wait = lambda seconds: self.trace.append(("wait", seconds))
        self.engine.preparation_wait = lambda seconds, stop: self.engine.wait(seconds)

    def test_separate_first_second_collect_timings_without_difficulty_clicks(self):
        self.c["delays"] = {key: (i + 1) / 1000 for i, key in enumerate(self.c["delays"])}
        d = self.c["delays"]
        self.record_waits()
        self.engine.run_round(self.grant, self.c)
        expected = []
        def clicked(delay, point):
            expected.extend([("wait", delay), ("click", point), ("wait", d["after_click"])])
        clicked(d["play"], self.c["play"])
        expected.append(("wait", d["after_play"]))
        clicked(d["tile"], self.c["tiles"]["1"])
        expected.append(("wait", d["after_tile"]))
        clicked(d["second_tile"], self.c["tiles"]["2"])
        expected.append(("wait", d["after_second_tile"]))
        clicked(d["collect"], self.c["play"])
        expected.append(("wait", d["reveal"]))
        self.assertEqual([item for item in self.trace if item != ("wait", 0)], expected)
        actions = [e["body"]["action"] for e in self.store.events() if e["kind"] == "intent"]
        self.assertEqual(actions, ["play", "tile:1", "tile:2", "collect"])
        self.trace.clear()
        self.store.update(round=deepcopy(self.grant))
        self.engine.run_round(self.grant, self.c)
        self.assertEqual([item for item in self.trace if item[0] == "click"],
                         [("click", self.c["play"]), ("click", self.c["tiles"]["1"]),
                          ("click", self.c["tiles"]["2"]), ("click", self.c["play"])])

    def test_board_has_one_initial_wait_and_two_independent_retry_waits(self):
        self.c["delays"].update(reveal=0.013, board_retry=0.029)
        self.adapter.board = lambda: [None] * 25
        self.record_waits()
        self.engine.run_round(self.grant, self.c)
        self.assertEqual(self.trace.count(("wait", 0.013)), 1)
        self.assertEqual(self.trace.count(("wait", 0.029)), 2)
        self.assertFalse(self.store.events()[-1]["body"]["board_complete"])

    def test_bet_clicks_each_have_explicit_pause_and_ignore_group_pause(self):
        self.c["bet_values"] = [100, 200, 500]
        self.c["steps"] += [{"action": "click", "point": [95, 95]}]
        self.c["delays"]["after_click"] = 0.017
        self.stop.set()
        self.record_waits()
        self.engine.apply_bet({**DEFAULT_CONFIG, "stake": 500}, 3, self.c)
        clicks = [item for item in self.trace if item[0] == "click"]
        self.assertEqual(clicks, [("click", self.c["lower"])] * 3 + [("click", self.c["raise"])] * 2 + [("click", [95, 95])] +
                         [("click", self.c["difficulty_lower"])] * 4 + [("click", self.c["difficulty_raise"])])
        self.assertEqual(self.trace.count(("wait", 0.017)), len(clicks))
        self.assertEqual(self.store.snapshot()["applied_revision"], 3)
        self.assertTrue(self.engine.difficulty_prepared)

    def test_disarm_during_bet_stops_and_clears_preparation_flags(self):
        self.engine.setup_stop = threading.Event()
        self.adapter.click = lambda point: self.engine.setup_stop.set()
        with self.assertRaises(PreparationStopped):
            self.engine.apply_bet(DEFAULT_CONFIG, 3, self.c)
        state = self.store.snapshot()
        self.assertFalse(state["bet_in_progress"])
        self.assertEqual(state["applied_revision"], 0)
        self.assertIsNone(state["applied_stake"])
        self.assertFalse(self.emergency.is_set())

    def test_long_preparation_wait_is_interruptible_within_poll_interval(self):
        self.engine.setup_stop = threading.Event()
        timer = threading.Timer(0.02, self.engine.setup_stop.set)
        timer.start()
        beginning = time.monotonic()
        try:
            with self.assertRaises(PreparationStopped):
                self.engine.preparation_wait(10, self.engine.setup_stop)
            self.assertLess(time.monotonic() - beginning, 0.5)
        finally:
            timer.join()

    def test_medium_is_prepared_once_and_not_repeated_by_rounds_or_stake_change(self):
        self.c["bet_values"] = [100, 200]
        self.engine.apply_bet(DEFAULT_CONFIG, 1, self.c)
        setup = [("click", self.c["difficulty_lower"])] * 4 + [("click", self.c["difficulty_raise"])]
        self.assertEqual(self.trace[-5:], setup)
        self.assertTrue(self.engine.difficulty_prepared)
        self.assertFalse(self.store.events())
        self.trace.clear()
        for _ in range(2):
            self.store.update(round=deepcopy(self.grant))
            self.engine.run_round(self.grant, self.c)
        self.engine.apply_bet({**DEFAULT_CONFIG, "stake": 200}, 2, self.c)
        self.assertNotIn(("click", self.c["difficulty_lower"]), self.trace)
        self.assertNotIn(("click", self.c["difficulty_raise"]), self.trace)
        self.assertEqual(self.store.snapshot()["applied_revision"], 2)

    def test_interrupted_difficulty_preparation_stays_unconfirmed_and_retries_whole_setup(self):
        self.engine.setup_stop = threading.Event()
        def click(point):
            self.trace.append(("click", point))
            if point == self.c["difficulty_lower"]:
                self.engine.setup_stop.set()
        self.adapter.click = click
        with self.assertRaises(PreparationStopped):
            self.engine.apply_bet(DEFAULT_CONFIG, 1, self.c)
        self.assertFalse(self.engine.difficulty_prepared)
        self.assertFalse(self.store.snapshot()["bet_in_progress"])
        self.assertEqual(self.store.snapshot()["applied_revision"], 0)
        self.assertFalse(self.store.events())
        self.engine.setup_stop.clear()
        self.trace.clear()
        self.adapter.click = lambda point: self.trace.append(("click", point))
        self.engine.apply_bet(DEFAULT_CONFIG, 1, self.c)
        self.assertEqual(self.trace[-5:], [("click", self.c["difficulty_lower"])] * 4 + [("click", self.c["difficulty_raise"])])
        self.assertTrue(self.engine.difficulty_prepared)
        self.assertEqual(self.store.snapshot()["applied_revision"], 1)

    def test_restart_after_only_difficulty_intent_cancels_reserved_round(self):
        self.store.emit("intent", {"round": "round", "action": "difficulty_lower"})
        self.assertEqual(self.store.snapshot()["round"]["status"], "reserved")
        self.store.close()
        self.store = ClientStore(self.path)
        self.assertEqual(self.store.events()[-1]["kind"], "cancel")
        self.assertNotIn("uncertain", [e["kind"] for e in self.store.events()])

    def test_screen_adapter_disables_hidden_pyautogui_pause(self):
        adapter = ScreenAdapter(self.c)
        with patch("game_engine.pyautogui.size", return_value=(100, 100)), patch("game_engine.pyautogui.click") as click:
            adapter.click([70, 80])
            click.assert_called_once_with(70, 80, _pause=False)
        with patch("game_engine.pyautogui.size", return_value=(90, 90)), patch("game_engine.pyautogui.click") as click:
            with self.assertRaisesRegex(RuntimeError, "Geometria"):
                adapter.click([70, 80])
            click.assert_not_called()

    def test_migration_preserves_old_times_and_requires_new_difficulty_calibration(self):
        c = calibration()
        for key in ("difficulty_lower", "difficulty_raise"):
            c.pop(key)
        old_delays = {key: (i + 1) / 7 for i, key in enumerate(("play", "after_play", "tile", "after_tile", "retry", "reveal", "bet", "reset", "between"))}
        c["delays"] = deepcopy(old_delays)
        self.store.update(calibration=c)
        self.store.close()
        self.store = ClientStore(self.path)
        migrated = self.store.snapshot()["calibration"]
        self.assertEqual({key: migrated["delays"][key] for key in old_delays}, old_delays)
        for new, old in (("collect", "play"), ("second_tile", "tile"), ("after_second_tile", "after_tile"), ("board_retry", "reveal")):
            self.assertEqual(migrated["delays"][new], old_delays[old])
        self.assertEqual(migrated["difficulty_lower"], [0, 0])
        with self.assertRaisesRegex(ValueError, "Calibrare entrambi"):
            validate_calibration(migrated, (100, 100), DEFAULT_CONFIG)
        self.assertEqual(migrated["delays"]["after_click"], 0.1)

    def test_legacy_import_recovers_explicit_difficulty_coordinates_and_waits(self):
        path = Path(self.temp.name) / "legacy.json"
        path.write_text(json.dumps({"lower_diff_x": 70, "lower_diff_y": 80, "raise_diff_x": 80, "raise_diff_y": 80,
                                    "sleep_decrease_diff_force": 0.11, "sleep_set_difficulty": 0.23,
                                    "sleep_play_or_collect": 0.3, "sleep_click_tile": 0.4,
                                    "sleep_after_tile_click": 0.6, "tile_reveal_delay": 0.7}), encoding="utf-8")
        before = path.read_bytes()
        self.store.import_legacy(path)
        c = self.store.snapshot()["calibration"]
        self.assertEqual(c["difficulty_lower"], [70, 80])
        self.assertEqual(c["difficulty_raise"], [80, 80])
        self.assertEqual(c["delays"]["difficulty_lower"], 0.11)
        self.assertEqual(c["delays"]["difficulty_raise"], 0.23)
        self.assertEqual(c["delays"]["collect"], 0.3)
        self.assertEqual(c["delays"]["second_tile"], 0.4)
        self.assertEqual(c["delays"]["after_second_tile"], 0.6)
        self.assertEqual(c["delays"]["board_retry"], 0.7)
        self.assertEqual(path.read_bytes(), before)

    def test_difficulty_coordinates_are_distinct_and_within_screen(self):
        for point in ([0, 0], self.c["play"], self.c["difficulty_lower"], [100, 80]):
            with self.subTest(point=point):
                c = deepcopy(self.c)
                c["difficulty_raise"] = point
                with self.assertRaises(ValueError):
                    validate_calibration(c, (100, 100), DEFAULT_CONFIG)


if __name__ == "__main__":
    unittest.main()
