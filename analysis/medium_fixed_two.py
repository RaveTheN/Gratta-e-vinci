"""Research only: always open tiles 1 then 2 on fresh independent medium boards."""

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import json
import time
from unittest.mock import patch

try:
    from . import collective_parallel as parallel
    from . import medium_two_sessions as two
    from .medium_two_verification import observed
except ImportError:
    import collective_parallel as parallel
    import medium_two_sessions as two
    from medium_two_verification import observed


FIXED_CELLS = (0, 1)


def fixed_board_round(rng, picks=2):
    if picks != 2:
        raise ValueError("This experiment always opens exactly two fixed tiles")
    mines = rng.sample(range(25), 6)
    for opened, cell in enumerate(FIXED_CELLS, 1):
        if cell in mines:
            return opened, False
    return 2, True


def run_chunk(months):
    assert two.run_validation.__globals__["simulate_day"].__globals__ is vars(parallel)
    with patch.object(parallel, "sample_round", fixed_board_round):
        return two.run_chunk((months, 4, 2, 240))


def run_research(months=1000, workers=4):
    if any(type(value) is not int or value < 1 for value in (months, workers)):
        raise ValueError("Positive integer month and worker counts required")
    started = time.monotonic()
    counts = [months // workers + (index < months % workers) for index in range(workers)]
    print(f"Fixed tiles 1 then 2: {months} fresh months, {workers} workers", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as executor:
        chunks = list(executor.map(run_chunk, [count for count in counts if count]))
    rows = [dict(row) for chunk in chunks for row in chunk["monthly_rows"]]
    for index, row in enumerate(rows, 1):
        row["month"] = index
        assert sum(round(value * 100) for value in row["final_cash_per_pc"]) - 8000 == round(row["gross_profit"] * 100)
        assert row["electricity_cost_example"] == round(.240 * .30 * row["elapsed_hours"], 2)
    result = observed(chunks)
    assert result["months"]["count"] == months
    assert result["days"]["count"] == months * 30
    assert result["sessions"]["planned"] == months * 60
    assert result["sessions"]["executed"] + sum(row["sessions_skipped_daily_time_budget"] for row in rows) == months * 60
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "script": "analysis/medium_fixed_two.py",
        "source": "fresh_synthetic_complete_uniform_independent_boards",
        "real_games_started": False, "gui_settings_or_live_bot_changed": False,
        "previous_reports_reused_as_samples": False, "workers": workers,
        "simulation": {**chunks[0]["simulation"], "independent_months": months,
                       "selected_tiles_1_based_in_order": [cell + 1 for cell in FIXED_CELLS]},
        "board_method": "Before opening any tile, sample six distinct mine positions uniformly from all 25 cells. "
                        "Open tile 1 and, only if safe, tile 2. Every round and laptop receives its own fresh board "
                        "from its independent stream; fixed tile choices do not mean shared boards. No outcome-CDF sampler is used.",
        "timing_seconds": chunks[0]["timing_seconds"],
        "observed_simulation": result,
        "total_board_rounds": round(sum(chunk["summary"]["mean_daily_rounds_all_laptops"] *
                                         chunk["summary"]["daily_count"] for chunk in chunks)),
        "minimum_session_closing_cash_per_pc": [min(row["minimum_session_closing_cash_per_pc"][pc] for row in rows)
                                                for pc in range(4)],
        "electricity_example": chunks[0]["electricity_example"],
        "limitations": chunks[0]["limitations"],
        "monthly_rows": rows,
        "runtime_seconds": time.monotonic() - started,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--months", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    report = run_research(args.months, args.workers)
    directory = parallel.ROOT / "bulk_results"
    directory.mkdir(exist_ok=True)
    path = directory / f"medium_fixed_two_{datetime.now(timezone.utc):%Y%m%d_%H%M%S_%fZ}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
    print("Report:", path, flush=True)
    print(json.dumps({key: value for key, value in report["observed_simulation"].items()
                      if key != "laptops"}, indent=2), flush=True)
    print("Runtime seconds:", report["runtime_seconds"], flush=True)
