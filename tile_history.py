"""Observed boards and an experimental tile order, separate for each difficulty."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import threading

from game_config import MAX_PICKS


MIN_COMPLETE_BOARDS = 100
DIFFICULTIES = ("low", "medium", "high")


class TileHistory:
    def __init__(self, path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._round_ids = set()
        self._needs_newline = False
        self.invalid_records = 0
        self._data = {
            difficulty: {
                "complete_boards": 0, "partial_boards": 0, "reds": [0] * 25,
                "evaluation": {"pairs": 0, "history_wins": 0, "random_wins": 0},
            }
            for difficulty in DIFFICULTIES
        }
        if self.path.exists():
            with self.path.open("rb") as stream:
                for line in stream:
                    self._needs_newline = not line.endswith(b"\n")
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line.decode("utf-8"))
                        if not isinstance(record, dict):
                            raise ValueError("A record must be an object")
                        values = self._validate(
                            record.get("difficulty"), record.get("colors"),
                            record.get("outcome"), record.get("prospective"),
                            record.get("round_id"), record.get("expected_mines"),
                        )
                        datetime.fromisoformat(record["timestamp"])
                        if values["round_id"] in self._round_ids:
                            raise ValueError("Duplicate round")
                    except (ValueError, TypeError, KeyError, UnicodeError):
                        self.invalid_records += 1
                        continue
                    self._apply(values)

    @staticmethod
    def _validate(difficulty, colors, outcome, prospective, round_id, expected_mines):
        if difficulty not in DIFFICULTIES:
            raise ValueError("Difficulty must be low, medium or high")
        if not isinstance(colors, (list, tuple)) or len(colors) > 25:
            raise ValueError("Colors must contain at most 25 entries")
        if any(color not in ("blue", "red", None) for color in colors):
            raise ValueError("A color must be blue, red or None")
        if outcome not in (None, "win", "loss"):
            raise ValueError("Outcome must be win, loss or None")
        if round_id is not None and (not isinstance(round_id, str) or not round_id.strip()):
            raise ValueError("Round identifier must be a nonempty string")
        if expected_mines is not None and (type(expected_mines) is not int or not 0 <= expected_mines <= 25):
            raise ValueError("Expected mines must be an integer between 0 and 25")
        if prospective is not None:
            if not isinstance(prospective, dict):
                raise ValueError("Prospective choices must be an object")
            picks = prospective.get("picks")
            if type(picks) is not int or not 1 <= picks <= MAX_PICKS:
                raise ValueError(f"Prospective picks must be between 1 and {MAX_PICKS}")
            orders = {}
            for name in ("history_order", "random_order"):
                order = prospective.get(name)
                if (not isinstance(order, (list, tuple)) or len(order) != 25
                        or any(type(tile) is not int for tile in order)
                        or set(order) != set(range(1, 26))):
                    raise ValueError("An order must be a permutation of tiles 1 to 25")
                orders[name] = list(order)
            prospective = {"picks": picks, **orders}
        colors = list(colors) + [None] * (25 - len(colors))
        reason = None
        if None in colors:
            reason = "unknown_cells"
        elif expected_mines is not None and colors.count("red") != expected_mines:
            reason = "mine_count_mismatch"
        return {
            "difficulty": difficulty, "colors": colors,
            "outcome": outcome, "prospective": prospective, "round_id": round_id,
            "expected_mines": expected_mines, "complete": reason is None,
            "incomplete_reason": reason,
        }

    def _apply(self, record):
        data = self._data[record["difficulty"]]
        colors = record["colors"]
        complete = record["complete"]
        prospective = record["prospective"]
        # Score the order made before this board; the current board is not training data yet.
        if complete and prospective and data["complete_boards"] >= MIN_COMPLETE_BOARDS:
            evaluation = data["evaluation"]
            evaluation["pairs"] += 1
            picks = prospective["picks"]
            for name in ("history", "random"):
                order = prospective[f"{name}_order"][:picks]
                evaluation[f"{name}_wins"] += int(all(colors[tile - 1] == "blue" for tile in order))
        if complete:
            data["complete_boards"] += 1
            for index, color in enumerate(colors):
                data["reds"][index] += color == "red"
        else:
            data["partial_boards"] += 1
        if record["round_id"] is not None:
            self._round_ids.add(record["round_id"])

    def record(self, difficulty, colors, outcome=None, prospective=None, round_id=None,
               expected_mines=None):
        record = self._validate(difficulty, colors, outcome, prospective, round_id, expected_mines)
        record["timestamp"] = datetime.now(timezone.utc).isoformat()
        with self._lock:
            if round_id is not None and round_id in self._round_ids:
                return False
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Preserve a truncated final line rather than overwriting old observations.
            prefix = "\n" if self._needs_newline else ""
            with self.path.open("a", encoding="utf-8", newline="\n") as stream:
                stream.write(prefix + json.dumps(record, ensure_ascii=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            self._needs_newline = False
            self._apply(record)
        return True

    def stats(self, difficulty):
        if difficulty not in DIFFICULTIES:
            raise ValueError("Difficulty must be low, medium or high")
        with self._lock:
            data = self._data[difficulty]
            complete = data["complete_boards"]
            return {
                "complete_boards": complete, "partial_boards": data["partial_boards"],
                "ready": complete >= MIN_COMPLETE_BOARDS,
                "invalid_records": self.invalid_records,
                "tiles": [
                    {"tile": index + 1, "red_count": reds, "observations": complete,
                     "red_rate": reds / complete if complete else None}
                    for index, reds in enumerate(data["reds"])
                ],
                "evaluation": dict(data["evaluation"]),
            }

    def order(self, difficulty, rng=None):
        if difficulty not in DIFFICULTIES:
            raise ValueError("Difficulty must be low, medium or high")
        order = list(range(1, 26))
        (rng if rng is not None else random).shuffle(order)
        with self._lock:
            data = self._data[difficulty]
            complete = data["complete_boards"]
            if complete >= MIN_COMPLETE_BOARDS:
                order.sort(key=lambda tile: (data["reds"][tile - 1] + 1) / (complete + 2))
        return order
