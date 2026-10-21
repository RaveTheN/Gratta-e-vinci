"""Research only: repeat +3 EUR collective sessions within a shared daily time budget."""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from fractions import Fraction
import argparse
import json
import math
import secrets
from statistics import mean, stdev
import time

from . import collective_parallel as parallel
from .collective_validation import distribution


def validate_counts(months, hours, days):
    if any(type(value) is not int or value < 1 for value in (months, days)):
        raise ValueError("Positive integer month and day counts required")
    if type(hours) not in (int, float) or not math.isfinite(hours) or hours <= 0:
        raise ValueError("Daily hours must be finite and positive")


def run_chunk(arguments):
    months, seed, hours, days, timing = arguments
    validate_counts(months, hours, days)
    deadline = hours * 3600
    rows = []
    for month in range(1, months + 1):
        bank = [2000] * 4
        minimum = list(bank)
        minimum_close = list(bank)
        pc_rounds = [0] * 4
        ever_unfunded = [False] * 4
        statuses = Counter()
        daily_profits = []
        session_profit_cents = []
        daily_hours = []
        daily_sessions = []
        daily_rounds = []
        no_bet_attempts = negative_sessions = zero_sessions = target_sessions = 0
        last_active_day = active_days = idle_days = overrun_days = 0
        first_all_unfunded_day = first_pc_unfunded_day = None
        minimum_daily_total = 8000
        for day in range(1, days + 1):
            before_day = sum(bank)
            elapsed = 0.0
            rounds_today = sessions_today = day_session_profit = 0
            if all(value < 10 for value in bank):
                idle_days += 1
            while elapsed < deadline and any(value >= 10 for value in bank):
                before_session = sum(bank)
                session = parallel.simulate_day(
                    f"{seed}:month:{month}:day:{day}:session:{sessions_today + 1}", timing,
                    laptop_count=4, starting_cash_cents=bank, protected=True, floor_lock=False,
                    target_cents=300, drawdown_cents=50000,
                    deadline_seconds=deadline - elapsed, round_cap=4000, picks=2, payout_cents=18)
                bank = session["pc_final_cash_cents"]
                profit = sum(bank) - before_session
                assert profit == round(session["profit"] * 100)
                assert all(type(value) is int and value >= 0 for value in bank)
                rounds = sum(session["pc_rounds"])
                statuses[session["status"]] += 1
                elapsed += session["hours"] * 3600
                if not rounds:
                    no_bet_attempts += 1
                    assert all(value < 10 for value in bank)
                    break
                assert session["hours"] > 0
                sessions_today += 1
                rounds_today += rounds
                session_profit_cents.append(profit)
                day_session_profit += profit
                negative_sessions += profit < 0
                zero_sessions += profit == 0
                target_sessions += session["status"] == "target"
                for pc in range(4):
                    minimum[pc] = min(minimum[pc], session["pc_minimum_cash_cents"][pc])
                    minimum_close[pc] = min(minimum_close[pc], bank[pc])
                    pc_rounds[pc] += session["pc_rounds"][pc]
                    ever_unfunded[pc] |= bank[pc] < 10
                if first_pc_unfunded_day is None and any(ever_unfunded):
                    first_pc_unfunded_day = day
                if first_all_unfunded_day is None and all(value < 10 for value in bank):
                    first_all_unfunded_day = day
            day_profit = sum(bank) - before_day
            assert day_profit == day_session_profit
            minimum_daily_total = min(minimum_daily_total, sum(bank))
            daily_profits.append(day_profit)
            daily_hours.append(elapsed / 3600)
            daily_sessions.append(sessions_today)
            daily_rounds.append(rounds_today)
            active_days += rounds_today > 0
            if rounds_today:
                last_active_day = day
            overrun_days += elapsed > deadline + 1e-8
        gross_cents = sum(bank) - 8000
        assert gross_cents == sum(daily_profits) == sum(session_profit_cents)
        assert sum(pc_rounds) == sum(daily_rounds)
        assert active_days + idle_days == days
        electricity = round(.240 * .30 * sum(daily_hours), 2)
        rows.append({
            "month": month, "gross_profit": gross_cents / 100,
            "electricity_cost_example": electricity,
            "net_profit_after_example_electricity": round(gross_cents / 100 - electricity, 2),
            "elapsed_hours": sum(daily_hours), "active_days": active_days,
            "idle_days_after_funds_exhausted": idle_days,
            "negative_days": sum(value < 0 for value in daily_profits),
            "zero_active_days": sum(profit == 0 and rounds > 0 for profit, rounds in zip(daily_profits, daily_rounds)),
            "worst_day": min(daily_profits) / 100,
            "sessions_with_bets": sum(daily_sessions), "session_attempts_without_bets": no_bet_attempts,
            "target_sessions": target_sessions, "negative_sessions": negative_sessions,
            "zero_sessions_with_bets": zero_sessions,
            "worst_session": min(session_profit_cents) / 100 if session_profit_cents else None,
            "session_status_counts": dict(statuses),
            "minimum_sessions_per_active_day": min(count for count in daily_sessions if count) if active_days else 0,
            "maximum_sessions_per_day": max(daily_sessions),
            "total_rounds": sum(pc_rounds), "pc_rounds": pc_rounds,
            "maximum_daily_hours": max(daily_hours), "settlement_overrun_days": overrun_days,
            "maximum_settlement_overrun_seconds": max(0.0, (max(daily_hours) - hours) * 3600),
            "minimum_cash_per_pc_including_open_stakes": [value / 100 for value in minimum],
            "minimum_session_closing_cash_per_pc": [value / 100 for value in minimum_close],
            "minimum_daily_closing_total_cash": minimum_daily_total / 100,
            "final_cash_per_pc": [value / 100 for value in bank],
            "pc_ever_unfunded_at_session_close": ever_unfunded,
            "pc_unfunded_at_month_close": [value < 10 for value in bank],
            "last_active_day": last_active_day,
            "first_pc_unfunded_day": first_pc_unfunded_day,
            "first_all_unfunded_day": first_all_unfunded_day,
        })
    return rows


