"""Settings persistence and validation for Gratta e Vinci."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any

from game_config import BETTING_MODES


class SettingsManager:
    """Load/save settings payloads with defaults and light schema checks."""

    def __init__(self) -> None:
        self._defaults = self._build_defaults()

    @staticmethod
    def _build_defaults() -> dict[str, Any]:
        return {
            "starting_cash": 2001.50,
            "target_win": 2100.0,
            "max_loss": 10.0,
            "max_rounds": 100,
            "max_picks": 3,
            "mode": "normal",
            "wait_selected": False,
            "grinding_mode": False,
            "grinding_range": 0.5,
            "grinding_p_random": False,
            "play_x": 2196,
            "play_y": 1616,
            "raise_x": 1900,
            "raise_y": 1740,
            "lower_x": 1519,
            "lower_y": 1740,
            "raise_diff_x": 0,
            "raise_diff_y": 0,
            "lower_diff_x": 0,
            "lower_diff_y": 0,
            "difficulty": "low",
            "custom_mode": [{"b": 0.1, "p": 2, "d": "low"}],
            "tiles": {},
            "betting_modes": {k: list(v) for k, v in BETTING_MODES.items()},
            "init_steps": [{"action": "set_bet_min"}],
            "sleep_play_or_collect": 1.0,
            "sleep_increase_bet": 1.0,
            "sleep_decrease_bet": 1.0,
            "sleep_decrease_bet_force": 0.05,
            "sleep_decrease_diff_force": 0.05,
            "sleep_set_difficulty": 0.5,
            "sleep_click_tile": 1.0,
            "sleep_after_play": 1.0,
            "sleep_after_tile_click": 1.0,
            "sleep_between_rounds": 1.0,
            "sleep_after_result": 2.0,
            "sleep_color_retry": 1.0,
            "color_tolerance": 50,
            "sleep_init_raise_diff": 0.4,
            "sleep_init_lower_diff": 0.4,
            "sleep_init_click": 0.3,
        }

    def merge_with_defaults(self, raw: dict[str, Any] | None) -> dict[str, Any]:
        payload = deepcopy(self._defaults)
        if isinstance(raw, dict):
            payload.update(raw)
        if not isinstance(payload.get("betting_modes"), dict):
            payload["betting_modes"] = {k: list(v) for k, v in BETTING_MODES.items()}
        if not isinstance(payload.get("custom_mode"), list):
            payload["custom_mode"] = [{"b": 0.1, "p": 2, "d": "low"}]
        if not isinstance(payload.get("tiles"), dict):
            payload["tiles"] = {}
        if not isinstance(payload.get("init_steps"), list):
            payload["init_steps"] = [{"action": "set_bet_min"}]
        return payload

    def validate(self, payload: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        mode = payload.get("mode")
        if mode not in {"normal", "medium", "high", "safe", "custom"}:
            errors.append("mode must be one of: normal, medium, high, safe, custom")
        difficulty = payload.get("difficulty")
        if difficulty not in {"low", "medium", "high"}:
            errors.append("difficulty must be one of: low, medium, high")
        if float(payload.get("starting_cash", 0)) <= 0:
            errors.append("starting_cash must be > 0")
        if int(payload.get("max_picks", 0)) not in (1, 2, 3, 4):
            errors.append("max_picks must be 1,2,3,4")
        try:
            tolerance = int(payload.get("color_tolerance", 50))
        except (TypeError, ValueError):
            tolerance = -1
        if tolerance < 1 or tolerance > 255:
            errors.append("color_tolerance must be in range 1..255")
        if not isinstance(payload.get("custom_mode"), list):
            errors.append("custom_mode must be a list")
        else:
            for idx, step in enumerate(payload["custom_mode"], 1):
                if not isinstance(step, dict):
                    errors.append(f"custom_mode[{idx}] must be an object")
                    continue
                try:
                    p = int(step.get("p"))
                    d = str(step.get("d", "")).lower()
                    _ = round(float(step.get("b")), 2)
                except (TypeError, ValueError):
                    errors.append(f"custom_mode[{idx}] has invalid numeric values")
                    continue
                if p not in (1, 2, 3, 4):
                    errors.append(f"custom_mode[{idx}].p must be 1..4")
                if d not in ("low", "medium", "high"):
                    errors.append(f"custom_mode[{idx}].d must be low/medium/high")
        return errors

    def load_settings(self, path: str) -> dict[str, Any]:
        raw: dict[str, Any] | None = None
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                raw = data if isinstance(data, dict) else None
        return self.merge_with_defaults(raw)

    def save_settings(self, path: str, payload: dict[str, Any]) -> None:
        normalized = self.merge_with_defaults(payload)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(normalized, f, indent=2)

    def save_custom_mode(self, path: str, custom_mode: list[dict[str, Any]], mode: str, difficulty: str) -> None:
        payload = self.load_settings(path)
        payload["custom_mode"] = custom_mode
        payload["mode"] = mode
        payload["difficulty"] = difficulty
        self.save_settings(path, payload)
