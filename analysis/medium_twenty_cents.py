"""Research only: 0.20 EUR stakes, 0.36 EUR total wins, two daily group targets."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import json
import secrets
import time
from unittest.mock import patch

try:
    from . import collective_parallel as parallel
    from . import collective_validation as validation
    from .medium_two_verification import observed
except ImportError:
    import collective_parallel as parallel
    import collective_validation as validation
    from medium_two_verification import observed


def run_chunk(arguments):
    months, seed, initial_bankroll_cents, target_cents = arguments
    # Scope the research stake to this worker; the live bot and default remain unchanged.
    with patch.object(parallel, "STAKE", 20), patch.object(validation.secrets, "randbits", return_value=seed):
        return validation.run_validation(months=months, days_per_month=30, picks=2, payout_cents=36,
                                         initial_bankroll_cents=initial_bankroll_cents, sessions_per_day=2,
                                         laptop_count=4, total_power_watts=240, target_cents=target_cents)


def run_research(months=3000, workers=4, initial_bankroll_cents=2000, target_cents=300):
    if any(type(value) is not int or value < 1 for value in (months, workers)):
        raise ValueError("Positive integer month and worker counts required")
    if type(initial_bankroll_cents) is not int or initial_bankroll_cents < 0:
        raise ValueError("initial_bankroll_cents must be a nonnegative integer")
    if type(target_cents) is not int or target_cents <= 0:
        raise ValueError("target_cents must be a positive integer")
    started = time.monotonic()
    counts = [months // workers + (index < months % workers) for index in range(workers)]
    jobs = [(count, secrets.randbits(128), initial_bankroll_cents, target_cents) for count in counts if count]
    assert len({job[1] for job in jobs}) == len(jobs)
    print(f"0.20 EUR stake, {initial_bankroll_cents / 100:g} EUR per laptop, "
          f"two +{target_cents / 100:g} EUR sessions: {months} fresh months, {workers} workers", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as executor:
        chunks = list(executor.map(run_chunk, jobs))
    rows = [dict(row) for chunk in chunks for row in chunk["monthly_rows"]]
    for chunk in chunks:
        plan = chunk["simulation"]
        assert (plan["stake"], plan["payout_on_win"], plan["picks"], plan["multiplier"],
                plan["initial_bankroll_per_laptop"], plan["sessions_per_day"], plan["laptops"],
                plan["global_session_target"]) == (.2, .36, 2, 1.8, initial_bankroll_cents / 100, 2, 4, target_cents / 100)
        assert chunk["timing_seconds"] == chunks[0]["timing_seconds"]
    for number, row in enumerate(rows, 1):
        row["month"] = number
        assert sum(round(value * 100) for value in row["final_cash_per_pc"]) - 4 * initial_bankroll_cents == round(row["gross_profit"] * 100)
        assert row["electricity_cost_example"] == round(.240 * .30 * row["elapsed_hours"], 2)
        assert min(row["minimum_cash_per_pc"]) >= 0
    result = observed(chunks)
    assert result["months"]["count"] == months
    assert result["sessions"]["executed"] + sum(row["sessions_skipped_daily_time_budget"] for row in rows) == months * 60
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "script": "analysis/medium_twenty_cents.py",
        "source": "fresh_synthetic_uniform_independent_boards",
        "real_games_started": False, "gui_settings_or_live_bot_changed": False,
        "previous_reports_reused_as_samples": False, "workers": workers,
        "independent_seed_chunks": [{"months": job[0], "seed": job[1]} for job in jobs],
        "simulation": {**chunks[0]["simulation"], "independent_months": months},
        "method": chunks[0]["method"],
        "timing_seconds": chunks[0]["timing_seconds"],
        "theoretical_calculations": {
            "win_probability": .57, "loss_probability": .43,
            "total_win_payment_eur": .36, "net_win_eur": .16, "net_loss_eur": -.20,
            "expected_profit_per_game_eur": .0052,
            "return_to_player_percent": 102.6,
            "fair_total_win_payment_eur": .20 / .57,
            "initial_stakes_available_per_laptop": initial_bankroll_cents // 20,
            "session_target_eur": target_cents / 100,
        },
        "observed_simulation": result,
        "electricity_example": chunks[0]["electricity_example"],
        "limitations": chunks[0]["limitations"] + [
            "The assumed 0.36 EUR total payment at a 0.20 EUR stake has not been verified on the site.",
            "Zero observed losses do not mean zero risk; a day can still finish below the initial group capital.",
            "Out-of-funds means a laptop has less than 0.20 EUR after settling its own bet, even when the group has money.",
        ],
        "monthly_rows": rows,
        "runtime_seconds": time.monotonic() - started,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capital-cents", type=int, default=2000)
    parser.add_argument("--target-cents", type=int, default=300)
    args = parser.parse_args()
    report = run_research(initial_bankroll_cents=args.capital_cents, target_cents=args.target_cents)
    directory = parallel.ROOT / "bulk_results"
    directory.mkdir(exist_ok=True)
    path = directory / f"medium_twenty_cents_{datetime.now(timezone.utc):%Y%m%d_%H%M%S_%fZ}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
    print("Report:", path, flush=True)
    print(json.dumps(report["observed_simulation"], indent=2), flush=True)
    print("Runtime seconds:", report["runtime_seconds"], flush=True)
