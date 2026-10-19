"""Independent re-check: 4 laptops, medium 2 cells, 0.18 EUR total win, two +3 EUR sessions a day.

Research only: no real games, no GUI, settings or live-bot changes.
"""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from fractions import Fraction
import itertools
import json
import math
import os
import random
import secrets
from statistics import mean, variance
import time
from unittest.mock import patch

import numpy as np

try:
    from . import collective_parallel as parallel
    from . import medium_two_sessions as two
    from .collective_validation import distribution
    from .medium_bankroll import mathematical_bound
except ImportError:
    import collective_parallel as parallel
    import medium_two_sessions as two
    from collective_validation import distribution
    from medium_bankroll import mathematical_bound


CELLS, MINES, PICKS = 25, 6, 2
STAKE, PAYOUT = parallel.STAKE, 18  # cents; PAYOUT is the whole amount a win returns, stake included
LAPTOPS, CAPITAL, SESSIONS, WATTS = 4, 2000, 2, 240
TARGET, CAP = 300, 4000
OUTCOMES = {(1, False): "lose_first_cell", (2, False): "lose_second_cell", (2, True): "win"}
EXACT = {(1, False): Fraction(MINES, CELLS),
         (2, False): Fraction(CELLS - MINES, CELLS) * Fraction(MINES, CELLS - 1),
         (2, True): Fraction(math.comb(CELLS - MINES, PICKS), math.comb(CELLS, PICKS))}
TIMING_KEYS = ("sleep_play_or_collect", "sleep_after_play", "sleep_click_tile", "sleep_after_tile_click",
               "sleep_after_result", "tile_record_enabled", "tile_reveal_delay", "sleep_between_rounds",
               "wait_selected", "sleep_color_retry")


def full_board_round(rng, picks=PICKS):
    """Reference generator: a complete 25-cell board with 6 mines, then distinct cells opened in order."""
    mines = set(rng.sample(range(CELLS), MINES))
    for opened, cell in enumerate(rng.sample(range(CELLS), picks), 1):
        if cell in mines:
            return opened, False
    return picks, True


def exact_board_outcomes(cells=(0, 1)):
    """Open the given distinct cells on every one of the C(25, 6) complete boards."""
    counts = Counter()
    for mines in itertools.combinations(range(CELLS), MINES):
        first = next((opened for opened, cell in enumerate(cells, 1) if cell in mines), None)
        counts[(first, False) if first else (len(cells), True)] += 1
    return counts


def fit_p_value(counts):
    """Pearson test against the exact probabilities; three outcomes give 2 df, survival exp(-x/2)."""
    total = sum(counts.values())
    statistic = sum((counts[key] - total * float(p)) ** 2 / (total * float(p)) for key, p in EXACT.items())
    return {"chi_square": statistic, "p_value": math.exp(-statistic / 2)}


def homogeneity_p_value(first, second):
    """Pearson test that two samples share one outcome distribution (2 x 3 table, 2 df)."""
    sizes = sum(first.values()), sum(second.values())
    statistic = 0.0
    for key in EXACT:
        pooled = (first[key] + second[key]) / sum(sizes)
        statistic += sum((counts[key] - size * pooled) ** 2 / (size * pooled)
                         for counts, size in zip((first, second), sizes))
    return {"chi_square": statistic, "p_value": math.exp(-statistic / 2)}


def compare_generators(games, seed):
    fast_rng, full_rng = random.Random(f"{seed}:fast"), random.Random(f"{seed}:full")
    fast = Counter(parallel.sample_round(fast_rng, PICKS) for _ in range(games))
    full = Counter(full_board_round(full_rng) for _ in range(games))
    return {"games_each": games,
            "exact_probability": {name: float(EXACT[key]) for key, name in OUTCOMES.items()},
            "fast_generator_frequency": {name: fast[key] / games for key, name in OUTCOMES.items()},
            "complete_board_frequency": {name: full[key] / games for key, name in OUTCOMES.items()},
            "fast_vs_exact": fit_p_value(fast),
            "complete_boards_vs_exact": fit_p_value(full),
            "fast_vs_complete_boards": homogeneity_p_value(fast, full)}


