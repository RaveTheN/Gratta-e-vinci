"""Compare tile history vs random selection using the app's financial engine.

Research only: synthetic independent boards, never reads/writes real tile history.
Run from project root: .venv\Scripts\python.exe analysis/tile_bulk_experiment.py
"""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import secrets
from statistics import mean, stdev
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bulk_simulation import _new_run, _play_run, _validate_snapshot, summarize_runs
from tile_history import MIN_COMPLETE_BOARDS


class SyntheticTileOutcomes:
    def __init__(self, mine_config, warmup_counts, history_enabled, world, selection):
        self.difficulties = {mines: difficulty for difficulty, mines in mine_config.items()}
        if len(self.difficulties) != len(mine_config):
            raise ValueError("This experiment requires distinct mine counts per difficulty")
        self.counts = deepcopy(warmup_counts)
        self.history_enabled = history_enabled
        self.world = random.Random(world)
        self.selection = random.Random(selection)
        self.rounds = 0

    def __call__(self, mines, picks):
        difficulty = self.difficulties[mines]
        counts = self.counts[difficulty]
        # This is the same ranking as TileHistory.order: a common smoothing
        # denominator preserves the ordering, with random ties from the shuffle.
        order = list(range(25))
        self.selection.shuffle(order)
        if self.history_enabled:
            order.sort(key=counts.__getitem__)
        selected = order[:picks]
        # The prediction is fixed before generating/observing this new board.
        board = self.world.sample(range(25), 25)
        reds = set(board[:mines])
        hit = any(tile in reds for tile in selected)
        for tile in reds:
            counts[tile] += 1
        self.rounds += 1
        # 0 or 1 makes the existing engine resolve this board's actual tile outcome.
        return 0.0 if hit else 1.0


def make_warmup(mine_config, rng):
    counts = {difficulty: [0] * 25 for difficulty in mine_config}
    for difficulty, mines in mine_config.items():
        for _ in range(MIN_COMPLETE_BOARDS):
            for tile in rng.sample(range(25), mines):
                counts[difficulty][tile] += 1
    return counts


def compare_settings(settings_list, runs_per_laptop=5000, progress=None):
    master = secrets.randbits(128)
    started = time.monotonic()
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "synthetic_uniform_independent_boards",
        "real_history_available": False,
        "requested_runs_per_laptop_and_policy": runs_per_laptop,
        "warmup_boards_per_difficulty": MIN_COMPLETE_BOARDS,
        "method": "Fresh simulated history per replica; orders fixed before each board; paired worlds per laptop/replica, independent worlds between laptops; app betting/grinding/stop logic unchanged.",
        "costs_included": False,
        "configurations": [],
    }
    for laptop, original in enumerate(settings_list, 1):
        settings = _validate_snapshot(original)
        policies = {"random": [], "history": []}
        for index in range(1, runs_per_laptop + 1):
            key = f"{master}:laptop:{laptop}:replica:{index}"
            warmup = make_warmup(settings["mine_config"], random.Random(key + ":warmup"))
            for policy in policies:
                outcomes = SyntheticTileOutcomes(settings["mine_config"], warmup,
                                                 policy == "history", key + ":world", key + ":selection:" + policy)
                run = _new_run(index, settings["starting_cash"], [])
                # Only resolve tile outcomes differently; the production financial
                # engine still applies every bet, payout, grinding transition and stop.
                with patch("bulk_simulation.win_probability", side_effect=outcomes):
                    _play_run(settings, run, [], lambda: False, lambda: None, key + ":strategy")
                policies[policy].append(run)
            if progress and index % 1000 == 0:
                progress(laptop, index, runs_per_laptop)
        differences = [h["profit"] - r["profit"] for h, r in zip(policies["history"], policies["random"])]
        average = mean(differences)
        error = 1.959963984540054 * stdev(differences) / len(differences)**.5 if len(differences) > 1 else None
        report["configurations"].append({
            "label": settings.get("label", f"Laptop {laptop}"), "settings": settings,
            "random": summarize_runs(policies["random"]), "history": summarize_runs(policies["history"]),
            "mean_profit_difference": average,
            "difference_ci_low": average - error if error is not None else None,
            "difference_ci_high": average + error if error is not None else None,
        })
    report["elapsed_seconds"] = time.monotonic() - started
    return report


if __name__ == "__main__":
    source = ROOT / "bulk_results" / "bulk_test_20260919_214240_983285.json"
    batch = json.loads(source.read_text(encoding="utf-8"))
    configurations = [c["settings"] for c in batch["configurations"]]
    result = compare_settings(configurations, progress=lambda laptop, done, total:
                              print(f"Laptop {laptop}: {done}/{total} paired sessions", flush=True))
    result["settings_source"] = source.name
    path = ROOT / "bulk_results" / f"tile_bulk_comparison_{datetime.now(timezone.utc):%Y%m%d_%H%M%S_%f}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2), encoding="utf-8")
    print(path)
    for config in result["configurations"]:
        print(json.dumps({"laptop": config["label"], "random_mean": config["random"]["avg_profit"],
                          "history_mean": config["history"]["avg_profit"],
                          "difference_ci": [config["difference_ci_low"], config["difference_ci_high"]]}))
