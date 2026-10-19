"""Size medium two-cell cash without live play, transfers or replenishment."""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import json
import math
import secrets
from statistics import mean
import time
from unittest.mock import patch

try:
    from . import collective_validation as validation
    from .collective_parallel import BANKROLL, ROOT, STAKE
except ImportError:
    import collective_validation as validation
    from collective_parallel import BANKROLL, ROOT, STAKE


GRID_CENTS = (10, 100, 200, 500, 1000, 1500, 2000, 3000)
SELECTED_CENTS = 2000


def required_capital_cents(month, initial_cents=BANKROLL):
    """Exact equal-cash threshold to replay this funded month and fund every close."""
    reserved = [round(value * 100) for value in month["minimum_cash_per_pc"]]
    closing = [round(value * 100) for value in month["minimum_daily_closing_cash_per_pc"]]
    return max([STAKE] + [initial_cents - value for value in reserved]
               + [initial_cents + STAKE - value for value in closing])


def mathematical_bound(capital_eur):
    # Solve .57*exp(-r*.08) + .43*exp(r*.10) = 1 for its positive root.
    low, high = .01, 2.0
    for _ in range(60):
        middle = (low + high) / 2
        if .57 * math.exp(-middle * .08) + .43 * math.exp(middle * .10) > 1:
            high = middle
        else:
            low = middle
    rate = (low + high) / 2
    return {"adjustment_rate_per_eur": rate,
            "any_of_four_unfunded_ever_upper_probability": min(1, 4 * math.exp(-rate * (capital_eur - .10))),
            "assumptions": "Independent uniform boards, exact .18 total win payment, .10 stake, "
                           "no fees, withdrawals, top-ups or inter-PC transfers. Stopping future bets "
                           "can only reduce the probability of ever falling below one stake."}


def run_chunk(arguments):
    months, capital_cents, stream = arguments
    # Research-only shared streams pair capitals; the global patch stays inside this worker.
    with patch.object(validation.secrets, "randbits", return_value=stream):
        return validation.run_validation(months=months, picks=2, payout_cents=18,
                                         initial_bankroll_cents=capital_cents)


def combine(chunks):
    rows = [dict(row) for chunk in chunks for row in chunk["monthly_rows"]]
    for number, row in enumerate(rows, 1):
        row["month"] = number
    statuses = Counter()
    for chunk in chunks:
        statuses.update(chunk["summary"]["daily_status_counts"])
    gross = [row["gross_profit"] for row in rows]
    net = [row["net_profit_after_example_electricity"] for row in rows]
    initial_cents = round(chunks[0]["simulation"]["initial_bankroll_per_laptop"] * 100)
    laptop_count = chunks[0]["simulation"]["laptops"]
    return {
        "simulation": {**chunks[0]["simulation"], "independent_months": len(rows)},
        "timing_seconds": chunks[0]["timing_seconds"],
        "months": len(rows), "days": sum(chunk["summary"]["daily_count"] for chunk in chunks),
        "monthly_gross": validation.distribution(gross),
        "monthly_net_after_example_electricity": validation.distribution(net),
        "negative_gross_months": sum(value < 0 for value in gross),
        "negative_net_months": sum(value < 0 for value in net),
        "months_with_any_pc_unfunded": sum(row["days_with_insufficient_pc_funds"] > 0 for row in rows),
        "months_any_pc_finishes_below_initial": sum(
            any(round(value * 100) < initial_cents for value in row["final_cash_per_pc"]) for row in rows),
        "months_finishing_below_initial_per_pc": [
            sum(round(row["final_cash_per_pc"][pc] * 100) < initial_cents for row in rows) for pc in range(laptop_count)],
        "negative_days": sum(row["negative_days"] for row in rows),
        "worst_day": min(row["worst_day"] for row in rows),
        "mean_daily_minutes": 60 * mean(row["elapsed_hours"] for row in rows) / chunks[0]["simulation"]["days_per_month"],
        "mean_monthly_electricity_example": mean(row["electricity_cost_example"] for row in rows),
        "minimum_cash_per_pc_including_open_stakes": [
            min(row["minimum_cash_per_pc"][pc] for row in rows) for pc in range(laptop_count)],
        "minimum_daily_closing_cash_per_pc": [
            min(row["minimum_daily_closing_cash_per_pc"][pc] for row in rows) for pc in range(laptop_count)],
        "daily_status_counts": dict(statuses), "monthly_rows": rows,
    }


