"""Adverse tests for four simulated PCs and an ordinary protected +3 EUR stop."""

from contextlib import ExitStack
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import secrets
from statistics import mean
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis import collective_parallel as parallel
from bulk_simulation import wilson_interval


def stress_case(timing, days, delay_factor=1, payout_cents=68, correlated=False):
    if type(days) is not int or days < 1:
        raise ValueError("days must be a positive integer")
    waits = {key: value * delay_factor for key, value in timing.items()}
    stream, rows = secrets.randbits(128), []
    original_random = parallel.random.Random
    with ExitStack() as scope:
        scope.enter_context(patch.object(parallel, "PAYOUT", payout_cents))
        if correlated:
            scope.enter_context(patch.object(parallel.random, "Random", side_effect=
                lambda seed: original_random(seed.rsplit(":laptop:", 1)[0])))
        for day in range(days):
            rows.append(parallel.simulate_day(f"{stream}:day:{day}", waits,
                                             protected=True, floor_lock=False, laptop_count=4))
            if (day + 1) % 500 == 0:
                print(f"Delay x{delay_factor}, payout {payout_cents}, correlated {correlated}: "
                      f"{day + 1}/{days}", flush=True)
    summary = parallel.summarize(rows)
    summary["negative_ci_low"], summary["negative_ci_high"] = wilson_interval(summary["negative_days"], days)
    net_profits = [row["profit"] - .240 * .30 * row["hours"] for row in rows]
    net_negatives = sum(profit < 0 for profit in net_profits)
    low, high = wilson_interval(net_negatives, days)
    net = {
        "average_profit": mean(net_profits), "worst_profit": min(net_profits),
        "negative_days": net_negatives, "zero_days": sum(profit == 0 for profit in net_profits),
        "negative_rate_percent": 100 * net_negatives / days,
        "negative_ci_low": low, "negative_ci_high": high,
        "average_energy_cost": mean(.240 * .30 * row["hours"] for row in rows),
        "mean_30_day_profit_from_daily_average": 30 * mean(net_profits),
    }
    win_probability = math.comb(19, 6) / math.comb(25, 6)
    return {
        "days": days, "delay_factor": delay_factor, "payout_cents": payout_cents,
        "perfectly_correlated_pc_worlds": correlated,
        "expected_net_per_bet_before_energy": (win_probability * payout_cents - parallel.STAKE) / 100,
        "timing_seconds": waits, "gross": summary, "after_energy": net,
        "mean_30_day_gross_profit_from_daily_average": 30 * summary["average_profit"],
    }


def all_red_case(timing):
    with patch.object(parallel, "sample_round", return_value=(1, False)):
        day = parallel.simulate_day("all-red-adverse-case", timing,
                                    protected=True, floor_lock=False, laptop_count=4)
    assert day["status"] == "drawdown"
    assert -500.40 <= day["profit"] <= -500
    assert sum(day["pc_rounds"]) <= 16000
    assert max(day["pc_rounds"]) <= 4000
    assert min(day["pc_minimum_cash"]) >= 0
    assert math.isclose(sum(day["pc_final_cash"]) - 4000, day["profit"], abs_tol=1e-9)
    return day


def main():
    started = time.monotonic()
    settings = json.loads((ROOT / "gratta_settings.json").read_text(encoding="utf-8"))
    timing = parallel.timing_from_settings(settings)
    cases = (("baseline", 1, 68, False),
             ("all_delays_x2", 2, 68, False),
             ("all_delays_x4", 4, 68, False),
             ("payout_67_cents", 1, 67, False),
             ("payout_66_cents", 1, 66, False),
             ("payout_65_cents", 1, 65, False),
             ("perfectly_correlated_pcs", 1, 68, True))
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "synthetic_uniform_boards_with_explicit_adverse_cases",
        "actual_autoplay_changed": False, "real_history_used": False,
        "configuration": {"laptops": 4, "bankroll_per_laptop": 1000, "stake": .1,
                          "medium_mines": 6, "picks": 6, "confirmed_total_multiplier": 6.8,
                          "global_target": 3, "settled_drawdown_limit": 500,
                          "deadline_hours": 12, "round_cap_per_laptop": 4000,
                          "protected_target": True, "floor_lock": False},
        "energy": {"total_power_watts": 240, "computers": 5,
                   "composition": "Four laptops plus one separate master computer.",
                   "tariff_eur_per_kwh": .30,
                   "method": "240 W total for the simulated elapsed day, including pending drain. "
                             "The tariff is an illustrative assumption, not a verified energy bill."},
        "method": "Cases fixed before outcomes; fresh independent daily streams for every case. "
                  "All timing waits are scaled together. Alternate payouts preserve the 10-cent stake "
                  "and six-pick probability. Correlation deliberately gives distinct PC RNG objects "
                  "the same seed, producing copied worlds; it is not the default model or a claim "
                  "about real-site correlation. Global patches are scoped and restored after each case.",
        "limitations": ["A 1000-day sample is weak evidence for rare losses; Wilson intervals are reported.",
                        "Coordinator latency, faults and one-PC-specific slowness are not modeled.",
                        "The coordinator is absent from the live bot; no guarantee of real-site payouts or independence.",
                        "Times are simulated, not measured on the site; pending rounds may settle after 12 hours.",
                        "Monthly figures are daily means multiplied by 30, not month or carryover simulations."],
        "cases": {},
    }
    for name, factor, payout, correlated in cases:
        result = stress_case(timing, 1000, factor, payout, correlated)
        report["cases"][name] = result
        print(f"{name}: mean gross {result['gross']['average_profit']:.4f} EUR, "
              f"mean after energy {result['after_energy']['average_profit']:.4f} EUR", flush=True)
    report["all_red_adverse_case"] = all_red_case(timing)
    report["runtime_seconds"] = time.monotonic() - started
    output_dir = ROOT / "bulk_results"
    output_dir.mkdir(exist_ok=True)
    path = output_dir / f"collective_stress_{datetime.now(timezone.utc):%Y%m%d_%H%M%S_%fZ}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
    print(f"Report: {path}", flush=True)


if __name__ == "__main__":
    main()
