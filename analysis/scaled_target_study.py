"""Offline fixed-scenario study: session-close time to 10,000 net credits."""

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import argparse
import json
import secrets
from statistics import mean
import time
from unittest.mock import patch

from . import collective_parallel as parallel
from .collective_validation import distribution


SCALES = (1, 2, 5, 10)
GOAL_CENTS = 1_000_000


def electricity_cents(seconds):
    # 240 W for the whole group at 0.30/kWh = 0.002 cents per second.
    return int((Decimal(str(seconds)) * Decimal(".002")).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def validate(replicates, workers, max_days, scales):
    if any(type(value) is not int or value < 1 for value in (replicates, workers, max_days)):
        raise ValueError("Positive integer replicate, worker and day counts required")
    if (not isinstance(scales, (list, tuple)) or not scales
            or any(type(value) is not int or value < 1 for value in scales)
            or len(set(scales)) != len(scales)):
        raise ValueError("Scales must be distinct positive integers")


def run_path(arguments):
    seed, scale, max_days, timing = arguments
    validate(1, 1, max_days, (scale,))
    bank = [2000 * scale] * 4
    initial_total = sum(bank)
    minimum = list(bank)
    stake = 10 * scale
    # Reserve a worst-case round duration before the daily cutoff, without looking at outcomes.
    maximum_round_seconds = 2 * timing["play"] + 2 * timing["tile"]
    start_deadline = 18000 - maximum_round_seconds
    if start_deadline <= 0:
        raise ValueError("A round must fit inside the five-hour daily budget")
    total_seconds = 0.0
    total_rounds = sessions = 0
    any_unfunded = False
    negative_sessions = 0
    peak = maximum_checkpoint_drawdown = maximum_session_drawdown = 0
    previous_net = net = 0
    hit_day = None
    daily_rows = []
    status = "horizon"
    with patch.object(parallel, "STAKE", stake):
        for day in range(1, max_days + 1):
            before_day = sum(bank)
            day_seconds = 0.0
            day_rounds = day_sessions = 0
            while day_seconds < start_deadline and any(value >= stake for value in bank):
                before_session = sum(bank)
                previous_net = before_session - initial_total - electricity_cents(total_seconds)
                result = parallel.simulate_day(
                    f"{seed}:day:{day}:session:{day_sessions}", timing,
                    protected=True, floor_lock=False, laptop_count=4, starting_cash_cents=bank,
                    target_cents=300, drawdown_cents=50000,
                    deadline_seconds=start_deadline - day_seconds,
                    round_cap=4000, picks=2, payout_cents=18 * scale)
                bank = result["pc_final_cash_cents"]
                rounds = sum(result["pc_rounds"])
                assert rounds > 0 and all(type(value) is int and value >= 0 for value in bank)
                assert sum(bank) - before_session == round(result["profit"] * 100)
                duration = result["hours"] * 3600
                assert duration > 0
                day_seconds += duration
                total_seconds += duration
                day_rounds += rounds
                total_rounds += rounds
                day_sessions += 1
                sessions += 1
                negative_sessions += sum(bank) < before_session
                any_unfunded |= any(value < stake for value in bank)
                minimum = [min(a, b) for a, b in zip(minimum, result["pc_minimum_cash_cents"])]
                gross = sum(bank) - initial_total
                peak = max(peak, gross)
                maximum_checkpoint_drawdown = max(maximum_checkpoint_drawdown, peak - gross)
                maximum_session_drawdown = max(maximum_session_drawdown,
                                               round(result["max_settled_drawdown"] * 100))
                net = gross - electricity_cents(total_seconds)
                if net >= GOAL_CENTS:
                    assert previous_net < GOAL_CENTS
                    hit_day, status = day, "hit"
                    break
            assert day_seconds <= 18000 + 1e-7
            daily_rows.append({"day": day, "seconds": day_seconds, "rounds": day_rounds,
                               "sessions_with_bets": day_sessions,
                               "gross_profit_cents": sum(bank) - before_day,
                               "closing_cash_cents_per_pc": list(bank)})
            if hit_day is not None:
                break
            if all(value < stake for value in bank):
                status = "all_unfunded"
                break
    gross = sum(bank) - initial_total
    assert gross == sum(row["gross_profit_cents"] for row in daily_rows)
    assert total_rounds == sum(row["rounds"] for row in daily_rows)
    assert sessions == sum(row["sessions_with_bets"] for row in daily_rows)
    assert net == gross - electricity_cents(total_seconds)
    return {"seed": seed, "scale": scale, "status": status, "hit_day": hit_day,
            "observed_days": len(daily_rows), "activity_hours": total_seconds / 3600,
            "gross_profit_cents": gross, "electricity_cents": electricity_cents(total_seconds),
            "net_profit_cents": net, "previous_checkpoint_net_cents": previous_net,
            "final_cash_cents_per_pc": bank, "minimum_cash_cents_per_pc": minimum,
            "total_rounds": total_rounds, "sessions_with_bets": sessions,
            "negative_sessions": negative_sessions,
            "any_pc_unfunded_at_session_close": any_unfunded,
            "maximum_checkpoint_drawdown_cents": maximum_checkpoint_drawdown,
            "maximum_within_session_drawdown_cents": maximum_session_drawdown,
            "maximum_daily_seconds": max(row["seconds"] for row in daily_rows),
            "last_day_activity_hours": daily_rows[-1]["seconds"] / 3600,
            "daily_rows": daily_rows}


def summarize(rows):
    hits = [row for row in rows if row["status"] == "hit"]
    return {"replicates": len(rows), "target_hits": len(hits),
            "horizon_censored": sum(row["status"] == "horizon" for row in rows),
            "all_unfunded_before_target": sum(row["status"] == "all_unfunded" for row in rows),
            "any_pc_unfunded_before_stop": sum(row["any_pc_unfunded_at_session_close"] for row in rows),
            "hit_rate": len(hits) / len(rows),
            "hit_day_among_successes": distribution([row["hit_day"] for row in hits]) if hits else None,
            "activity_hours_to_hit_among_successes": distribution([row["activity_hours"] for row in hits]) if hits else None,
            "net_profit_at_stop_credits": distribution([row["net_profit_cents"] / 100 for row in rows]),
            "mean_electricity_at_stop_credits": mean(row["electricity_cents"] / 100 for row in rows),
            "maximum_checkpoint_drawdown_credits": max(row["maximum_checkpoint_drawdown_cents"] for row in rows) / 100,
            "maximum_within_session_drawdown_credits": max(row["maximum_within_session_drawdown_cents"] for row in rows) / 100,
            "minimum_cash_per_pc_credits": [min(row["minimum_cash_cents_per_pc"][pc] for row in rows) / 100 for pc in range(4)],
            "maximum_daily_seconds": max(row["maximum_daily_seconds"] for row in rows)}


def run_research(replicates=50, workers=4, max_days=450, scales=SCALES):
    validate(replicates, workers, max_days, scales)
    created = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    timing = parallel.timing_from_settings(json.loads(
        (parallel.ROOT / "gratta_settings.json").read_text(encoding="utf-8")))
    # Check the hypothetical advantage before spending time simulating.
    assert 19 * 18 / (25 * 24) == .57
    assert Decimal(".57") * Decimal("1.8") - 1 == Decimal(".026")
    jobs = [(secrets.randbits(128), scale, max_days, timing)
            for scale in scales for _ in range(replicates)]
    assert len({job[0] for job in jobs}) == len(jobs)
    completed = {}
    print(f"Fixed scenarios {tuple(scales)}: {replicates} paths each, maximum {max_days} days", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(run_path, job): index for index, job in enumerate(jobs)}
        for future in as_completed(futures):
            completed[futures[future]] = future.result()
            if len(completed) % 5 == 0 or len(completed) == len(jobs):
                print(f"Completed {len(completed)}/{len(jobs)} paths", flush=True)
    rows = [completed[index] for index in range(len(jobs))]
    return {"created_at": created, "completed_at": datetime.now(timezone.utc).isoformat(),
            "script": "analysis/scaled_target_study.py", "real_games_started": False,
            "gui_settings_or_live_bot_changed": False,
            "source": "fresh_uniform_independent_synthetic_boards",
            "previous_reports_reused_as_samples": False,
            "protocol": {"replicates_per_scenario": replicates, "maximum_days": max_days,
                         "net_profit_goal_credits": GOAL_CENTS / 100,
                         "goal_excludes_initial_capital": True, "goal_deducts_example_electricity": True,
                         "laptops": 4, "separate_nonplaying_master": True,
                         "cells": 25, "mines": 6, "picks": 2, "total_multiplier": 1.8,
                         "session_target_credits": 3, "session_drawdown_limit_credits": 500,
                         "round_cap_per_laptop_per_session": 4000,
                         "maximum_daily_elapsed_hours": 5,
                         "last_start_margin_seconds": 2 * timing["play"] + 2 * timing["tile"],
                         "timing_seconds": timing,
                         "continuous_balances_across_days": True, "money_unit_credits": .01,
                         "topups_or_transfers": False, "automatic_stake_changes": False,
                         "initial_capital_or_profit_protection": False,
                         "checkpoint": "After every fully settled session; stop at first checkpoint above the net goal",
                         "sampling": "Independent seeds for every scenario and replicate; no monthly resets",
                         "electricity": "240 W total for all five PCs at 0.30/kWh; external to balances; cumulative cost rounded once per checkpoint"},
            "scenarios": [{"scale": scale, "stake_credits": scale / 10,
                           "total_win_payment_credits": 18 * scale / 100,
                           "initial_capital_per_laptop_credits": 20 * scale,
                           "initial_total_capital_credits": 80 * scale,
                           "theoretical_expected_profit_per_game_credits": .0026 * scale,
                           "theoretical_rtp_percent": 102.6,
                           "observed": summarize([row for row in rows if row["scale"] == scale])}
                          for scale in scales],
            "path_rows": rows,
            "limitations": [
                "Fixed independent starting configurations, not a profits-funded progression or an 80-credit loss cap.",
                "Larger stakes and capital have no specified upper bound, so this study cannot identify a globally fastest configuration.",
                "Session-close threshold times are not exact first-passage times during open games.",
                "Quantiles among hits are conditional on success; horizon misses and depletion are reported separately.",
                "A small finite sample cannot establish zero risk, even if all paths hit the target.",
                "Drawdowns are measured separately within sessions and between settled session checkpoints, not as a full intrapartita experiment-wide maximum.",
                "The 102.6% return follows from the assumed uniform independent boards and 1.8x payout; it is not a verified site return.",
                "Immediate session restarts omit residual reset delays, network latency, setup, failures and voluntary pauses.",
                "Electricity is an illustrative external cost, not a measured consumption or real-money simulation expense.",
                "The HTML has separate defaults, a 30-day calendar and a 12-hour start budget; this study does not change it."],
            "runtime_seconds": time.monotonic() - started}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replicates", type=int, default=50)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-days", type=int, default=450)
    options = parser.parse_args()
    report = run_research(options.replicates, options.workers, options.max_days)
    directory = parallel.ROOT / "bulk_results"
    directory.mkdir(exist_ok=True)
    path = directory / f"fixed_scenarios_net_10000_{datetime.now(timezone.utc):%Y%m%d_%H%M%S_%fZ}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
    print("Report:", path, flush=True)
    print(json.dumps(report["scenarios"], indent=2), flush=True)