def session_cap_theory(barrier_cents, games=LAPTOPS * CAP, trim=1e-30):
    """Exact recurrence: pooled settled profit (+8/-10 cents per game) never touching the barrier.

    Works in two-cent units (+4/-5); probability below `trim` is dropped and reported.
    """
    win = float(EXACT[(2, True)])
    barrier = barrier_cents // 2
    alive, low, reached, trimmed = np.array([1.0]), 0, 0.0, 0.0
    for _ in range(games):
        step = np.zeros(len(alive) + 9)
        step[:len(alive)] += alive * (1 - win)
        step[9:] += alive * win
        low -= 5
        cut = barrier - low
        reached += step[cut:].sum()
        alive = step[:cut]
        keep = np.flatnonzero(alive > trim)
        first = int(keep[0]) if len(keep) else len(alive)
        trimmed += alive[:first].sum()
        alive, low = alive[first:], low + first
    units = low + np.arange(len(alive))
    miss = float(alive.sum())
    return {"settled_barrier_eur": barrier_cents / 100, "pooled_games": games,
            "target_reached_probability": float(reached), "miss_probability": miss,
            "miss_and_negative_probability": float(alive[units < 0].sum()),
            "miss_and_below_minus_3_eur_probability": float(alive[units < -150].sum()),
            "mean_profit_given_miss_eur": float(.02 * (alive @ units) / miss) if miss else None,
            "dropped_tail_probability": float(trimmed)}


def reach_upper_bound(payout_cents, target_cents=TARGET):
    """Lundberg bound: when games lose on average, P(ever gaining target_cents) <= exp(-R * target).

    Holds with unlimited games, time and cash, so it also bounds the capped sessions. None when the
    average game wins (no bound below 1).
    """
    win = float(EXACT[(2, True)])
    if win * (payout_cents - STAKE) >= (1 - win) * STAKE:
        return None

    def excess(rate):
        return win * math.exp(rate * (payout_cents - STAKE)) + (1 - win) * math.exp(-rate * STAKE) - 1

    low, high = 1e-12, 1.0
    for _ in range(200):
        middle = (low + high) / 2
        low, high = (middle, high) if excess(middle) < 0 else (low, middle)
    return math.exp(-low * target_cents)


def cycle_seconds(timing):
    """Seconds from one start to the next on one laptop, from the modeled click pauses."""
    game = {(1, False): timing["play"] + timing["tile"],
            (2, False): timing["play"] + 2 * timing["tile"],
            (2, True): 2 * timing["play"] + 2 * timing["tile"]}
    cycle = {key: game[key] + timing["reveal"] + timing["between"] + (0 if key[1] else timing["after_loss"])
             for key in game}
    return {**{OUTCOMES[key]: value for key, value in cycle.items()},
            "mean": sum(float(EXACT[key]) * value for key, value in cycle.items())}


def miss_reason(entry):
    if entry["status"] == "deadline":
        return "time_12h_budget"
    if entry["status"] == "round_cap_or_funds":  # every laptop reached 4000 games
        return "game_cap_4000_per_laptop"
    if entry["status"] == "insufficient_funds":
        return "funds" if all(entry["pc_unfunded_at_close"]) else "funds_and_game_cap"
    return entry["status"]


