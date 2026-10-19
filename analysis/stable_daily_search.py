"""Research daily outcomes for three independent laptops; never plays online."""

from copy import deepcopy
from datetime import datetime, timezone
import argparse
import json
import math
from pathlib import Path
import secrets
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bulk_simulation import (_new_run, _play_run, _validate_snapshot,
                             summarize_runs, wilson_interval)
from game_config import BET_VALUES, TEST_MODE_MINE_CONFIG, WIN_MULTIPLIERS


def candidates(max_rounds=4000):
    base = {
        "mode": "custom", "starting_cash": 1000, "target_profit": 3,
        "max_loss": 50, "max_rounds": max_rounds, "difficulty": "medium",
        "max_picks": 6, "grinding_enabled": False, "grinding_range": 0,
        "p_random": False, "bet_values": list(BET_VALUES),
        "mine_config": deepcopy(TEST_MODE_MINE_CONFIG),
        "win_multipliers": deepcopy(WIN_MULTIPLIERS),
        "custom_mode": [{"b": .1, "p": 6, "d": "medium"}],
    }
    result = []
    for target in (1, 3, 7):
        for loss in (10, 50, 500):
            settings = deepcopy(base)
            settings.update(target_profit=target, max_loss=loss)
            settings["label"] = f"Medium 6, 0.10 EUR, target {target}, trailing stop {loss}"
            result.append(_validate_snapshot(settings))
    for target in (.1, .5):
        settings = deepcopy(base)
        settings.update(target_profit=target, label=f"Medium 6, 0.10 EUR, target {target}, trailing stop 50")
        result.append(_validate_snapshot(settings))
    for label, steps in (
        ("Medium 5, 0.10 EUR", [{"b": .1, "p": 5, "d": "medium"}]),
        ("Medium 6, bounded 0.10 -> 0.20 EUR", [{"b": .1, "p": 6, "d": "medium"},
                                              {"b": .2, "p": 6, "d": "medium"}]),
        ("Mixed Medium 5 -> 6, 0.10 EUR", [{"b": .1, "p": 5, "d": "medium"},
                                         {"b": .1, "p": 6, "d": "medium"}]),
    ):
        settings = deepcopy(base)
        settings.update(custom_mode=steps, label=label + ", target 3, trailing stop 50")
        result.append(_validate_snapshot(settings))
    return result


def timing_estimate(settings, pauses):
    seconds = []
    for step in settings["custom_mode"]:
        picks, mines = step["p"], settings["mine_config"][step["d"]]
        safe = 25 - mines
        clicked = sum(math.comb(safe, j) / math.comb(25, j) for j in range(picks))
        win = math.comb(safe, picks) / math.comb(25, picks)
        tile_pause = sum(pauses.get(key, fallback) for key, fallback in (
            ("sleep_after_play", .5), ("sleep_click_tile", 1), ("sleep_after_tile_click", .5)))
        play = pauses.get("sleep_play_or_collect", 1)
        seconds.append(clicked * tile_pause + play * (1 + win)
                       + (1 - win) * pauses.get("sleep_after_result", 1)
                       + pauses.get("sleep_between_rounds", 1)
                       + pauses.get("tile_reveal_delay", 1))
    return {
        "estimated_seconds_per_round": max(seconds),
        "hours_at_round_limit": settings["max_rounds"] * max(seconds) / 3600,
        "actual_speed_verified": False,
        "method": "Expected clicked tiles until first mine; slowest configured step, "
                  "including one 1-second board reveal. Excludes retries, network, setup "
                  "and bet-change delays; approximate, not a measured daily deadline.",
    }


def evaluate(settings, days, pauses=None, progress=None, keep_days=False):
    if isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise ValueError("days must be a positive integer")
    settings = _validate_snapshot(settings)
    timing = timing_estimate(settings, pauses or {})
    streams = secrets.randbits(128)
    laptops, aggregate, rows = [[], [], []], [], []
    for day in range(1, days + 1):
        runs = []
        for laptop in range(3):
            run = _new_run(day, settings["starting_cash"], [])
            _play_run(settings, run, [], lambda: False, lambda: None,
                      f"{streams}:day:{day}:laptop:{laptop}")
            laptops[laptop].append(run)
            runs.append(run)
        # Daily profits are added in cents; path drawdowns cannot be combined.
        group = _new_run(day, 3 * settings["starting_cash"], [])
        group.update(profit=sum(round(r["profit"] * 100) for r in runs) / 100,
                     wagered=round(sum(r["wagered"] for r in runs), 2),
                     rounds=sum(r["rounds"] for r in runs), status="period_end")
        aggregate.append(group)
        if keep_days:
            rows.append({"day": day, "profits": [r["profit"] for r in runs],
                         "rounds": [r["rounds"] for r in runs],
                         "statuses": [r["status"] for r in runs]})
        if progress and day % 500 == 0:
            progress(day, days)
    group_summary = summarize_runs(aggregate)
    group_summary.pop("max_drawdown")
    negatives = sum(r["profit"] < 0 for r in aggregate)
    zeroes = sum(r["profit"] == 0 for r in aggregate)
    group_summary.update(negative_days=negatives, zero_days=zeroes,
                         nonpositive_rate=100 * (negatives + zeroes) / days,
                         negative_ci_low=wilson_interval(negatives, days)[0],
                         negative_ci_high=wilson_interval(negatives, days)[1])
    summaries = []
    for runs in laptops:
        summary = summarize_runs(runs)
        summary["max_rounds_rate"] = 100 * sum(r["status"] == "max_rounds" for r in runs) / days
        summary["estimated_avg_hours"] = summary["avg_rounds"] * timing["estimated_seconds_per_round"] / 3600
        summary["estimated_over_12h_rate"] = 100 * sum(
            r["rounds"] * timing["estimated_seconds_per_round"] > 43200 for r in runs) / days
        summaries.append(summary)
    result = {"settings": settings, "days": days, "group": group_summary,
              "laptops": summaries, "timing": timing}
    if keep_days:
        result["daily_results"] = rows
    return result


