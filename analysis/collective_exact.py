"""Settled collective-stop distribution: no random sampling or online actions."""

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time

import numpy as np


WIN_PROBABILITY = math.comb(19, 6) / math.comb(25, 6)
TARGETS = (.1, .5, 1, 2, 3, 5, 7, 10)
CAPS = (3000, 6000, 12000)


def collective_distribution(target, caps=CAPS, trim_threshold=1e-21):
    """Absorb at target; propagate remaining profits in units of two cents.

    Tiny left-tail trimming has a recorded probability bound. Use zero to
    retain all reachable states, useful for small exact enumeration checks.
    """
    if not math.isfinite(target) or target <= 0:
        raise ValueError("target must be positive and finite")
    caps = sorted(set(caps))
    if not caps or any(isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in caps):
        raise ValueError("caps must contain positive integer round counts")
    if not math.isfinite(trim_threshold) or trim_threshold < 0:
        raise ValueError("trim_threshold must be finite and nonnegative")
    barrier = math.ceil(round(target * 100) / 2)
    probabilities = np.array([1.0])
    low = 0
    stopped_mass = stopped_profit = expected_rounds = discarded = 0.0
    results = []
    for rounds in range(1, caps[-1] + 1):
        expected_rounds += probabilities.sum()
        # A win adds 58 cents; a loss removes 10, hence +29/-5 units.
        updated = np.zeros(len(probabilities) + 34)
        updated[:len(probabilities)] += probabilities * (1 - WIN_PROBABILITY)
        updated[34:] += probabilities * WIN_PROBABILITY
        low -= 5
        boundary = barrier - low
        absorbing = updated[boundary:]
        stopped_mass += absorbing.sum()
        stopped_profit += .02 * np.dot(absorbing, np.arange(barrier, barrier + len(absorbing)))
        probabilities = updated[:boundary]
        if trim_threshold:
            retained = np.flatnonzero(probabilities > trim_threshold)
            trim = int(retained[0]) if len(retained) else len(probabilities)
            discarded += probabilities[:trim].sum()
            probabilities = probabilities[trim:]
            low += trim
        if rounds in caps:
            units = low + np.arange(len(probabilities))
            negative = float(probabilities[units < 0].sum())
            zero = float(probabilities[units == 0].sum())
            positive = float(stopped_mass + probabilities[units > 0].sum())
            unfinished = float(probabilities.sum())
            final_profit = float(stopped_profit + .02 * np.dot(probabilities, units))
            expected_losses = float(.02 * np.dot(probabilities[units < 0], units[units < 0]))
            results.append({
                "target_eur": target, "total_round_cap": rounds,
                "round_cap_per_laptop": rounds / 3,
                "negative_probability": negative, "zero_probability": zero,
                "positive_probability": positive,
                "nonpositive_probability": negative + zero,
                "target_reached_probability": float(stopped_mass),
                "deadline_probability": unfinished,
                "mean_profit_eur": final_profit,
                "expected_gains_eur": final_profit - expected_losses,
                "expected_losses_eur": expected_losses,
                "mean_negative_day_profit_eur": expected_losses / negative if negative else None,
                "expected_total_rounds": float(expected_rounds),
                "one_or_more_negative_days_in_30_probability": -math.expm1(30 * math.log1p(-negative)),
                "minimum_possible_profit_eur": -.1 * rounds,
                "maximum_profit_upper_bound_eur": min(.58 * rounds, .02 * (barrier + 28)),
                "omitted_probability_bound": float(discarded),
                "mean_profit_error_bound_eur": float(discarded * max(.1 * rounds, .02 * (barrier + 28))),
                "mass_balance_error": abs(float(stopped_mass + unfinished + discarded) - 1),
                "funding_safe_with_3000_eur": .1 * rounds <= 3000,
            })
    return results


def main():
    started = time.monotonic()
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "method": "Absorbing probability recurrence, not Monte Carlo; all rounds settle "
                  "before the next stop check. Tiny discarded numeric tails are bounded. "
                  "No trailing drawdown stop. Equal laptop allocation under IID outcomes "
                  "has the same aggregate law.",
        "board_size": 25, "mines": 6, "picks": 6,
        "total_multiplier": 6.8, "bet_eur": .1,
        "win_probability": WIN_PROBABILITY,
        "costs_included": False, "real_history_used": False,
        "actual_speed_verified": False, "coordinator_implemented": False,
        "results": [],
    }
    for target in TARGETS:
        rows = collective_distribution(target)
        report["results"].extend(rows)
        print(target, [(r["total_round_cap"], round(100 * r["negative_probability"], 6),
                        round(r["mean_profit_eur"], 6)) for r in rows], flush=True)
    report["elapsed_seconds"] = time.monotonic() - started
    root = Path(__file__).resolve().parents[1]
    directory = root / "bulk_results"
    directory.mkdir(exist_ok=True)
    path = directory / f"collective_exact_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print("Report:", path, "seconds:", report["elapsed_seconds"], flush=True)


if __name__ == "__main__":
    main()
