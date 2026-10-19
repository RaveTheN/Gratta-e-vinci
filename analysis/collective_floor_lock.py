"""Research a collective principal floor activated only after the first profit."""

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis.collective_exact import CAPS, WIN_PROBABILITY, collective_distribution


def floor_lock_distribution(target, caps=CAPS, trim_threshold=1e-21, loss_limit=50):
    """Phase 1 seeks any positive profit; phase 2 spends only current profit."""
    if isinstance(target, bool) or not math.isfinite(target) or target < .01:
        raise ValueError("target must be finite and at least 0.01")
    caps = sorted(set(caps))
    if not caps or any(isinstance(n, bool) or not isinstance(n, int) or n < 1 for n in caps):
        raise ValueError("caps must contain positive integer round counts")
    if not math.isfinite(trim_threshold) or trim_threshold < 0:
        raise ValueError("trim_threshold must be finite and nonnegative")
    if loss_limit is not None:
        if isinstance(loss_limit, bool) or not math.isfinite(loss_limit) or loss_limit <= target + .58:
            raise ValueError("loss_limit must exceed target + 0.58 EUR for this two-stage model")
        loss_boundary = math.floor(-round(loss_limit * 100) / 2)
    else:
        loss_boundary = None
    barrier = math.ceil(round(target * 100) / 2)
    unlocked, low = np.array([1.0]), 0
    locked = np.zeros(barrier)
    stopped_mass = stopped_profit = floor_mass = target_mass = zero_stopped = 0.0
    expected_rounds = discarded = 0.0
    loss_mass = loss_profit = 0.0
    results = []
    for rounds in range(1, caps[-1] + 1):
        expected_rounds += unlocked.sum() + locked.sum()
        next_unlocked = np.zeros(len(unlocked) + 34)
        next_unlocked[:len(unlocked)] += unlocked * (1 - WIN_PROBABILITY)
        next_unlocked[34:] += unlocked * WIN_PROBABILITY
        low -= 5
        boundary = 1 - low
        first_positive = next_unlocked[boundary:]
        unlocked = next_unlocked[:boundary]
        if loss_boundary is not None:
            # Before first profit the peak is zero; afterwards the floor and
            # target keep drawdowns smaller than the configured loss limit.
            cut = min(len(unlocked), max(0, loss_boundary - low + 1))
            loss_mass += unlocked[:cut].sum()
            loss_profit += .02 * np.dot(unlocked[:cut], low + np.arange(cut))
            unlocked = unlocked[cut:]
            low += cut

        next_locked = np.zeros(barrier + 29)
        # Only locked profits >= 10 cents may finance another 10-cent bet.
        if barrier > 5:
            next_locked[:barrier - 5] += locked[5:] * (1 - WIN_PROBABILITY)
            next_locked[34:] += locked[5:] * WIN_PROBABILITY
        next_locked[1:len(first_positive) + 1] += first_positive
        floor = next_locked[:min(5, barrier)]
        target_hit = next_locked[barrier:]
        floor_mass += floor.sum()
        target_mass += target_hit.sum()
        stopped_mass += floor.sum() + target_hit.sum()
        stopped_profit += .02 * (np.dot(floor, np.arange(len(floor)))
                                + np.dot(target_hit, np.arange(barrier, len(next_locked))))
        zero_stopped += next_locked[0]
        locked = next_locked[:barrier]
        locked[:5] = 0
        if trim_threshold:
            retained = np.flatnonzero(unlocked > trim_threshold)
            trim = int(retained[0]) if len(retained) else len(unlocked)
            discarded += unlocked[:trim].sum()
            unlocked = unlocked[trim:]
            low += trim

        if rounds in caps:
            units = low + np.arange(len(unlocked))
            negative = float(loss_mass + unlocked[units < 0].sum())
            zero = float(zero_stopped + unlocked[units == 0].sum())
            active_locked = float(locked.sum())
            positive = float(stopped_mass - zero_stopped + active_locked)
            unfinished = float(unlocked.sum() + active_locked)
            losses = float(loss_profit + .02 * np.dot(unlocked[units < 0], units[units < 0]))
            profit = float(stopped_profit + loss_profit + .02 * np.dot(unlocked, units)
                           + .02 * np.dot(locked, np.arange(barrier)))
            results.append({
                "target_eur": target, "total_round_cap": rounds,
                "loss_limit_eur": loss_limit, "loss_stop_probability": float(loss_mass),
                "round_cap_per_laptop": rounds / 3,
                "negative_probability": negative, "zero_probability": zero,
                "positive_probability": positive,
                "nonpositive_probability": negative + zero,
                "target_reached_probability": float(target_mass),
                "floor_stop_probability": float(floor_mass),
                "floor_activated_probability": float(stopped_mass + active_locked),
                "deadline_probability": unfinished,
                "deadline_unlocked_probability": float(unlocked.sum()),
                "deadline_locked_probability": active_locked,
                "mean_profit_eur": profit,
                "expected_gains_eur": profit - losses, "expected_losses_eur": losses,
                "mean_negative_day_profit_eur": losses / negative if negative else None,
                "expected_total_rounds": float(expected_rounds),
                "one_or_more_negative_days_in_30_probability": -math.expm1(30 * math.log1p(-negative)),
                "minimum_possible_profit_eur": max(-.1 * rounds, .02 * (loss_boundary - 4))
                    if loss_boundary is not None else -.1 * rounds,
                "minimum_possible_profit_after_floor_activation_eur": 0,
                "omitted_probability_bound": float(discarded),
                "mean_profit_error_bound_eur": float(discarded * max(.1 * rounds, .02 * (barrier + 28))),
                "mass_balance_error": abs(float(stopped_mass + loss_mass + unfinished + discarded) - 1),
                "funding_safe_with_3000_eur": .1 * rounds <= 3000,
            })
    return results