def observed(chunks, units_per_eur=100):
    plan = chunks[0]["simulation"]
    capital_units = round(plan["initial_bankroll_per_laptop"] * units_per_eur)
    laptop_count = plan["laptops"]
    rows = [row for chunk in chunks for row in chunk["monthly_rows"]]
    summaries = [chunk["summary"] for chunk in chunks]
    days = len(rows) * chunks[0]["simulation"]["days_per_month"]
    gross = [row["gross_profit"] for row in rows]
    net = [row["net_profit_after_example_electricity"] for row in rows]
    misses = [{"month": number, **entry} for number, row in enumerate(rows, 1) for entry in row["non_target_sessions"]]
    skipped = sum(row["sessions_skipped_daily_time_budget"] for row in rows)
    reasons = Counter(miss_reason(entry) for entry in misses)
    if skipped:
        reasons["time_no_second_session_start"] = skipped
    unfunded = [row for row in rows if row["days_with_insufficient_pc_funds"]]
    return {
        "sessions": {
            "planned": days * plan["sessions_per_day"],
            "executed": sum(row["sessions_executed"] for row in rows),
            "negative": sum(row["negative_sessions"] for row in rows),
            "worst_eur": min(row["worst_session"] for row in rows),
            "not_reaching_session_target": len(misses) + skipped,
            "not_reaching_session_target_by_reason": dict(reasons),
            "not_reaching_session_target_detail": misses,
        },
        "days": {
            "count": days,
            "negative": sum(row["negative_days"] for row in rows),
            "zero": sum(row["zero_days"] for row in rows),
            "worst_eur": min(row["worst_day"] for row in rows),
            "months_with_a_day_closing_below_initial_group_capital": sum(
                round(row["minimum_daily_closing_total_cash"] * units_per_eur) < laptop_count * capital_units for row in rows),
            "lowest_daily_closing_group_cash_eur": min(row["minimum_daily_closing_total_cash"] for row in rows),
            "mean_activity_minutes": 60 * sum(row["elapsed_hours"] for row in rows) / days,
            "maximum_activity_hours": max(summary["maximum_daily_hours"] for summary in summaries),
            "days_with_games_settling_after_12h": sum(summary["settlement_overrun_days"] for summary in summaries),
            "mean_games_all_laptops": sum(summary["mean_daily_rounds_all_laptops"] * summary["daily_count"]
                                          for summary in summaries) / days,
        },
        "months": {
            "count": len(rows),
            "negative_gross": sum(value < 0 for value in gross),
            "gross_eur": distribution(gross),
            "electricity_example_eur": distribution([row["electricity_cost_example"] for row in rows]),
            "net_after_example_electricity_eur": distribution(net),
            "negative_net_after_example_electricity": sum(value < 0 for value in net),
            "with_any_laptop_out_of_funds": len(unfunded),
            "with_any_laptop_out_of_funds_while_group_positive": sum(row["gross_profit"] > 0 for row in unfunded),
        },
        "laptops": [{
            "laptop": pc + 1,
            "minimum_cash_with_open_stake_eur": min(row["minimum_cash_per_pc"][pc] for row in rows),
            "minimum_daily_closing_cash_eur": min(row["minimum_daily_closing_cash_per_pc"][pc] for row in rows),
            "final_cash_eur": distribution([row["final_cash_per_pc"][pc] for row in rows]),
            "months_finishing_below_initial_capital": sum(
                round(row["final_cash_per_pc"][pc] * units_per_eur) < capital_units for row in rows),
        } for pc in range(laptop_count)],
    }


def mean_gap(fast_chunks, full_chunks, key):
    fast = [row[key] for chunk in fast_chunks for row in chunk["monthly_rows"]]
    full = [row[key] for chunk in full_chunks for row in chunk["monthly_rows"]]
    error = math.sqrt(variance(fast) / len(fast) + variance(full) / len(full))
    return {"fast_mean": mean(fast), "complete_board_mean": mean(full),
            "difference": mean(fast) - mean(full), "standard_error": error,
            "z_score": (mean(fast) - mean(full)) / error}


def run_chunk(arguments):
    months, complete_boards = arguments
    if not complete_boards:
        return two.run_chunk((months, LAPTOPS, SESSIONS, WATTS))
    # The patch only applies if the simulator resolves sample_round from this very module object.
    assert two.run_validation.__globals__["simulate_day"].__globals__ is vars(parallel)
    with patch.object(parallel, "sample_round", full_board_round):
        return two.run_chunk((months, LAPTOPS, SESSIONS, WATTS))


