"""Read complete frames and record real rounds without touching the mouse or screen."""

import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from color_detector import ColorDetector
from game_config import Point, TARGET_BLUE, TARGET_RED
from game_engine import GameEngine
from tile_history import MIN_COMPLETE_BOARDS, TileHistory


def variable(value):
    return SimpleNamespace(get=lambda: value)


def grid_points():
    return {tile: Point(10 + (tile - 1) % 5 * 10, 20 + (tile - 1) // 5 * 10)
            for tile in range(1, 26)}


class BoardReadTest(unittest.TestCase):
    def test_one_screenshot_classifies_all_cells_in_tile_order(self):
        points = grid_points()
        detector = ColorDetector(tolerance=10)
        pixels = [(TARGET_BLUE["r"], TARGET_BLUE["g"], TARGET_BLUE["b"])] * 25
        pixels[1] = (TARGET_RED["r"], TARGET_RED["g"], TARGET_RED["b"], 255)
        pixels[2] = (100, 100, 100)
        frame = Mock()
        pixel_by_point = {(point.x - 10, point.y - 20): pixels[tile - 1]
                          for tile, point in points.items()}
        frame.getpixel.side_effect = pixel_by_point.__getitem__
        with patch("color_detector.pyautogui.size", return_value=(100, 100)), \
             patch("color_detector.ImageGrab.grab", return_value=frame) as grab:
            colors = detector.read_board(points)
        grab.assert_called_once_with(bbox=(10, 20, 51, 61))
        self.assertEqual(frame.getpixel.call_count, 25)
        self.assertEqual(colors, ["blue", "red", None] + ["blue"] * 22)

    def test_ambiguous_pixels_are_unknown(self):
        shared = {"r": 10, "g": 20, "b": 30}
        detector = ColorDetector(shared, shared, tolerance=0)
        frame = Mock()
        frame.getpixel.return_value = (10, 20, 30)
        with patch("color_detector.pyautogui.size", return_value=(100, 100)), \
             patch("color_detector.ImageGrab.grab", return_value=frame) as grab:
            self.assertEqual(detector.read_board(grid_points()), [None] * 25)
        grab.assert_called_once()

    def test_invalid_coordinates_fail_before_capture(self):
        missing = grid_points()
        del missing[25]
        duplicate = grid_points()
        duplicate[25] = duplicate[24]
        negative = grid_points()
        negative[1] = Point(-1, 20)
        outside = grid_points()
        outside[1] = Point(100, 20)
        for points in (missing, duplicate, negative, outside):
            with self.subTest(points=points), \
                 patch("color_detector.pyautogui.size", return_value=(100, 100)), \
                 patch("color_detector.ImageGrab.grab") as grab:
                with self.assertRaises(ValueError):
                    ColorDetector().read_board(points)
                grab.assert_not_called()


class TileRecordingTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "tile_history.jsonl"
        self.history = TileHistory(self.path)
        clicks = patch("game_engine.pyautogui.click", side_effect=AssertionError("Real click"))
        clicks.start()
        self.addCleanup(clicks.stop)

    def engine(self, outcome="blue", custom=False, grinding=False, recording=True,
               use_history=False):
        events = []
        app = SimpleNamespace(
            tile_history=self.history, tiles=grid_points(),
            tile_record_enabled_var=variable(recording),
            tile_use_history_var=variable(use_history), tile_reveal_delay_var=variable(0),
            mode_var=variable("custom" if custom else "normal"),
            custom_mode=[{"b": 20.0, "p": 1, "d": "medium"}] if custom else [],
            betting_modes={"normal": [0.1, 0.2]}, bet_values=[0.1, 0.2, 20.0],
            grinding_mode_var=variable(grinding), grinding_range_var=variable(5),
            max_picks_var=variable(1), difficulty_var=variable("low"),
            starting_cash_var=variable(100), target_win_var=variable(101),
            max_loss_var=variable(100), sleep_after_play_var=variable(0),
            sleep_after_tile_click_var=variable(0), sleep_after_result_var=variable(0),
            sleep_color_retry_var=variable(0), game_running=True, escape_pressed=False,
            log_message=Mock(), format_money=lambda value: f"{value:.2f}",
            get_win_multiplier=lambda difficulty, picks: 1.1,
            update_stats_display=Mock(),
        )

        async def play_or_collect():
            events.append(("play_or_collect", app.tries, app.bet, app.current_difficulty))

        async def set_difficulty(difficulty):
            events.append(("difficulty", difficulty))
            app.current_difficulty = difficulty

        async def set_bet(value):
            events.append(("bet", value))
            app.bet = value

        def read_board(points):
            events.append(("board", app.tries, app.bet, app.current_difficulty))
            mines = 6 if custom else 3
            return ["blue"] * (25 - mines) + ["red"] * mines

        adapter = SimpleNamespace(
            play_or_collect=AsyncMock(side_effect=play_or_collect),
            set_difficulty=AsyncMock(side_effect=set_difficulty),
            click_tile=AsyncMock(), read_color=Mock(return_value=outcome),
            is_blue=lambda color: color == "blue", is_red=lambda color: color == "red",
            read_board=Mock(side_effect=read_board),
        )
        engine = GameEngine(app, adapter)
        engine.initialize_game_variables()
        engine.set_bet_value = AsyncMock(side_effect=set_bet)
        return engine, app, adapter, events

    def saved(self):
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines()]

    def play(self, engine):
        with patch("game_engine.asyncio.sleep", new_callable=AsyncMock):
            asyncio.run(engine.play_real_game_round())

    def test_win_records_once_after_collect_before_bet_reset(self):
        engine, app, adapter, events = self.engine()
        with patch.object(self.history, "record", wraps=self.history.record) as record:
            self.play(engine)
        record.assert_called_once()
        self.assertEqual([event[0] for event in events],
                         ["play_or_collect", "play_or_collect", "board", "bet"])
        adapter.play_or_collect.assert_awaited()
        self.assertEqual(adapter.play_or_collect.await_count, 2)
        self.assertEqual(app.rounds, 1)
        saved = self.saved()[0]
        self.assertEqual((saved["difficulty"], saved["outcome"], saved["expected_mines"]),
                         ("low", "win", 3))
        self.assertTrue(saved["complete"])

    def test_loss_preserves_round_difficulty_before_grinding_transition(self):
        engine, app, adapter, events = self.engine(outcome="red", custom=True, grinding=True)
        with patch.object(self.history, "record", wraps=self.history.record) as record:
            self.play(engine)
        record.assert_called_once()
        self.assertEqual(events[:3], [("difficulty", "medium"),
                                    ("play_or_collect", 0, 20.0, "medium"),
                                    ("board", 0, 20.0, "medium")])
        self.assertEqual(events[3:], [("difficulty", "high"), ("bet", 20.0)])
        self.assertTrue(app.grinding_active)
        self.assertEqual(app.current_difficulty, "high")
        self.assertEqual(self.saved()[0]["difficulty"], "medium")
        self.assertEqual(self.saved()[0]["outcome"], "loss")
        self.assertEqual(self.history.stats("medium")["complete_boards"], 1)
        self.assertEqual(self.history.stats("high")["complete_boards"], 0)

    def test_interrupted_or_disabled_round_does_not_record(self):
        for recording in (True, False):
            with self.subTest(recording=recording):
                engine, app, adapter, events = self.engine(recording=recording)
                if recording:
                    async def stop_on_click(*args):
                        app.escape_pressed = True
                    adapter.click_tile.side_effect = stop_on_click
                with patch.object(self.history, "record", wraps=self.history.record) as record:
                    self.play(engine)
                record.assert_not_called()
                adapter.read_board.assert_not_called()
                self.assertFalse(self.path.exists())

    def test_stop_during_reveal_wait_does_not_capture_or_record(self):
        engine, app, adapter, events = self.engine()
        config = engine._get_round_config_for_strategy()
        engine._prepare_tile_selection(config)

        async def stop_during_wait(delay):
            app.escape_pressed = True

        with patch("game_engine.asyncio.sleep", new=AsyncMock(side_effect=stop_during_wait)), \
             patch.object(self.history, "record", wraps=self.history.record) as record:
            asyncio.run(engine._record_finished_board(config, "win"))
        adapter.read_board.assert_not_called()
        record.assert_not_called()

    def test_retries_partial_and_wrong_mine_frames_then_records_only_valid_board(self):
        engine, app, adapter, events = self.engine()
        valid = ["blue"] * 22 + ["red"] * 3
        adapter.read_board.side_effect = [[None] * 25, ["blue"] * 25, valid]
        with patch.object(self.history, "record", wraps=self.history.record) as record:
            self.play(engine)
        self.assertEqual(adapter.read_board.call_count, 3)
        record.assert_called_once()
        self.assertEqual(self.saved()[0]["colors"], valid)
        stats = self.history.stats("low")
        self.assertEqual((stats["complete_boards"], stats["partial_boards"]), (1, 0))

    def test_three_invalid_frames_are_saved_but_never_teach_safe_cells(self):
        engine, app, adapter, events = self.engine()
        adapter.read_board.side_effect = None
        adapter.read_board.return_value = ["blue"] * 25
        self.play(engine)
        self.assertEqual(adapter.read_board.call_count, 3)
        saved = self.saved()
        self.assertEqual(len(saved), 1)
        self.assertFalse(saved[0]["complete"])
        self.assertEqual(saved[0]["incomplete_reason"], "mine_count_mismatch")
        stats = self.history.stats("low")
        self.assertEqual((stats["complete_boards"], stats["partial_boards"]), (0, 1))
        self.assertTrue(all(tile["observations"] == 0 for tile in stats["tiles"]))

    def test_threshold_reached_by_current_board_only_applies_to_next_round(self):
        board = ["blue"] * 22 + ["red"] * 3
        for _ in range(MIN_COMPLETE_BOARDS - 1):
            self.history.record("low", board, expected_mines=3)
        engine, app, adapter, events = self.engine(use_history=True)
        with patch("game_engine.random.sample", return_value=list(range(25, 0, -1))), \
             patch.object(self.history, "order", return_value=list(range(1, 26))) as order:
            self.play(engine)
            self.assertIsNone(self.saved()[-1]["prospective"])
            self.assertEqual(self.history.stats("low")["evaluation"]["pairs"], 0)
            self.play(engine)
        self.assertEqual(order.call_count, 2)
        saved = self.saved()[-1]
        self.assertEqual(saved["prospective"]["history_order"], list(range(1, 26)))
        self.assertEqual(saved["prospective"]["random_order"], list(range(25, 0, -1)))
        self.assertEqual(self.history.stats("low")["evaluation"],
                         {"pairs": 1, "history_wins": 1, "random_wins": 0})
        self.assertNotEqual(self.saved()[-1]["round_id"], self.saved()[-2]["round_id"])

    def test_experimental_order_and_random_shadow_are_distinct_and_tiles_do_not_repeat(self):
        engine, app, adapter, events = self.engine(use_history=True)
        historical = list(range(1, 26))
        shadow = list(range(25, 0, -1))
        with patch.object(self.history, "order", return_value=historical), \
             patch.object(self.history, "stats", return_value={"ready": True}), \
             patch("game_engine.random.sample", return_value=shadow):
            engine._prepare_tile_selection(engine._get_round_config_for_strategy())
        self.assertEqual(engine.round_tile_order, historical)
        self.assertEqual(engine.tile_comparison["random_order"], shadow)
        self.assertIsNot(engine.tile_comparison["random_order"], engine.round_tile_order)
        self.assertEqual([engine.generate_random_tile() for _ in range(25)], historical)
        with self.assertRaises(ValueError):
            engine.generate_random_tile()
        app.tile_use_history_var = variable(False)
        with patch.object(self.history, "order", return_value=historical), \
             patch.object(self.history, "stats", return_value={"ready": True}), \
             patch("game_engine.random.sample", return_value=shadow):
            engine._prepare_tile_selection(engine._get_round_config_for_strategy())
        self.assertEqual(engine.round_tile_order, shadow)
        self.assertEqual(engine.tile_comparison["history_order"], historical)


if __name__ == "__main__":
    unittest.main()