def main():
    started = time.monotonic()
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "method": "Two-stage settled probability recurrence. Seek strictly positive "
                  "aggregate profit first; then latch the initial principal floor and "
                  "only place a 0.10-EUR bet when profit >= 0.10 EUR. Stop at the target, "
                  "at remaining profit below 0.10 EUR, or at the round cap. No live actions.",
        "board_size": 25, "mines": 6, "picks": 6,
        "total_multiplier": 6.8, "bet_eur": .1,
        "win_probability": WIN_PROBABILITY,
        "costs_included": False, "coordinator_implemented": False,
        "real_history_used": False, "pending_bets_modelled": False,
        "warning": "The floor activates only after the first positive profit; phase 1 "
                   "can still end with a loss. Real coordination must reserve all pending "
                   "stakes before spending any locked profit.",
        "plain_stop_at_first_positive": collective_distribution(.02),
        "loss_limit_eur": 50,
        "loss_limit_method": "Before first positive profit, the peak remains zero, "
                             "so drawdown 50 EUR equals a settled profit <= -50 EUR. "
                             "After the floor activates, goals at most 10 EUR and "
                             "nonnegative profits prevent drawdowns of 50 EUR.",
        "without_loss_limit": [],
        "results": [],
    }
    for target in (1, 3, 5, 10):
        rows = floor_lock_distribution(target)
        report["results"].extend(rows)
        report["without_loss_limit"].extend(floor_lock_distribution(target, loss_limit=None))
        print(target, [(r["total_round_cap"], round(100 * r["negative_probability"], 6),
                        round(100 * r["zero_probability"], 4), round(r["mean_profit_eur"], 6),
                        round(100 * r["target_reached_probability"], 4)) for r in rows], flush=True)
    report["elapsed_seconds"] = time.monotonic() - started
    directory = ROOT / "bulk_results"
    directory.mkdir(exist_ok=True)
    path = directory / f"collective_floor_lock_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print("Report:", path, "seconds:", report["elapsed_seconds"], flush=True)


if __name__ == "__main__":
    main()