def summarize(rows, days):
    def monthly_distribution(key):
        values = [row[key] for row in rows]
        result = distribution(values)
        error = stdev(values) / math.sqrt(len(values)) if len(values) > 1 else None
        result.update(count=len(values), standard_error_of_mean=error,
                      approximate_95_percent_confidence_interval_of_mean=
                      [mean(values) - 1.96 * error, mean(values) + 1.96 * error] if error is not None else None)
        return result

    statuses = Counter()
    for row in rows:
        statuses.update(row["session_status_counts"])
    total_days = len(rows) * days
    sessions = sum(row["sessions_with_bets"] for row in rows)
    active_days = sum(row["active_days"] for row in rows)
    return {
        "monthly_gross": monthly_distribution("gross_profit"),
        "monthly_net_after_example_electricity": monthly_distribution("net_profit_after_example_electricity"),
        "negative_gross_months": sum(row["gross_profit"] < 0 for row in rows),
        "negative_net_months": sum(row["net_profit_after_example_electricity"] < 0 for row in rows),
        "mean_monthly_electricity_cost": mean(row["electricity_cost_example"] for row in rows),
        "mean_monthly_hours": mean(row["elapsed_hours"] for row in rows),
        "mean_monthly_rounds": mean(row["total_rounds"] for row in rows),
        "calendar_days": total_days, "active_days": active_days,
        "idle_days_after_funds_exhausted": sum(row["idle_days_after_funds_exhausted"] for row in rows),
        "negative_days": sum(row["negative_days"] for row in rows),
        "zero_active_days": sum(row["zero_active_days"] for row in rows),
        "mean_sessions_per_calendar_day": sessions / total_days,
        "mean_sessions_per_active_day": sessions / active_days if active_days else None,
        "mean_rounds_per_calendar_day": sum(row["total_rounds"] for row in rows) / total_days,
        "sessions_with_bets": sessions,
        "session_attempts_without_bets": sum(row["session_attempts_without_bets"] for row in rows),
        "target_sessions": sum(row["target_sessions"] for row in rows),
        "negative_sessions": sum(row["negative_sessions"] for row in rows),
        "zero_sessions_with_bets": sum(row["zero_sessions_with_bets"] for row in rows),
        "session_status_counts": dict(statuses),
        "worst_session": min((row["worst_session"] for row in rows if row["worst_session"] is not None), default=None),
        "worst_day": min(row["worst_day"] for row in rows),
        "months_with_any_pc_unfunded": sum(any(row["pc_ever_unfunded_at_session_close"]) for row in rows),
        "months_with_all_pcs_unfunded": sum(all(row["pc_unfunded_at_month_close"]) for row in rows),
        "last_active_day_counts": dict(Counter(row["last_active_day"] for row in rows)),
        "minimum_cash_per_pc_including_open_stakes": [
            min(row["minimum_cash_per_pc_including_open_stakes"][pc] for row in rows) for pc in range(4)],
        "mean_final_cash_per_pc": [mean(row["final_cash_per_pc"][pc] for row in rows) for pc in range(4)],
        "maximum_daily_hours": max(row["maximum_daily_hours"] for row in rows),
        "settlement_overrun_days": sum(row["settlement_overrun_days"] for row in rows),
        "maximum_settlement_overrun_seconds": max(row["maximum_settlement_overrun_seconds"] for row in rows),
    }