def run_research(baseline_months=2000, grid_months=250, holdout_months=3000, workers=4):
    for count in (baseline_months, grid_months, holdout_months, workers):
        if type(count) is not int or count < 1:
            raise ValueError("Positive integer counts required")
    started = time.monotonic()
    print(f"Baseline: {baseline_months} fresh funded months, {workers} workers", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as executor:
        counts = [baseline_months // workers + (index < baseline_months % workers)
                  for index in range(workers)]
        baseline = combine(list(executor.map(run_chunk, [(count, BANKROLL, secrets.randbits(128))
                            for count in counts if count])))
        assert baseline["months_with_any_pc_unfunded"] == 0
        thresholds = [required_capital_cents(month) for month in baseline["monthly_rows"]]
        paired_grid = [{"capital_per_laptop": cents / 100,
                        "months_with_any_pc_unfunded": sum(required > cents for required in thresholds),
                        "months": baseline_months} for cents in GRID_CENTS]
        print("Funded-path paired grid:", paired_grid, flush=True)
        stream = secrets.randbits(128)
        print(f"Direct paired grid: {grid_months} new months per capital", flush=True)
        grid_chunks = list(executor.map(run_chunk, [(grid_months, cents, stream) for cents in GRID_CENTS]))
        direct_grid = {str(cents): combine([chunk]) for cents, chunk in zip(GRID_CENTS, grid_chunks)}
        reference = direct_grid[str(GRID_CENTS[-1])]
        assert reference["months_with_any_pc_unfunded"] == 0
        reference_thresholds = [required_capital_cents(month, GRID_CENTS[-1])
                                for month in reference["monthly_rows"]]
        for cents, result in zip(GRID_CENTS, grid_chunks):
            actual = [row["days_with_insufficient_pc_funds"] > 0 for row in result["monthly_rows"]]
            expected = [required > cents for required in reference_thresholds]
            assert actual == expected
        print("Direct grid independently matches every paired funded-path classification", flush=True)
        # Twenty euros is frozen from the 99.99% mathematical all-four operating criterion.
        print(f"Holdout: {holdout_months} fresh months at {SELECTED_CENTS / 100:.2f} EUR per laptop", flush=True)
        counts = [holdout_months // workers + (index < holdout_months % workers)
                  for index in range(workers)]
        holdout = combine(list(executor.map(run_chunk, [(count, SELECTED_CENTS, secrets.randbits(128))
                           for count in counts if count])))
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "fresh_synthetic_uniform_independent_boards", "actual_autoplay_changed": False,
        "real_site_history_used": False, "workers": workers,
        "configuration": {"laptops": 4, "separate_master_pc": True, "stake_eur": .10,
                          "payout_on_win_eur": .18, "picks": 2, "medium_mines": 6,
                          "days_per_month": 30, "global_target_eur": 3, "global_drawdown_eur": 500,
                          "round_cap_per_laptop_per_day": 4000, "start_deadline_hours": 12,
                          "pending_stakes_reserved": True, "principal_floor_lock": False,
                          "topups": False, "transfers": False, "withdrawals": False},
        "criterion": "An operating month requires all four PCs to finish every day with at least .10 EUR. "
                     "Any PC below one stake at a daily close counts as an interrupted month, even if group profit is positive.",
        "threshold_method": "For each fully funded reference month, equal initial cents B preserve every start "
                            "and outcome until an account becomes unfunded. The exact needed B is the maximum "
                            "of 10 cents, initial-reference cents minus each reserved-cash minimum, and "
                            "initial-reference cents plus 10 minus each daily-closing minimum. Classification "
                            "is checked against direct same-world runs at all eight capitals; reference profit "
                            "is not extrapolated to unfunded lower-capital worlds.",
        "selected_capital_per_laptop": SELECTED_CENTS / 100,
        "selection_basis": "Fixed 20 EUR before holdout; first grid amount meeting the mathematical 99.99% "
                           "all-four operating bound. This is a practical capital, not an absolute guarantee or "
                           "a minimum accepted by the website.",
        "mathematical_bounds": {str(cents): mathematical_bound(cents / 100) for cents in GRID_CENTS},
        "baseline": baseline, "baseline_required_equal_capital_cents": thresholds,
        "paired_grid": paired_grid, "direct_grid": direct_grid, "independent_holdout": holdout,
        "electricity_example": {"watts_all_five_pcs": 240, "eur_per_kwh": .30,
                                "hardware_power_measured": False, "other_costs_included": False},
        "limitations": ["Uniform independent mine placement and winning payment are assumed, not verified on the site.",
                        "Real network delays, coordinator faults, retries, fees and withdrawals are not modeled.",
                        "Direct interrupted-month rows continue the remaining funded PCs; their profit is not a full four-PC operating month.",
                        "The holdout is finite; zero sampled failures does not establish zero future risk.",
                        "The master/coordinator remains simulated and is absent from the live bot."],
        "runtime_seconds": time.monotonic() - started,
    }


if __name__ == "__main__":
    report = run_research()
    directory = ROOT / "bulk_results"
    directory.mkdir(exist_ok=True)
    path = directory / f"medium_two_bankroll_{datetime.now(timezone.utc):%Y%m%d_%H%M%S_%fZ}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
    print("Report:", path, flush=True)
    print("Holdout:", json.dumps({key: value for key, value in report["independent_holdout"].items()
                                 if key != "monthly_rows"}, indent=2), flush=True)
