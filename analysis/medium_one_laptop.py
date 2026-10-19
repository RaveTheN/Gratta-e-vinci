"""Fresh single-laptop sessions, same +3 EUR stop and total 12-hour daily budget."""

from datetime import datetime, timezone
import json
import time

try:
    from .collective_parallel import ROOT
    from .medium_two_sessions import run_research as run_case
except ImportError:
    from collective_parallel import ROOT
    from medium_two_sessions import run_research as run_case


def run_research(months=3000, workers=4, include_one_session=True):
    started = time.monotonic()
    cases = {}
    for sessions in ((2, 1) if include_one_session else (2,)):
        case = run_case(months=months, workers=workers, laptop_count=1,
                        sessions_per_day=sessions, total_power_watts=50)
        case.pop("comparison")
        cases[str(sessions)] = case
        summary = case["result"]
        print(f"Completed one laptop/{sessions} session(s): monthly net mean "
              f"{summary['monthly_net_after_example_electricity']['mean']:.2f} EUR, "
              f"negative months {summary['negative_net_months']}, "
              f"negative sessions/days {summary['negative_sessions']}/{summary['negative_days']}, "
              f"case runtime {case['runtime_seconds']:.1f}s", flush=True)
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "fresh_synthetic_uniform_independent_boards", "actual_autoplay_changed": False,
        "real_site_history_used": False,
        "cases": cases,
        "comparison": {"four_laptop_two_session_reference_report": "medium_two_sessions_20261014_185618_103144Z.json",
                       "samples_are_paired": False,
                       "label": "Fresh one-laptop samples with their own round capacity and timing; prior four-laptop sample is an independent reference, not divided by four."},
        "runtime_seconds": time.monotonic() - started,
    }


if __name__ == "__main__":
    report = run_research()
    directory = ROOT / "bulk_results"
    directory.mkdir(exist_ok=True)
    path = directory / f"medium_one_laptop_{datetime.now(timezone.utc):%Y%m%d_%H%M%S_%fZ}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
    print("Report:", path, flush=True)
