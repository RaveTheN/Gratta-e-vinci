"""History never learns from hidden cells or from the board it is about to play."""

import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from tile_history import MIN_COMPLETE_BOARDS, TileHistory


class TileHistoryTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "history" / "tiles.jsonl"
        self.history = TileHistory(self.path)

    def train(self, difficulty="low", reds=(1,), count=MIN_COMPLETE_BOARDS):
        colors = ["red" if tile in reds else "blue" for tile in range(1, 26)]
        for _ in range(count):
            self.history.record(difficulty, colors)

    def test_partial_boards_do_not_teach_that_unknown_cells_are_safe(self):
        self.history.record("low", ["red", "blue"])
        stats = self.history.stats("low")
        self.assertEqual((stats["complete_boards"], stats["partial_boards"]), (0, 1))
        self.assertTrue(all(tile["observations"] == 0 for tile in stats["tiles"]))
        self.assertTrue(all(tile["red_rate"] is None for tile in stats["tiles"]))
        self.history.record("low", ["red"] + ["blue"] * 24)
        stats = self.history.stats("low")
        self.assertEqual(stats["tiles"][0]["red_rate"], 1)
        self.assertEqual(stats["tiles"][1]["red_rate"], 0)
        saved = json.loads(self.path.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(saved["colors"], ["red", "blue"] + [None] * 23)

    def test_difficulties_are_separate_and_start_with_random_order(self):
        self.train(count=MIN_COMPLETE_BOARDS - 1)
        expected = list(range(1, 26))
        random.Random(17).shuffle(expected)
        self.assertEqual(self.history.order("low", random.Random(17)), expected)
        self.history.record("low", ["red"] + ["blue"] * 24)
        self.assertEqual(self.history.order("low", random.Random(17))[-1], 1)
        self.assertEqual(self.history.order("medium", random.Random(17)), expected)
        self.assertTrue(self.history.stats("low")["ready"])
        self.assertFalse(self.history.stats("medium")["ready"])
        first = self.history.order("low", random.Random(1))
        second = self.history.order("low", random.Random(2))
        self.assertNotEqual(first[:-1], second[:-1])
        self.assertEqual(set(first), set(range(1, 26)))

    def test_prospective_evaluation_uses_orders_from_before_new_board(self):
        self.train(reds=(1,))
        history_order = self.history.order("low", random.Random(5))
        self.assertNotEqual(history_order[0], 1)
        prospective = {"picks": 1, "history_order": history_order,
                       "random_order": list(range(1, 26))}
        self.history.record("low", ["red"] + ["blue"] * 24,
                            outcome="win", prospective=prospective)
        self.assertEqual(self.history.stats("low")["evaluation"],
                         {"pairs": 1, "history_wins": 1, "random_wins": 0})
        self.history.record("low", ["blue"], prospective=prospective)
        self.assertEqual(self.history.stats("low")["evaluation"]["pairs"], 1)
        # The same precomputed order can lose on a future board despite previous frequencies.
        colors = ["blue"] * 25
        colors[history_order[0] - 1] = "red"
        self.history.record("low", colors, prospective=prospective)
        self.assertEqual(self.history.stats("low")["evaluation"],
                         {"pairs": 2, "history_wins": 1, "random_wins": 1})

    def test_warmup_is_not_counted_as_evidence_for_history(self):
        prospective = {"picks": 4, "history_order": list(range(1, 26)),
                       "random_order": list(range(25, 0, -1))}
        for _ in range(MIN_COMPLETE_BOARDS):
            self.history.record("high", ["blue"] * 25, prospective=prospective)
        self.assertEqual(self.history.stats("high")["evaluation"]["pairs"], 0)
        self.history.record("high", ["blue"] * 25, prospective=prospective)
        self.assertEqual(self.history.stats("high")["evaluation"]["pairs"], 1)

    def test_unexpected_mine_count_is_saved_without_learning_or_evaluation(self):
        self.train(reds=(1, 2, 3))
        prospective = {"picks": 1, "history_order": self.history.order("low"),
                       "random_order": list(range(1, 26))}
        self.history.record("low", ["blue"] * 25, expected_mines=3, prospective=prospective)
        stats = self.history.stats("low")
        self.assertEqual((stats["complete_boards"], stats["partial_boards"]), (100, 1))
        self.assertEqual(stats["evaluation"]["pairs"], 0)
        self.assertEqual(stats["tiles"][0]["red_count"], 100)
        saved = json.loads(self.path.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(saved["colors"], ["blue"] * 25)
        self.assertFalse(saved["complete"])
        self.assertEqual(saved["incomplete_reason"], "mine_count_mismatch")
        restored = TileHistory(self.path)
        self.assertEqual(restored.stats("low"), stats)
        self.history.record("low", ["red"] * 3 + ["blue"] * 22, expected_mines=3)
        self.assertEqual(self.history.stats("low")["complete_boards"], 101)

    def test_persistence_duplicate_rounds_and_caller_mutations(self):
        colors = ["red"] + ["blue"] * 24
        self.assertTrue(self.history.record("medium", colors, "loss", round_id="match-1"))
        colors[0] = "blue"
        self.assertFalse(self.history.record("medium", colors, round_id="match-1"))
        restored = TileHistory(self.path)
        self.assertEqual(restored.stats("medium"), self.history.stats("medium"))
        self.assertFalse(restored.record("medium", colors, round_id="match-1"))
        stats = restored.stats("medium")
        stats["tiles"][0]["red_count"] = 999
        stats["evaluation"]["pairs"] = 999
        self.assertEqual(restored.stats("medium")["tiles"][0]["red_count"], 1)
        self.assertEqual(restored.stats("medium")["evaluation"]["pairs"], 0)

    def test_invalid_or_truncated_lines_are_retained_and_new_records_survive(self):
        self.history.record("low", ["blue"] * 25)
        original = self.path.read_bytes()
        with self.path.open("ab") as stream:
            stream.write(b'{"broken": true}\n\xff\n{"colors": [')
        corrupt = self.path.read_bytes()
        restored = TileHistory(self.path)
        self.assertEqual(restored.stats("low")["complete_boards"], 1)
        self.assertEqual(restored.stats("low")["invalid_records"], 3)
        restored.record("low", ["red"] * 25)
        self.assertTrue(self.path.read_bytes().startswith(corrupt))
        self.assertTrue(corrupt.startswith(original))
        reloaded = TileHistory(self.path)
        self.assertEqual(reloaded.stats("low")["complete_boards"], 2)
        self.assertEqual(reloaded.stats("low")["invalid_records"], 3)

    def test_failed_durable_write_does_not_update_observations(self):
        with patch("tile_history.os.fsync", side_effect=OSError("disk error")):
            with self.assertRaisesRegex(OSError, "disk error"):
                self.history.record("low", ["blue"] * 25)
        self.assertEqual(self.history.stats("low")["complete_boards"], 0)

    def test_invalid_inputs_are_rejected_before_file_is_created(self):
        prospective = {"picks": 1, "history_order": list(range(1, 26)),
                       "random_order": list(range(1, 26))}
        cases = [
            ("invalid", ["blue"] * 25, {}),
            ("low", ["blue"] * 26, {}),
            ("low", ["unknown"], {}),
            ("low", {1: "blue"}, {}),
            ("low", ["blue"], {"outcome": True}),
            ("low", ["blue"], {"round_id": ""}),
            ("low", ["blue"], {"expected_mines": True}),
            ("low", ["blue"], {"expected_mines": -1}),
            ("low", ["blue"], {"expected_mines": 26}),
            ("low", ["blue"], {"prospective": {**prospective, "picks": True}}),
            ("low", ["blue"], {"prospective": {**prospective, "picks": 9}}),
            ("low", ["blue"], {"prospective": {**prospective, "history_order": [1] * 25}}),
            ("low", ["blue"], {"prospective": {**prospective, "history_order": [True] + list(range(2, 26))}}),
        ]
        for difficulty, colors, kwargs in cases:
            with self.subTest(kwargs=kwargs, colors=colors):
                with self.assertRaises(ValueError):
                    self.history.record(difficulty, colors, **kwargs)
        self.assertFalse(self.path.exists())
        with self.assertRaises(ValueError):
            self.history.stats("invalid")
        with self.assertRaises(ValueError):
            self.history.order("invalid")

    def test_eight_cell_prediction_scores_the_eighth_cell_and_survives_reload(self):
        for _ in range(MIN_COMPLETE_BOARDS):
            self.history.record("medium", ["blue"] * 25)
        colors = ["blue"] * 25
        colors[7] = "red"
        prospective = {"picks": 8, "history_order": list(range(1, 26)),
                       "random_order": list(range(25, 0, -1))}
        self.history.record("medium", colors[:8], prospective=prospective)
        self.assertEqual(self.history.stats("medium")["evaluation"]["pairs"], 0)
        self.history.record("medium", colors, prospective=prospective)
        evaluation = self.history.stats("medium")["evaluation"]
        self.assertEqual(evaluation, {"pairs": 1, "history_wins": 0, "random_wins": 1})
        self.assertEqual(TileHistory(self.path).stats("medium")["evaluation"], evaluation)


if __name__ == "__main__":
    unittest.main()
