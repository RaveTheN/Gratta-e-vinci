"""Research only: configurable mines, two cells, four 20 EUR laptops, two +3 EUR trigger stops."""

from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from fractions import Fraction
import json
import math
import secrets
import time
from unittest.mock import patch

from . import collective_parallel as parallel
from . import collective_validation as validation
from .medium_two_verification import observed


SAFE_PREFIXES = [math.comb(18, picks) / math.comb(25, picks) for picks in range(1, 9)]


def simulate_millieuro_session(seed, timing, **kwargs):
    kwargs["drawdown_cents"] *= 10
    return parallel.simulate_day(seed, timing, **kwargs)


def run_chunk(arguments):
    months, seed, payout_millieuro, mines = arguments
    # The existing event coordinator checks reserved cash after every observed settlement.
    # Scale its integer cent ledger by ten so 0.184 EUR remains exact throughout the month.
    prefixes = [math.comb(25 - mines, picks) / math.comb(25, picks) for picks in range(1, 9)]
    with patch.object(parallel, "SAFE_PREFIXES", prefixes), \
         patch.object(parallel, "STAKE", 100), \
         patch.object(validation, "simulate_day", simulate_millieuro_session), \
         patch.object(validation.secrets, "randbits", return_value=seed):
        result = validation.run_validation(months=months, days_per_month=30, picks=2, payout_cents=payout_millieuro,
                                           initial_bankroll_cents=20000, sessions_per_day=2,
                                           laptop_count=4, target_cents=3000, total_power_watts=240)
    for row in result["monthly_rows"]:
        for key in ("gross_profit", "worst_day", "worst_session", "minimum_daily_closing_total_cash"):
            row[key] = round(row[key] / 10, 3)
        for key in ("minimum_cash_per_pc", "minimum_daily_closing_cash_per_pc",
                    "minimum_session_closing_cash_per_pc", "final_cash_per_pc"):
            row[key] = [round(value / 10, 3) for value in row[key]]
        for entry in row["non_target_sessions"]:
            entry["profit"] = round(entry["profit"] / 10, 3)
        row["net_profit_after_example_electricity"] = round(row["gross_profit"] - row["electricity_cost_example"], 3)
    summary = result["summary"]
    for key in ("mean_daily_gross_profit", "worst_day", "worst_session", "mean_negative_day_profit"):
        if summary[key] is not None:
            summary[key] /= 10
    summary["minimum_cash_per_pc_including_open_stakes"] = [
        round(value / 10, 3) for value in summary["minimum_cash_per_pc_including_open_stakes"]]
    summary["monthly_gross"] = validation.distribution([row["gross_profit"] for row in result["monthly_rows"]])
    nets = [row["net_profit_after_example_electricity"] for row in result["monthly_rows"]]
    summary["monthly_net_after_example_electricity"] = validation.distribution(nets)
    summary["negative_net_months"] = sum(value < 0 for value in nets)
    summary["zero_net_months"] = sum(value == 0 for value in nets)
    for key in ("stake", "payout_on_win", "initial_bankroll_per_laptop", "global_session_target", "global_daily_target"):
        result["simulation"][key] = round(result["simulation"][key] / 10, 3)
    result["simulation"].update(mines=mines, cells=25, difficulty="custom", stop_policy="cash_reserved_trigger",
                                batch_size_per_laptop=None, money_unit_eur=.001, payout_rounding="none")
    plan = result["simulation"]
    assert (plan["stake"], plan["payout_on_win"], plan["picks"], plan["laptops"],
            plan["sessions_per_day"], plan["initial_bankroll_per_laptop"],
            plan["global_session_target"]) == (.1, payout_millieuro / 1000, 2, 4, 2, 20, 3)
    return result


