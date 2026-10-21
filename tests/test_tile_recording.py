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


if __name__ == "__main__":
    unittest.main()
