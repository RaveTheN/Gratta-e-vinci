"""Compare four confirmed medium payments using fresh 30-day bankroll replicas."""

import argparse
from datetime import datetime, timezone
import json
import math
import time

try:
    from .collective_parallel import ROOT, STAKE
    from .collective_validation import run_validation
except ImportError:
    from collective_parallel import ROOT, STAKE
    from collective_validation import run_validation


CASES = ((2, 18), (6, 68), (7, 100), (8, 150))


def run_comparison(months=1000, progress=None):
    if type(months) is not int or months < 1:
        raise ValueError("months must be a positive integer")
    started = time.monotonic()
    cases = {}
    for picks, payout_cents in CASES:
        if progress:
            progress(picks, 0, months)
        report = run_validation(months=months, days_per_month=30, picks=picks,
                                payout_cents=payout_cents,
                                progress=(lambda done, total: progress(picks, done, total)) if progress else None)
        if cases:
            assert report["timing_seconds"] == next(iter(cases.values()))["timing_seconds"]
        probability = math.comb(19, picks) / math.comb(25, picks)
        report["mathematics"] = {
            "win_probability": probability,
            "expected_profit_per_bet_before_energy": (probability * payout_cents - STAKE) / 100,
            "expected_return_percent_of_stake": 100 * probability * payout_cents / STAKE,
        }
        cases[str(picks)] = report
        summary = report["summary"]
        print(f"Completed {picks} picks: {months} fresh months, "
              f"gross mean {summary['monthly_gross']['mean']:.2f} EUR, "
              f"net mean {summary['monthly_net_after_example_electricity']['mean']:.2f} EUR, "
              f"negative gross/net months {summary['negative_gross_months']}/{summary['negative_net_months']}, "
              f"runtime {report['runtime_seconds']:.1f}s", flush=True)
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "fresh_synthetic_uniform_independent_boards",
        "actual_autoplay_changed": False,
        "real_site_history_used": False,
        "months_per_case": months,
        "days_per_case": 30 * months,
        "cases_declared_before_sampling": [{"picks": picks, "payout_cents": payout} for picks, payout in CASES],
        "sampling": "Fresh independent monthly replicas for every case; all cases use the same count, "
                    "controller, bankroll, limits and timing. No previous reports are reused and no rules "
                    "are adjusted from observed results. A monthly replica carries its four individual "
                    "balances across 30 days without resets, transfers or replenishment.",
        "payment_source": "User-confirmed total winning payments for a 0.10 EUR stake, medium difficulty with six mines.",
        "cases": cases,
        "runtime_seconds": time.monotonic() - started,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--months", type=int, default=1000, choices=(500, 1000))
    args = parser.parse_args()
    report = run_comparison(args.months, progress=lambda picks, done, total:
        print(f"Medium {picks} picks: {done}/{total} months", flush=True))
    directory = ROOT / "bulk_results"
    directory.mkdir(exist_ok=True)
    path = directory / f"medium_monthly_comparison_{datetime.now(timezone.utc):%Y%m%d_%H%M%S_%fZ}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
    print(f"Report: {path}", flush=True)


if __name__ == "__main__":
    main()