def best_screening(results):
    return min(results, key=lambda r: (r["group"]["negative_rate"], -r["group"]["avg_profit"]))


def evaluate_collective(settings, days, pauses=None, progress=None):
    """Ideal settled global stop; IID interleaving has the same aggregate law."""
    if isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise ValueError("days must be a positive integer")
    settings = deepcopy(settings)
    settings.update(starting_cash=3 * settings["starting_cash"],
                    max_rounds=3 * settings["max_rounds"], target_profit=3, max_loss=500,
                    max_picks=6,
                    label="Collective settled stop: Medium 6, 0.10 EUR, total target 3 EUR")
    settings["custom_mode"] = [{"b": .1, "p": 6, "d": "medium"}]
    settings = _validate_snapshot(settings)
    timing = timing_estimate(settings, pauses or {})
    runs, streams = [], secrets.randbits(128)
    for day in range(1, days + 1):
        run = _new_run(day, settings["starting_cash"], [])
        _play_run(settings, run, [], lambda: False, lambda: None, f"{streams}:global:{day}")
        runs.append(run)
        if progress and day % 500 == 0:
            progress(day, days)
    summary = summarize_runs(runs)
    negatives = sum(r["profit"] < 0 for r in runs)
    zeroes = sum(r["profit"] == 0 for r in runs)
    summary.update(negative_days=negatives, zero_days=zeroes,
                   nonpositive_rate=100 * (negatives + zeroes) / days,
                   negative_ci_low=wilson_interval(negatives, days)[0],
                   negative_ci_high=wilson_interval(negatives, days)[1],
                   max_rounds_rate=100 * sum(r["status"] == "max_rounds" for r in runs) / days)
    return {
        "settings": settings, "days": days, "group": summary,
        "estimated_avg_hours_per_pc_parallel": summary["avg_rounds"] / 3 * timing["estimated_seconds_per_round"] / 3600,
        "requires_new_coordinator": True, "implemented_in_real_bot": False,
        "method": "Ideal aggregate financial model; rounds settle before checking the "
                  "global stop. Independent IID laptop outcomes interleaved evenly have "
                  "the same distribution. This does not model pending simultaneous bets "
                  "or per-PC individual balances and is not a live speed measurement.",
        "daily_results": [{"day": r["index"], "profit": r["profit"], "rounds": r["rounds"],
                           "status": r["status"]} for r in runs],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen-days", type=int, default=500)
    parser.add_argument("--validation-days", type=int, default=10000)
    parser.add_argument("--max-rounds", type=int, default=4000)
    args = parser.parse_args()
    if min(args.screen_days, args.validation_days, args.max_rounds) < 1:
        parser.error("counts must be positive")
    pauses = json.loads((ROOT / "gratta_settings.json").read_text(encoding="utf-8"))
    started = time.monotonic()
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "synthetic_uniform_independent_boards",
        "confirmed_rules": {"medium_mines": 6, "board_size": 25,
                            "total_multipliers": {4: 3.2, 5: 4.6, 6: 6.8}},
        "costs_included": False, "real_history_used": False,
        "method": "Each day starts with 1000 EUR per laptop; three laptops share a "
                  "configuration but have independent game streams. Search then freeze "
                  "the candidate and validate on new streams; no guaranteed profit.",
        "selection": "Lowest aggregate negative-day rate, then highest mean profit; "
                     "500-day screening is noisy and does not prove global optimality.",
        "screening": [],
    }
    for settings in candidates(args.max_rounds):
        result = evaluate(settings, args.screen_days, pauses)
        report["screening"].append(result)
        print(settings["label"], "negative %:", result["group"]["negative_rate"],
              "mean profit:", result["group"]["avg_profit"], flush=True)
    chosen = best_screening(report["screening"])
    report["frozen_settings"] = chosen["settings"]
    output_dir = ROOT / "bulk_results"
    output_dir.mkdir(exist_ok=True)
    path = output_dir / f"stable_daily_search_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print("Frozen candidate:", chosen["settings"]["label"], "Report:", path, flush=True)
    report["validation"] = evaluate(chosen["settings"], args.validation_days, pauses,
        progress=lambda done, total: print(f"Validation {done}/{total}", flush=True), keep_days=True)
    report["collective_stop_comparison"] = evaluate_collective(chosen["settings"], args.validation_days, pauses,
        progress=lambda done, total: print(f"Collective comparison {done}/{total}", flush=True))
    report["elapsed_seconds"] = time.monotonic() - started
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
    print("Validation:", json.dumps(report["validation"]["group"]), "Report:", path, flush=True)
    print("Collective stop:", json.dumps(report["collective_stop_comparison"]["group"]), flush=True)


if __name__ == "__main__":
    main()
