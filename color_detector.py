"""Pixel read and color classification helpers."""

from __future__ import annotations

from typing import Any

import pyautogui
from PIL import ImageGrab

from game_config import COLOR_TOLERANCE, TARGET_BLUE, TARGET_RED


class ColorDetector:
    def __init__(
        self,
        target_blue: dict[str, int] | None = None,
        target_red: dict[str, int] | None = None,
        tolerance: int = COLOR_TOLERANCE,
    ) -> None:
        self.target_blue = dict(target_blue or TARGET_BLUE)
        self.target_red = dict(target_red or TARGET_RED)
        self.tolerance = tolerance

    def read_board(self, points: dict[int, Any]) -> list[str | None]:
        """Read the entire revealed board from one frame, avoiding mixed animations."""
        if set(points) != set(range(1, 26)):
            raise ValueError("Servono le coordinate di tutte le 25 celle")
        coordinates = [(int(points[tile].x), int(points[tile].y)) for tile in range(1, 26)]
        if len(set(coordinates)) != 25:
            raise ValueError("Le 25 celle devono avere coordinate distinte")
        width, height = pyautogui.size()
        if any(x < 0 or y < 0 or x >= width or y >= height for x, y in coordinates):
            raise ValueError("Una o più celle sono fuori dallo schermo")
        left, top = min(x for x, _ in coordinates), min(y for _, y in coordinates)
        right, bottom = max(x for x, _ in coordinates) + 1, max(y for _, y in coordinates) + 1
        screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
        colors = []
        for x, y in coordinates:
            pixel = screenshot.getpixel((x - left, y - top))
            color = dict(zip(("r", "g", "b"), pixel[:3]))
            blue, red = self.is_color_in_range_blue(color), self.is_color_in_range_red(color)
            colors.append("blue" if blue and not red else "red" if red and not blue else None)
        return colors

    def read_color_at_point(self, point: Any) -> dict[str, int]:
        x = int(point.x)
        y = int(point.y)
        screen_width, screen_height = pyautogui.size()
        if x < 0 or y < 0 or x >= screen_width or y >= screen_height:
            raise ValueError(f"Point ({x}, {y}) outside screen bounds {screen_width}x{screen_height}")
        screenshot = ImageGrab.grab(bbox=(x, y, x + 1, y + 1))
        pixel_color = screenshot.getpixel((0, 0))
        if len(pixel_color) == 3:
            r, g, b = pixel_color
            a = 255
        else:
            r, g, b, a = pixel_color
        return {"r": r, "g": g, "b": b, "a": a}

    def is_color_in_range_blue(self, color: dict[str, int], target_color: dict[str, int] | None = None, tolerance: int | None = None) -> bool:
        target = target_color or self.target_blue
        tol = self.tolerance if tolerance is None else tolerance
        return (
            abs(color["r"] - target["r"]) <= tol
            and abs(color["g"] - target["g"]) <= tol
            and abs(color["b"] - target["b"]) <= tol
        )

    def is_color_in_range_red(self, color: dict[str, int], target_color: dict[str, int] | None = None, tolerance: int | None = None) -> bool:
        target = target_color or self.target_red
        tol = self.tolerance if tolerance is None else tolerance
        return (
            abs(color["r"] - target["r"]) <= tol
            and abs(color["g"] - target["g"]) <= tol
            and abs(color["b"] - target["b"]) <= tol
        )
