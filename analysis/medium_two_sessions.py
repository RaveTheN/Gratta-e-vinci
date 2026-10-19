"""Two daily +3 EUR sessions share cash and one 12-hour start budget."""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import json
import time

try:
    from .collective_parallel import ROOT
    from .collective_validation import run_validation
    from .medium_bankroll import combine
except ImportError:
    from collective_parallel import ROOT
    from collective_validation import run_validation
    from medium_bankroll import combine


FOUR_LAPTOP_REPORT = "medium_two_sessions_20261014_185618_103144Z.json"


def run_chunk(arguments):
    months, laptop_count, sessions_per_day, total_power_watts = arguments
    return run_validation(months=months, picks=2, payout_cents=18,
                          initial_bankroll_cents=2000, sessions_per_day=sessions_per_day,
                          laptop_count=laptop_count, total_power_watts=total_power_watts)


def run_research(months=3000, workers=4, laptop_count=4, sessions_per_day=2, total_power_watts=240):
    if type(months) is not int or months < 1 or type(workers) is not int or workers < 1:
        raise ValueError("Positive integer month and worker counts required")
    started = time.monotonic()
    counts = [months // workers + (index < months % workers) for index in range(workers)]
    print(f"{laptop_count} laptop(s), {sessions_per_day} session(s)/day: {months} fresh months, {workers} workers", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as executor:
        chunks = list(executor.map(run_chunk, [(count, laptop_count, sessions_per_day, total_power_watts)
                                               for count in counts if count]))
    result = combine(chunks)
    rows = result["monthly_rows"]
    statuses = Counter()
    for row in rows:
        statuses.update(row["session_status_counts"])
    result.update(
        sessions=sum(row["sessions_executed"] for row in rows),
        negative_sessions=sum(row["negative_sessions"] for row in rows),
        worst_session=min(row["worst_session"] for row in rows),
        sessions_skipped_daily_time_budget=sum(row["sessions_skipped_daily_time_budget"] for row in rows),
        session_status_counts=dict(statuses),
        maximum_daily_hours=max(chunk["summary"]["maximum_daily_hours"] for chunk in chunks),
        settlement_overrun_days=sum(chunk["summary"]["settlement_overrun_days"] for chunk in chunks),
        maximum_settlement_overrun_seconds=max(chunk["summary"]["maximum_settlement_overrun_seconds"] for chunk in chunks),
        mean_daily_rounds_all_laptops=sum(
            chunk["summary"]["mean_daily_rounds_all_laptops"] * chunk["summary"]["daily_count"] for chunk in chunks) / result["days"],
        minimum_session_closing_cash_per_pc=[
            min(row["minimum_session_closing_cash_per_pc"][pc] for row in rows) for pc in range(laptop_count)],
    )
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "fresh_synthetic_uniform_independent_boards", "actual_autoplay_changed": False,
        "real_site_history_used": False, "workers": workers,
        "method": "Fresh independent 30-day monthly replicas at the stated laptop/session count. Each session has its own "
                  "+3 EUR cash-reserved target, 500 EUR settled drawdown limit and 4000-bet cap per PC. "
                  "If another session is scheduled, it starts immediately after the first drains and uses only the remainder "
                  "of the same 43200-second daily budget. No account resets, replenishment, transfers, "
                  "withdrawals or voluntary waits. Already open rounds may settle after the daily start deadline.",
        "comparison": {"four_laptop_two_session_reference_report": FOUR_LAPTOP_REPORT,
                       "samples_are_paired": False,
                       "label": "Prior independent 3000-month four-laptop/two-session sample; current laptop/session counts are stated in simulation metadata. No division or multiplication of prior profits."},
        "result": result,
        "electricity_example": chunks[0]["electricity_example"],
        "limitations": chunks[0]["limitations"],
        "runtime_seconds": time.monotonic() - started,
    }


if __name__ == "__main__":
    report = run_research()
    directory = ROOT / "bulk_results"
    directory.mkdir(exist_ok=True)
    path = directory / f"medium_two_sessions_{datetime.now(timezone.utc):%Y%m%d_%H%M%S_%fZ}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
    print("Report:", path, flush=True)
    print(json.dumps({key: value for key, value in report["result"].items() if key != "monthly_rows"}, indent=2), flush=True)