def run_months(executor, months, workers, complete_boards=False):
    counts = [months // workers + (index < months % workers) for index in range(workers)]
    return list(executor.map(run_chunk, [(count, complete_boards) for count in counts if count]))


def run_verification(months=3000, complete_board_months=300, generator_games=1_000_000, workers=None):
    workers = workers or os.cpu_count() or 4
    for count in (months, complete_board_months, generator_games, workers):
        if type(count) is not int or count < 1:
            raise ValueError("Positive integer counts required")
    started = time.monotonic()
    settings = json.loads((parallel.ROOT / "gratta_settings.json").read_text(encoding="utf-8"))
    timing = parallel.timing_from_settings(settings)
    print(f"Fresh months: {months} fast + {complete_board_months} complete-board, {workers} workers", flush=True)
    with ProcessPoolExecutor(max_workers=workers) as executor:
        fast_chunks = run_months(executor, months, workers)
        print("Fast-generator months done", flush=True)
        full_chunks = run_months(executor, complete_board_months, workers, complete_boards=True)
        print("Complete-board months done", flush=True)
    for chunk in fast_chunks + full_chunks:
        plan = chunk["simulation"]
        # Guards against the 6-cell / 0.68 EUR defaults of the shared helpers.
        assert (plan["picks"], plan["payout_on_win"], plan["laptops"], plan["sessions_per_day"],
                plan["initial_bankroll_per_laptop"], plan["days_per_month"]) == (2, .18, 4, 2, 20, 30)
        assert chunk["timing_seconds"] == timing
    fast = observed(fast_chunks)
    print("Generator comparison and exact recurrences", flush=True)
    win = EXACT[(2, True)]
    expected_cents = win * (PAYOUT - STAKE) - (1 - win) * STAKE
    spread = math.sqrt(win * (PAYOUT - STAKE) ** 2 + (1 - win) * STAKE ** 2 - expected_cents ** 2)
    misses = [session_cap_theory(TARGET), session_cap_theory(TARGET + (LAPTOPS - 1) * STAKE)]
    sessions = fast["sessions"]["executed"]
    rows = [row for chunk in fast_chunks for row in chunk["monthly_rows"]]
    for number, row in enumerate(rows, 1):
        row["month"] = number
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "script": "analysis/medium_two_verification.py",
        "source": "fresh_synthetic_uniform_independent_boards",
        "real_games_started": False, "gui_settings_or_live_bot_changed": False,
        "previous_reports_reused_as_samples": False,
        "independent_seed_chunks": {"fast_generator": len(fast_chunks), "complete_boards": len(full_chunks)},
        "configuration": {
            "laptops_playing": LAPTOPS, "separate_master_not_playing": True,
            "initial_capital_per_laptop_eur": CAPITAL / 100, "initial_capital_total_eur": LAPTOPS * CAPITAL / 100,
            "days_per_month": 30, "sessions_per_day": SESSIONS, "stake_eur": STAKE / 100,
            "difficulty": "medium", "cells": CELLS, "mines": MINES, "distinct_cells_opened": PICKS,
            "total_returned_on_win_eur": PAYOUT / 100, "net_on_win_eur": (PAYOUT - STAKE) / 100,
            "net_on_loss_eur": -STAKE / 100, "progression_or_grinding": False,
            "session_stop": "+3 EUR for the whole group, measured on cash with every open stake already deducted",
            "second_session_target": "+3 EUR over the cash left by the first session, even after a loss",
            "game_cap_per_laptop_per_session": CAP, "shared_daily_start_budget_hours": 12,
            "drawdown_limit_per_session_eur": 500, "voluntary_pauses": False,
            "resets_topups_transfers_withdrawals": False},
        "timing_from_settings": {
            "settings_file": "gratta_settings.json (read only)",
            "values_in_file": {key: settings.get(key, "absent: default used") for key in TIMING_KEYS},
            "modeled_seconds": timing,
            "modeled_sequence": "start: sleep_play_or_collect, click play (stake already reserved); each cell: "
                                "sleep_after_play + sleep_click_tile + sleep_after_tile_click; win: "
                                "sleep_play_or_collect, click collect; every finished board: one tile_reveal_delay; "
                                "after a loss also sleep_after_result.",
            "cycle_seconds_per_laptop": cycle_seconds(timing),
            "cycle_seconds_if_live_sleep_between_rounds_kept": cycle_seconds(
                {**timing, "between": settings.get("sleep_between_rounds", 0.0)}),
            "excluded": ["sleep_between_rounds: pause after every live round, excluded as a voluntary pause",
                         "wait_selected random 60-360 s waits", "sleep_color_retry color re-reads",
                         "bet-change pauses (fixed 0.10 EUR stake)", "initial setup steps",
                         "network, rendering, click and coordinator latency"]},
        "observed_simulation": {"note": "Counts from a finite random sample of fresh months.", **fast},
        "fast_generator_vs_complete_boards": {
            "exact_enumeration": {
                "boards": math.comb(CELLS, MINES),
                "cells_opened": "two fixed distinct cells; any pair gives the same counts on uniform boards",
                "counts": {OUTCOMES[key]: count for key, count in exact_board_outcomes().items()},
                "fast_generator_probabilities": {
                    "lose_first_cell": 1 - parallel.SAFE_PREFIXES[0],
                    "lose_second_cell": parallel.SAFE_PREFIXES[0] - parallel.SAFE_PREFIXES[1],
                    "win": parallel.SAFE_PREFIXES[1]}},
            "sampled_games": compare_generators(generator_games, secrets.randbits(128)),
            "sampled_months": {
                "complete_board_months": complete_board_months,
                "monthly_gross_eur": mean_gap(fast_chunks, full_chunks, "gross_profit"),
                "monthly_activity_hours": mean_gap(fast_chunks, full_chunks, "elapsed_hours"),
                "complete_board_observed": observed(full_chunks)}},
        "theoretical_calculations": {
            "note": "Calculated from the stated rules, not sampled.",
            "outcome_probabilities": {name: str(EXACT[key]) for key, name in OUTCOMES.items()},
            "expected_profit_per_game_cents": float(expected_cents),
            "standard_deviation_per_game_cents": spread,
            "return_to_player_percent": float(100 * win * PAYOUT / STAKE),
            "fair_total_win_payment_cents": float(STAKE / win),
            "if_win_pays_in_total": {
                f"{float(cents) / 100:.3f}_eur": {
                    "expected_profit_per_game_cents": float(win * (cents - STAKE) - (1 - win) * STAKE),
                    "session_ever_reaching_plus_3_eur_upper_bound": reach_upper_bound(float(cents))}
                for cents in (Fraction(17), Fraction(35, 2), Fraction(18))},
            "session_miss_within_4000_games_per_laptop": {
                "method": "Exact recurrence on the pooled settled profit over 16000 games; ignores per-laptop "
                          "funds and time. The real stop needs settled profit between 3.00 and 3.30 EUR because "
                          "up to three other laptops can hold an open 0.10 EUR stake.",
                "settled_barrier_3_00_eur": misses[0], "settled_barrier_3_30_eur": misses[1],
                "expected_misses_in_this_sample": [sessions * row["miss_probability"] for row in misses],
                "approximate_negative_day_probability": [
                    2 * row["miss_and_below_minus_3_eur_probability"] for row in misses]},
            "laptop_out_of_funds_ever_upper_bound": mathematical_bound(CAPITAL / 100),
        },
        "unverified_site_assumptions": [
            "Medium really has 6 mines on 25 cells and mine placement is uniform and independent between games and laptops.",
            "A two-cell win credits exactly 0.18 EUR in total. 1.8x is above the fair 1.754x (102.6% return); "
            "a credit of 0.17 or 0.175 EUR makes every game negative on average.",
            "No fees, limits, account checks, bonuses, rounding or session rules that change payments.",
            "Click pauses equal the configured sleeps; real network/rendering delays and coordinator latency are not measured.",
            "A master that stops all four laptops instantly exists; the live bot has no such coordinator.",
            "The live gratta_settings.json currently uses custom progression, grinding, high difficulty and 3 picks, "
            "so the live bot would not play this plan as configured today.",
        ],
        "code_review": {
            "verified": [
                "Fast generator thresholds equal complete-board enumeration (6/25, 19/100, 57/100).",
                "Win returns 18 cents total (+8 net), loss -10; balances are integer cents and reconcile per session, day and month.",
                "The stake leaves the laptop before the outcome is drawn; a laptop below 10 cents never plays or uses other laptops' cash.",
                "Stop decisions use only settled outcomes; +3 EUR is checked on cash with every open stake deducted; open games are completed.",
                "Second session: target relative to its own starting cash, deadline equals the unused part of 12 hours.",
                "A second, heap-free implementation reproduces simulate_day and the month loop exactly.",
            ],
            "issues": [
                "Helper defaults are 6 cells / 68 cents / 1000 EUR / 1 session; medium_two_sessions.run_chunk pins this plan and a test now guards it.",
                "Status 'insufficient_funds' also covers mixed funds/game-cap stops and 'round_cap_or_funds' means every laptop hit 4000; misses are now recorded per laptop and reclassified.",
                "The 500 EUR drawdown limit can never trigger with 80 EUR of capital, so it protects nothing.",
                "sleep_between_rounds is skipped by instruction; if the live bot keeps it, time and electricity grow by about 15%.",
            ],
            "changes": [
                "collective_validation.run_validation records missed-session details and the lowest daily group close (reporting only).",
                "tests/test_medium_two_config.py adds deterministic and reference checks.",
            ]},
        "electricity_example": {
            "total_watts_all_five_computers": WATTS, "eur_per_kwh": .30,
            "charged_hours": "modeled daily activity (wall clock), not multiplied by laptop count",
            "hardware_power_measured": False},
        "limitations": [
            "Rare events (session misses, negative days, laptop ruin) have few or no sample occurrences; see theoretical_calculations.",
            "Zero observed losses in a finite sample is not zero risk.",
        ],
        "observed_simulation_monthly_rows": rows,
        "runtime_seconds": time.monotonic() - started,
    }


if __name__ == "__main__":
    report = run_verification()
    directory = parallel.ROOT / "bulk_results"
    directory.mkdir(exist_ok=True)
    path = directory / f"medium_two_verification_{datetime.now(timezone.utc):%Y%m%d_%H%M%S_%fZ}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
    print("Report:", path, flush=True)
    sessions = dict(report["observed_simulation"]["sessions"])
    sessions.pop("not_reaching_session_target_detail")
    print(json.dumps({"sessions": sessions, "days": report["observed_simulation"]["days"],
                      "months": report["observed_simulation"]["months"]}, indent=2), flush=True)