def run_research(months=3000, workers=4, payout_millieuro=180, mines=7):
    if any(type(value) is not int or value < 1 for value in (months, workers, payout_millieuro)):
        raise ValueError("Positive integer month, worker and millieuro payout counts required")
    if type(mines) is not int or not 0 <= mines <= 23:
        raise ValueError("Integer mine count from 0 to 23 required for two safe cells")
    started = time.monotonic()
    counts = [months // workers + (index < months % workers) for index in range(workers)]
    jobs = [(count, secrets.randbits(128), payout_millieuro, mines) for count in counts if count]
    assert len({seed for _, seed, _, _ in jobs}) == len(jobs)
    print(f"{mines} mines, {payout_millieuro / 1000:g} EUR total payment, reserved-cash trigger: {months} fresh months", flush=True)
    chunks = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        for chunk in executor.map(run_chunk, jobs):
            chunks.append(chunk)
            print(f"Completed {sum(len(c['monthly_rows']) for c in chunks)}/{months} months", flush=True)
    summary = observed(chunks, units_per_eur=1000)
    summary["sessions"].pop("not_reaching_session_target_detail")
    rows = [row for chunk in chunks for row in chunk["monthly_rows"]]
    for number, row in enumerate(rows, 1):
        row["month"] = number
        assert sum(round(c * 1000) for c in row["final_cash_per_pc"]) - 80000 == round(row["gross_profit"] * 1000)
        assert row["electricity_cost_example"] == round(.240 * .30 * row["elapsed_hours"], 2)
        misses = row["non_target_sessions"]
        # Repeated attempts after all funds are exhausted add counts, but no new game history.
        row["non_target_sessions"] = [entry for entry in misses if any(entry["pc_rounds"])]
        row["unfunded_sessions_without_bets_omitted_from_detail"] = len(misses) - len(row["non_target_sessions"])
    win = Fraction(math.comb(25 - mines, 2), math.comb(25, 2))
    payment = Fraction(payout_millieuro, 1000)
    return {
        "created_at": datetime.now(timezone.utc).isoformat(), "script": "analysis/seven_mine_trigger.py",
        "source": "fresh_synthetic_uniform_independent_boards", "previous_reports_reused_as_samples": False,
        "real_games_started": False, "gui_settings_or_live_bot_changed": False,
        "independent_seed_chunks": [{"months": count, "seed": seed} for count, seed, _, _ in jobs],
        "simulation": {**chunks[0]["simulation"], "independent_months": months},
        "method": "After every observed settlement the master checks collective cash minus session starting "
                  "cash, with all outstanding stakes already deducted. At +3 EUR it prohibits new bets and "
                  "drains open games. No batches. Each laptop funds only its own bets; balances carry across "
                  "sessions and days. Session two has its own +3 EUR target and only the time remaining from "
                  "the shared 12-hour start budget. All counts include empty session attempts after ruin; "
                  "monthly detail omits these repeated no-bet attempts and records their count separately. "
                  "The complete month uses integer millieuro balances; payouts are never rounded to cents.",
        "timing_seconds": chunks[0]["timing_seconds"],
        "theoretical_calculations": {
            "lose_first_cell_probability": mines / 25,
            "lose_second_cell_probability": float(Fraction(25 - mines, 25) - win),
            "win_probability": float(win), "net_win_eur": float(payment - Fraction(1, 10)), "net_loss_eur": -.10,
            "total_win_payment_eur": float(payment), "expected_profit_per_game_eur": float(payment * win - Fraction(1, 10)),
            "return_to_player_percent": float(1000 * payment * win),
            "break_even_total_win_payment_eur": float(Fraction(1, 10) / win),
        },
        "observed_simulation": summary, "monthly_rows": rows,
        "electricity_example": chunks[0]["electricity_example"],
        "limitations": chunks[0]["limitations"] + [
            f"{mines} mines on 25 cells and exactly {float(payment):g} EUR total returned per two-cell win are unverified site assumptions.",
            "The site may round each payout to cents instead of preserving fractional cents; that changes the results.",
            "A trigger changes the stopping time, not the expected profit of each bet.",
            "Finite simulation observations are not guaranteed future outcomes.",
        ],
        "runtime_seconds": time.monotonic() - started,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payout-millieuro", type=int, default=180)
    parser.add_argument("--mines", type=int, default=7)
    arguments = parser.parse_args()
    report = run_research(payout_millieuro=arguments.payout_millieuro, mines=arguments.mines)
    directory = parallel.ROOT / "bulk_results"
    directory.mkdir(exist_ok=True)
    path = directory / f"mine_trigger_{arguments.mines}_mines_{arguments.payout_millieuro}_millieuro_{datetime.now(timezone.utc):%Y%m%d_%H%M%S_%fZ}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
    print("Report:", path, flush=True)
    print(json.dumps(report["observed_simulation"], indent=2), flush=True)