def run_research(months=1000, workers=4, hours=4, days=30):
    validate_counts(months, hours, days)
    if type(workers) is not int or workers < 1:
        raise ValueError("Workers must be a positive integer")
    created = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    settings_path = parallel.ROOT / "gratta_settings.json"
    timing = parallel.timing_from_settings(json.loads(settings_path.read_text(encoding="utf-8")))
    counts = [months // workers + (index < months % workers) for index in range(workers)]
    jobs = [(count, secrets.randbits(128), hours, days, timing) for count in counts if count]
    assert len({job[1] for job in jobs}) == len(jobs)
    rows = []
    print(f"6 mines, 1.8x, {hours:g} daily hours: {months} independent months", flush=True)
    # Preserve job ordering so saved seeds reproduce the month numbering.
    chunks = {}
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(run_chunk, job): index for index, job in enumerate(jobs)}
        for future in as_completed(futures):
            chunks[futures[future]] = future.result()
            print(f"Completed {sum(len(chunk) for chunk in chunks.values())}/{months} months", flush=True)
    for index in range(len(jobs)):
        rows.extend(chunks[index])
    for index, row in enumerate(rows, 1):
        row["month"] = index
        assert sum(round(value * 100) for value in row["final_cash_per_pc"]) - 8000 == round(row["gross_profit"] * 100)
    win = Fraction(19, 25) * Fraction(18, 24)
    return {
        "created_at": created, "completed_at": datetime.now(timezone.utc).isoformat(),
        "script": "analysis/timed_trigger_sessions.py", "source": "fresh_synthetic_uniform_independent_boards",
        "previous_reports_reused_as_samples": False, "real_games_started": False,
        "gui_settings_or_live_bot_changed": False,
        "independent_seed_chunks": [{"months": count, "seed": seed} for count, seed, _, _, _ in jobs],
        "simulation": {"independent_months": months, "days_per_month": days, "cells": 25, "mines": 6,
                       "picks": 2, "laptops": 4, "separate_master_pc": True,
                       "initial_bankroll_per_laptop": 20, "initial_total_bankroll": 80,
                       "stake": .1, "payout_on_win": .18, "multiplier": 1.8, "money_unit_eur": .01,
                       "global_session_target": 3, "sessions_per_day": "repeat_while_time_and_funds_remain",
                       "global_daily_target": None, "round_cap_per_session_per_pc": 4000,
                       "daily_round_cap_per_pc": None, "daily_start_deadline_hours": hours,
                       "global_drawdown_limit_per_session": 500, "principal_floor_lock": False,
                       "stop_policy": "cash_reserved_trigger", "protected_open_stake_reservations": True,
                       "topups_inside_month": False, "transfers_between_laptops": False,
                       "voluntary_pauses": False},
        "timing_source": "gratta_settings.json: technical delays only; read once before workers start",
        "timing_seconds": timing,
        "theoretical_calculations": {"win_probability": float(win), "total_win_payment_eur": .18,
                                     "net_win_eur": .08, "net_loss_eur": -.10,
                                     "expected_profit_per_game_eur": float(win * Fraction(18, 100) - Fraction(1, 10)),
                                     "return_to_player_percent": float(win * 180),
                                     "break_even_total_win_payment_eur": float(Fraction(1, 10) / win)},
        "method": "Repeat sessions until the daily start deadline or all four individual balances are below the stake. "
                  "Each session has its own +3 EUR target and 4000-round limit per laptop; no fixed daily gain or daily round cap. "
                  "The master sees only observed settlements and currently available cash, with all open stakes already reserved. "
                  "At a stop, drain open games, then use only the remaining daily time for the next session. "
                  "Final settlements may exceed the deadline; no new bets start at or after it. "
                  "Carry integer-cent individual balances between all sessions and days. Each month begins once with 80 EUR. "
                  "Do not create repeated empty sessions after funds run out; count later calendar days as idle separately.",
        "electricity_example": {"total_power_watts_all_five_pcs": 240, "eur_per_kwh": .30,
                                "charged_hours": "Actual elapsed group activity including final settlements, once, not per laptop",
                                "monthly_cost_rounding": "Nearest cent once per month", "hardware_power_measured": False,
                                "other_costs_included": False},
        "observed_simulation": summarize(rows, days), "monthly_rows": rows,
        "limitations": ["Uniform independent mine placement and the stated 1.8x total payout are unverified site assumptions.",
                        "The positive 102.6% theoretical return follows from those assumptions, not from measured site results.",
                        "Technical delays are modeled from settings; setup, network delays, retries, failures and coordinator latency are excluded.",
                        "Session restart is immediate after draining pending games, following prior studies; residual reveal/reset cooldown and coordinator/network latency at session boundaries are not modeled.",
                        "The 500 EUR drawdown limit does not protect the 80 EUR starting capital.",
                        "Electricity uses an illustrative fixed 240 W group draw; real consumption and standby costs are unmeasured.",
                        "Simulation percentiles and confidence intervals describe this model and finite sample, not guaranteed future outcomes.",
                        "No live bot or graphical simulator was configured by this experiment."],
        "runtime_seconds": time.monotonic() - started,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=float, choices=(4, 5), required=True)
    parser.add_argument("--months", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=4)
    options = parser.parse_args()
    report = run_research(months=options.months, workers=options.workers, hours=options.hours)
    directory = parallel.ROOT / "bulk_results"
    directory.mkdir(exist_ok=True)
    path = directory / f"timed_trigger_6_mines_180_millieuro_{options.hours:g}h_{datetime.now(timezone.utc):%Y%m%d_%H%M%S_%fZ}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
    print("Report:", path, flush=True)
    print(json.dumps(report["observed_simulation"], indent=2), flush=True)
