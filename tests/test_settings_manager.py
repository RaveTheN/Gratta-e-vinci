"""Validate available tile counts before settings can replace an existing file."""

from pathlib import Path
import tempfile
import unittest

from settings_manager import SettingsManager


class SettingsManagerTest(unittest.TestCase):
    def setUp(self):
        self.manager = SettingsManager()

    def test_medium_six_to_eight_cells_can_be_saved_and_reloaded(self):
        for picks in (6, 7, 8):
            with self.subTest(picks=picks):
                settings = self.manager.merge_with_defaults({"difficulty": "medium", "max_picks": picks})
                self.assertEqual(self.manager.validate(settings), [])
                with tempfile.TemporaryDirectory() as directory:
                    path = str(Path(directory) / "settings.json")
                    self.manager.save_settings(path, settings)
                    self.assertEqual(self.manager.load_settings(path)["max_picks"], picks)
                settings.update(mode="custom", difficulty="low",
                                custom_mode=[{"b": 0.1, "p": picks, "d": "medium"}])
                self.assertEqual(self.manager.validate(settings), [])

    def test_unsupported_combinations_cannot_replace_saved_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("original", encoding="utf-8")
            for difficulty, picks in (("low", 5), ("high", 6), ("low", 8), ("high", 8)):
                for mode in ("normal", "custom"):
                    settings = self.manager.merge_with_defaults({
                        "mode": mode, "difficulty": difficulty, "max_picks": picks,
                        "custom_mode": [{"b": 0.1, "p": picks, "d": difficulty}],
                    })
                    with self.subTest(difficulty=difficulty, picks=picks, mode=mode), \
                         self.assertRaisesRegex(ValueError, "multiplier"):
                        self.manager.save_settings(str(path), settings)
                    self.assertEqual(path.read_text(encoding="utf-8"), "original")

    def test_invalid_tile_counts_are_rejected(self):
        for picks in (True, 1.5, None, "invalid", 9):
            settings = self.manager.merge_with_defaults({"max_picks": picks})
            with self.subTest(picks=picks):
                self.assertTrue(self.manager.validate(settings))
        settings = self.manager.merge_with_defaults({
            "mode": "custom", "custom_mode": [{"b": 0.1, "p": 9, "d": "medium"}],
        })
        self.assertTrue(self.manager.validate(settings))


if __name__ == "__main__":
    unittest.main()
