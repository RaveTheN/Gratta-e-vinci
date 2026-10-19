"""Validate 30-day bankroll carryover; never controls the online bot."""

from collections import Counter
from datetime import datetime, timezone
import json
import math
import secrets
from statistics import mean, quantiles
import time

try:
    from . import collective_parallel as parallel
    from .collective_parallel import ROOT, BANKROLL, simulate_day, timing_from_settings
except ImportError:
    import collective_parallel as parallel
    from collective_parallel import ROOT, BANKROLL, simulate_day, timing_from_settings


def distribution(values):
    cuts = quantiles(values, n=100, method="inclusive") if len(values) > 1 else [values[0]] * 99
    return {"mean": mean(values), "minimum": min(values), "maximum": max(values),
            **{f"p{p}": cuts[p - 1] for p in (1, 5, 50, 95, 99)}}


def run_validation(months=1000, days_per_month=30, progress=None, picks=6, payout_cents=None,
                   initial_bankroll_cents=BANKROLL, sessions_per_day=1,
                   laptop_count=4, total_power_watts=240, target_cents=300):
    payout_cents = parallel.PAYOUT if payout_cents is None else payout_cents
    if (type(months) is not int or months < 1
            or type(days_per_month) is not int or days_per_month < 1):
        raise ValueError("Positive integer month and day counts required")
    if (type(picks) is not int or not 1 <= picks <= 8
            or type(payout_cents) is not int or payout_cents <= 0):
        raise ValueError("Integer picks from 1 to 8 and positive integer payout cents required")
    if type(initial_bankroll_cents) is not int or initial_bankroll_cents < 0:
        raise ValueError("initial_bankroll_cents must be a nonnegative integer")
    if type(target_cents) is not int or target_cents <= 0:
        raise ValueError("target_cents must be a positive integer")
    if type(sessions_per_day) is not int or sessions_per_day not in (1, 2):
        raise ValueError("sessions_per_day must be 1 or 2")
    if type(laptop_count) is not int or laptop_count < 1:
        raise ValueError("laptop_count must be a positive integer")
    if (type(total_power_watts) not in (int, float)
            or not math.isfinite(total_power_watts) or total_power_watts <= 0):
        raise ValueError("total_power_watts must be finite and positive")
    settings = json.loads((ROOT / "gratta_settings.json").read_text(encoding="utf-8"))
    timing = timing_from_settings(settings)
    started = time.monotonic()
    master = secrets.randbits(128)
    monthly_rows, daily_profits, daily_hours, weekly_gross = [], [], [], []
    daily_statuses = Counter()
    session_statuses = Counter()
    all_session_profits = []
    pc_minimum = [initial_bankroll_cents] * laptop_count
    total_rounds = unfunded_days = overrun_days = 0
    maximum_overrun = 0.0
    for month in range(1, months + 1):
        bank = [initial_bankroll_cents] * laptop_count
        month_minimum = list(bank)
        closing_minimum = list(bank)
        session_closing_minimum = list(bank)
        closing_total_minimum = sum(bank)
        profits, hours = [], []
        session_profits = []
        non_target_sessions = []
        month_session_statuses = Counter()
        month_statuses = Counter()
        month_funds_days = month_skipped_sessions = 0
        for day_index in range(1, days_per_month + 1):
            before = list(bank)
            elapsed_seconds = 0.0
            day_statuses = []
            funds_stop = False
            for session_index in range(1, sessions_per_day + 1):
                remaining = 43200 - elapsed_seconds
                if remaining <= 0:
                    month_skipped_sessions += sessions_per_day - session_index + 1
                    break
                seed = f"{master}:month:{month}:day:{day_index}"
                if sessions_per_day > 1:
                    seed += f":session:{session_index}"
                session_start = sum(bank)
                session = simulate_day(seed, timing,
                                       laptop_count=laptop_count, starting_cash_cents=bank,
                                       protected=True, floor_lock=False, target_cents=target_cents,
                                       drawdown_cents=50000, deadline_seconds=remaining, round_cap=4000,
                                       picks=picks, payout_cents=payout_cents)
                bank = session["pc_final_cash_cents"]
                assert sum(bank) - session_start == round(session["profit"] * 100)
                session_profits.append(session["profit"])
                day_statuses.append(session["status"])
                session_statuses[session["status"]] += 1
                month_session_statuses[session["status"]] += 1
                if session["status"] != "target":
                    # Rare misses keep per-PC detail so cap, time and funds causes can be separated.
                    non_target_sessions.append({
                        "day": day_index, "session": session_index, "status": session["status"],
                        "profit": session["profit"], "start_hours": elapsed_seconds / 3600,
                        "hours": session["hours"], "pc_rounds": session["pc_rounds"],
                        "pc_unfunded_at_close": session["pc_unfunded_at_close"]})
                elapsed_seconds += session["hours"] * 3600
                funds_stop |= session["status"] == "insufficient_funds" or any(session["pc_unfunded_at_close"])
                total_rounds += sum(session["pc_rounds"])
                for pc in range(laptop_count):
                    month_minimum[pc] = min(month_minimum[pc], session["pc_minimum_cash_cents"][pc])
                    pc_minimum[pc] = min(pc_minimum[pc], session["pc_minimum_cash_cents"][pc])
                    session_closing_minimum[pc] = min(session_closing_minimum[pc], bank[pc])
            profit_cents = sum(bank) - sum(before)
            assert all(value >= 0 for value in bank)
            profit = profit_cents / 100
            profits.append(profit)
            hours.append(elapsed_seconds / 3600)
            day_status = ("deadline" if len(day_statuses) < sessions_per_day else
                          next((status for status in day_statuses if status != "target"), "target"))
            daily_statuses[day_status] += 1
            month_statuses[day_status] += 1
            unfunded_days += funds_stop
            month_funds_days += funds_stop
            overrun = max(0.0, elapsed_seconds - 43200)
            overrun_days += overrun > 0
            maximum_overrun = max(maximum_overrun, overrun)
            for pc in range(laptop_count):
                closing_minimum[pc] = min(closing_minimum[pc], bank[pc])
            closing_total_minimum = min(closing_total_minimum, sum(bank))
        daily_profits.extend(profits)
        daily_hours.extend(hours)
        all_session_profits.extend(session_profits)
        gross_cents = sum(bank) - laptop_count * initial_bankroll_cents
        assert gross_cents == sum(round(value * 100) for value in profits)
        assert gross_cents == sum(round(value * 100) for value in session_profits)
        gross = gross_cents / 100
        electricity = round(total_power_watts / 1000 * .30 * sum(hours), 2)
        full_weeks = [round(sum(profits[index:index + 7]), 2) for index in range(0, days_per_month - 6, 7)]
        weekly_gross.extend(full_weeks)
        monthly_rows.append({
            "month": month,
            "gross_profit": gross,
            "electricity_cost_example": electricity,
            "net_profit_after_example_electricity": round(gross - electricity, 2),
            "elapsed_hours": sum(hours),
            "negative_days": sum(value < 0 for value in profits),
            "zero_days": sum(value == 0 for value in profits),
            "worst_day": min(profits),
            "sessions_executed": len(session_profits),
            "negative_sessions": sum(value < 0 for value in session_profits),
            "worst_session": min(session_profits),
            "sessions_skipped_daily_time_budget": month_skipped_sessions,
            "session_status_counts": dict(month_session_statuses),
            "status_counts": dict(month_statuses),
            "days_with_insufficient_pc_funds": month_funds_days,
            "minimum_cash_per_pc": [value / 100 for value in month_minimum],
            "minimum_daily_closing_cash_per_pc": [value / 100 for value in closing_minimum],
            "minimum_session_closing_cash_per_pc": [value / 100 for value in session_closing_minimum],
            "minimum_daily_closing_total_cash": closing_total_minimum / 100,
            "non_target_sessions": non_target_sessions,
            "final_cash_per_pc": [value / 100 for value in bank],
            "full_weeks_with_negative_gross": sum(value < 0 for value in full_weeks),
        })
        if progress and month % 25 == 0:
            progress(month, months)
    gross_profits = [row["gross_profit"] for row in monthly_rows]
    net_profits = [row["net_profit_after_example_electricity"] for row in monthly_rows]
    negatives = sum(value < 0 for value in daily_profits)
    zeroes = sum(value == 0 for value in daily_profits)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "synthetic_uniform_independent_boards",
        "actual_autoplay_changed": False,
        "real_site_history_used": False,
        "simulation": {"independent_months": months, "days_per_month": days_per_month,
                       "laptops": laptop_count, "separate_master_pc": laptop_count > 1,
                       "initial_bankroll_per_laptop": initial_bankroll_cents / 100,
                       "stake": parallel.STAKE / 100, "difficulty": "medium", "mines": 6, "picks": picks,
                       "payout_on_win": payout_cents / 100, "multiplier": payout_cents / parallel.STAKE,
                       "sessions_per_day": sessions_per_day, "global_session_target": target_cents / 100,
                       "global_daily_target": target_cents * sessions_per_day / 100, "protected_open_stake_reservations": True,
                       "principal_floor_lock": False, "global_drawdown_limit_per_session": 500,
                       "global_daily_drawdown_limit": 500 if sessions_per_day == 1 else None,
                       "round_cap_per_session_per_pc": 4000,
                       "daily_round_cap_per_pc": 4000 * sessions_per_day, "daily_start_deadline_hours": 12,
                       "voluntary_pauses": False, "topups_inside_month": False,
                       "transfers_between_laptops": False},
        "electricity_example": {"total_power_watts": total_power_watts,
                                "powered_computer_count": laptop_count + (laptop_count > 1),
                                **({"total_power_watts_all_five_pcs": total_power_watts} if laptop_count == 4 else {}),
                                "eur_per_kwh": .30, "charged_hours": "Actual modeled daily activity including final settlements",
                                "monthly_cost_rounding": "Nearest cent once per month",
                                "hardware_power_measured": False,
                                "other_costs_included": False},
        "timing_seconds": timing,
        "method": "1,000 independent monthly replicas by default. Each replica begins once with the configured number of equal individual "
                  "balances at the configured initial capital; each next day's input is the preceding day's final individual cash in integer cents. "
                  "No cash reset, top-up or cross-PC transfer. Each session resets its target, settled drawdown and round cap "
                  "relative to that session's starting cash. All sessions share one 12-hour daily start budget; "
                  "later sessions receive only time remaining after previous sessions' elapsed time including pending drain. "
                  "Each session and PC has an independent random stream. Coordinator observes current cash after reserving all open stakes; "
                  "outcome-dependent click times drive settlements without using future outcomes in starting/stopping decisions. "
                  "Open rounds are drained after stops. Four full seven-day blocks per 30-day month are counted; final two days are excluded from week counts.",
        "summary": {
            "monthly_gross": distribution(gross_profits),
            "monthly_net_after_example_electricity": distribution(net_profits),
            "negative_gross_months": sum(value < 0 for value in gross_profits),
            "zero_gross_months": sum(value == 0 for value in gross_profits),
            "negative_net_months": sum(value < 0 for value in net_profits),
            "zero_net_months": sum(value == 0 for value in net_profits),
            "mean_monthly_electricity_cost": mean(row["electricity_cost_example"] for row in monthly_rows),
            "mean_monthly_hours": mean(row["elapsed_hours"] for row in monthly_rows),
            "daily_count": len(daily_profits), "negative_days": negatives, "zero_days": zeroes,
            "session_count": len(all_session_profits),
            "negative_sessions": sum(value < 0 for value in all_session_profits),
            "zero_sessions": sum(value == 0 for value in all_session_profits),
            "worst_session": min(all_session_profits),
            "session_status_counts": dict(session_statuses),
            "sessions_skipped_daily_time_budget": sum(row["sessions_skipped_daily_time_budget"] for row in monthly_rows),
            "negative_day_rate_percent": 100 * negatives / len(daily_profits),
            "mean_daily_gross_profit": mean(daily_profits), "worst_day": min(daily_profits),
            "mean_negative_day_profit": mean(value for value in daily_profits if value < 0) if negatives else None,
            "mean_daily_hours": mean(daily_hours), "maximum_daily_hours": max(daily_hours),
            "mean_daily_rounds_all_laptops": total_rounds / len(daily_profits),
            "minimum_cash_per_pc_including_open_stakes": [value / 100 for value in pc_minimum],
            "days_with_insufficient_pc_funds": unfunded_days,
            "months_with_insufficient_pc_funds": sum(row["days_with_insufficient_pc_funds"] > 0 for row in monthly_rows),
            "daily_status_counts": dict(daily_statuses),
            "settlement_overrun_days": overrun_days, "maximum_settlement_overrun_seconds": maximum_overrun,
            "full_week_count": len(weekly_gross), "negative_gross_weeks": sum(value < 0 for value in weekly_gross),
            "months_with_any_negative_gross_week": sum(row["full_weeks_with_negative_gross"] > 0 for row in monthly_rows),
        },
        "monthly_rows": monthly_rows,
        "limitations": ["The mathematical results rely on unverified uniform independent mine placement and the stated total payout.",
                        "Click pauses are modeled, not measured elapsed online play; setup, network delays, retries, failures and coordinator latency excluded.",
                        "Electricity is an illustrative constant total draw during modeled activity; real watts, tariff and standby behavior are not measured.",
                        "An independent monthly simulation sample does not guarantee every future month is profitable.",
                        ("The live bot currently lacks the required shared master/coordinator." if laptop_count > 1
                         else "These simulations do not configure or schedule the live bot.")],
        "runtime_seconds": time.monotonic() - started,
    }
    return report


if __name__ == "__main__":
    report = run_validation(progress=lambda done, total: print(f"Monthly carryover: {done}/{total} months", flush=True))
    path = ROOT / "bulk_results" / f"collective_monthly_validation_{datetime.now(timezone.utc):%Y%m%d_%H%M%S_%f}.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(path)
    print(json.dumps(report["summary"], indent=2))
