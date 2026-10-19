"""Independently validate the CDF sampler using complete shuffled 25-cell boards."""

from collections import Counter
from datetime import datetime, timezone
import argparse
import json
import math
from pathlib import Path
import random
import secrets
from statistics import NormalDist, mean, stdev, variance
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis.collective_exact import WIN_PROBABILITY, collective_distribution
from analysis.collective_parallel import sample_round, simulate_day, summarize, timing_from_settings
from bulk_simulation import wilson_interval

SELECTED_TILES = (0, 1, 2, 3, 4, 5)
OUTCOMES = [(opened, False) for opened in range(1, 7)] + [(6, True)]


def full_board_round(rng):
    # The six unique selections are fixed before drawing this fresh board.
    board = [True] * 6 + [False] * 19
    rng.shuffle(board)
    for opened, tile in enumerate(SELECTED_TILES, 1):
        if board[tile]:
            return opened, False
    return 6, True


def simultaneous_wilson(successes, total, categories=7):
    z = NormalDist().inv_cdf(1 - .05 / (2 * categories))
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0, center - spread), min(1, center + spread)


def validate_boards(boards=500000):
    if type(boards) is not int or boards < 1:
        raise ValueError("boards must be a positive integer")
    master = secrets.randbits(128)
    rngs = [random.Random(f"{master}:board-validation:laptop:{pc}") for pc in range(4)]
    counts = Counter(full_board_round(rngs[index % 4]) for index in range(boards))
    survival = [math.comb(19, j) / math.comb(25, j) for j in range(7)]
    probabilities = [survival[j - 1] - survival[j] for j in range(1, 7)] + [survival[6]]
    rows = []
    for outcome, expected in zip(OUTCOMES, probabilities):
        low, high = simultaneous_wilson(counts[outcome], boards)
        rows.append({"opened": outcome[0], "won": outcome[1], "count": counts[outcome],
                     "expected_probability": expected, "observed_probability": counts[outcome] / boards,
                     "joint95_interval_low": low, "joint95_interval_high": high,
                     "expected_inside_interval": low <= expected <= high})
    return {"boards": boards, "independent_laptop_streams": 4,
            "method": "Fresh 25-cell board, 6 red cells, full shuffle, six fixed unique "
                      "selections chosen before the board. Bonferroni-Wilson intervals "
                      "give approximate 95% simultaneous coverage across seven outcomes.",
            "outcomes": rows, "all_expected_inside_intervals": all(r["expected_inside_interval"] for r in rows)}


def day_statistics(days):
    summary = summarize(days)
    low, high = wilson_interval(summary["negative_days"], len(days))
    profits = [r["profit"] for r in days]
    error = 1.959963984540054 * stdev(profits) / math.sqrt(len(profits)) if len(profits) > 1 else None
    summary.update(negative_ci_low_percent=low, negative_ci_high_percent=high,
                   mean_ci_low=summary["average_profit"] - error if error is not None else None,
                   mean_ci_high=summary["average_profit"] + error if error is not None else None,
                   mean_interval_method="Normal approximation over independent simulated days; "
                                        "rare unobserved losses remain possible.")
    return summary


def compare_days(days=5000, progress=None):
    if type(days) is not int or days < 1:
        raise ValueError("days must be a positive integer")
    settings = json.loads((ROOT / "gratta_settings.json").read_text(encoding="utf-8"))
    timing = timing_from_settings(settings)
    master = secrets.randbits(128)
    results = {}
    raw = {}
    for name, sampler in (("cdf", sample_round), ("full_board", full_board_round)):
        rows = []
        # A plain replacement avoids retaining millions of unittest.mock calls.
        with patch("analysis.collective_parallel.sample_round", new=sampler):
            for day in range(days):
                rows.append(simulate_day(f"{master}:{name}:day:{day}", timing,
                                         protected=True, floor_lock=False, laptop_count=4,
                                         target_cents=300, drawdown_cents=50000,
                                         deadline_seconds=43200, round_cap=4000))
                if progress and (day + 1) % 500 == 0:
                    progress(name, day + 1, days)
        results[name] = day_statistics(rows)
        raw[name] = rows
    cdf = [r["profit"] for r in raw["cdf"]]
    oracle = [r["profit"] for r in raw["full_board"]]
    difference = mean(oracle) - mean(cdf)
    error = 1.959963984540054 * math.sqrt(variance(cdf) / days + variance(oracle) / days) if days > 1 else None
    return {
        "days_per_sampler": days, "timing_seconds": timing, "results": results,
        "comparison": {"full_board_minus_cdf_mean": difference,
                       "difference_ci_low": difference - error if error is not None else None,
                       "difference_ci_high": difference + error if error is not None else None,
                       "paired_worlds": False,
                       "method": "Independent samples, same financial/timing controller; "
                                 "different random primitives, no policy optimization."},
    }


def financial_math():
    q = WIN_PROBABILITY
    return {
        "win_probability": q, "payout_on_win_eur": .68, "stake_eur": .1,
        "net_win_eur": .58, "net_loss_eur": -.1,
        "expected_profit_per_round_eur": q * .68 - .1,
        "expected_profit_per_100_wagered_eur": 100 * (q * 6.8 - 1),
        "break_even_total_multiplier": 1 / q,
        "minimum_win_probability_for_6_8_multiplier": 1 / 6.8,
        "win_probability_reduction_before_break_even_percentage_points": 100 * (q - 1 / 6.8),
        "maximum_fraction_fee_on_winning_payout_before_break_even": 1 - 1 / (q * 6.8),
        "expected_profit_if_actual_winning_payment_0_66_eur": q * .66 - .1,
        "expected_profit_if_actual_winning_payment_0_65_eur": q * .65 - .1,
        "fee_warning": "Fee threshold assumes an unrounded proportional deduction "
                       "from the total winning payout. Actual cent rounding can change "
                       "the result; no real-site fees or taxes have been verified.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boards", type=int, default=500000)
    parser.add_argument("--days", type=int, default=5000)
    args = parser.parse_args()
    if min(args.boards, args.days) < 1:
        parser.error("counts must be positive")
    started = time.monotonic()
    boards = validate_boards(args.boards)
    print("Full-board validation:", boards["all_expected_inside_intervals"], flush=True)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "synthetic_uniform_independent_full_boards",
        "actual_autoplay_changed": False, "real_history_used": False,
        "costs_included": False, "real_site_randomness_verified": False,
        "configuration": {"laptops_playing": 4, "master_playing": False,
                          "stake_eur": .1, "difficulty": "medium", "picks": 6,
                          "mines": 6, "total_multiplier": 6.8, "target_eur": 3,
                          "drawdown_eur": 500, "round_cap_per_laptop": 4000,
                          "deadline_hours": 12, "reserve_pending_stakes": True},
        "full_board_validation": boards,
        "financial_math": financial_math(),
        "ideal_16000_settled_reference": collective_distribution(3, caps=(16000,))[0],
        "day_comparison": compare_days(args.days, progress=lambda name, done, total:
            print(f"{name}: {done}/{total}", flush=True)),
    }
    # The existing exact helper's machine count is 3; this reference has 4.
    report["ideal_16000_settled_reference"]["round_cap_per_laptop"] = 4000
    report["runtime_seconds"] = time.monotonic() - started
    directory = ROOT / "bulk_results"
    directory.mkdir(exist_ok=True)
    path = directory / f"collective_oracle_{datetime.now(timezone.utc):%Y%m%d_%H%M%S_%f}.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print("Report:", path, flush=True)
    print(json.dumps(report["day_comparison"], indent=2), flush=True)


if __name__ == "__main__":
    main()
