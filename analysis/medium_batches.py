"""Research only: four 20 EUR laptops, 0.10 stakes, two +3 EUR sessions, synchronized batches."""

from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from functools import partial
from fractions import Fraction
import hashlib
import json
import math
import secrets
import time
from unittest.mock import patch

import numpy as np

from . import collective_validation as validation
from .collective_parallel import ROOT
from .medium_two_verification import observed


def make_rngs(seed, count):
    return [np.random.default_rng(int.from_bytes(hashlib.sha256(
        f"{seed}:laptop:{pc}".encode()).digest()[:16], "big")) for pc in range(count)]


def financial_path(valid, ends, gains, settled, peak):
    # Stable ordering preserves laptop-index order for simultaneous settlements.
    order = np.argsort(ends[valid], kind="stable")
    profits = settled + np.cumsum(gains[valid][order])
    peaks = np.maximum.accumulate(np.maximum(profits, peak))
    return ends[valid][order], profits, peaks


def simulate_batch_day(seed, timing, *, batch_size, laptop_count=4, starting_cash_cents=None,
                       protected=True, floor_lock=False, target_cents=300, drawdown_cents=50000,
                       deadline_seconds=43200, round_cap=4000, picks=2, payout_cents=18, mines=6):
    if any(type(n) is not int or n < 1 for n in
           (batch_size, laptop_count, target_cents, drawdown_cents, round_cap)):
        raise ValueError("Positive integer batch, laptop, target, drawdown and cap required")
    if type(mines) is not int or not 0 <= mines <= 25:
        raise ValueError("Integer mine count from 0 to 25 required")
    safe_prefixes = ((25 - mines) / 25, math.comb(25 - mines, 2) / math.comb(25, 2))
    if (type(picks) is not int or picks != 2 or type(payout_cents) is not int or payout_cents != 18
            or protected is not True or floor_lock is not False):
        raise ValueError("This experiment requires two cells, 18 cents total payout and no floor lock")
    if not math.isfinite(deadline_seconds) or deadline_seconds <= 0:
        raise ValueError("Positive finite deadline required")
    if (any(isinstance(timing[key], bool) or not math.isfinite(timing[key]) or timing[key] < 0
            for key in ("play", "tile", "after_loss", "reveal", "between"))
            or timing["play"] + timing["tile"] <= 0):
        raise ValueError("Finite nonnegative timings with positive round duration required")
    starting = [2000] * laptop_count if starting_cash_cents is None else list(starting_cash_cents)
    if len(starting) != laptop_count or any(type(c) is not int or c < 0 for c in starting):
        raise ValueError("One nonnegative integer cash balance per laptop required")
    cash = np.array(starting, dtype=np.int64)
    minimum = cash.copy()
    rounds = np.zeros(laptop_count, dtype=np.int64)
    initial = sum(starting)
    rngs = make_rngs(seed, laptop_count)
    columns = np.arange(batch_size)[None, :]
    now = end = stop = 0.0
    settled = peak = max_drawdown = batches = 0
    target_floor = None
    while True:
        active = (cash >= 10) & (rounds < round_cap)
        if not np.any(active):
            status = "insufficient_funds" if np.any(cash < 10) else "round_cap_or_funds"
            stop = end
            break
        if now >= deadline_seconds:
            status = "deadline"
            stop = end = deadline_seconds
            break
        quota = np.minimum(batch_size, round_cap - rounds)
        draws = np.stack([rng.random(batch_size) if active[pc] else np.zeros(batch_size)
                          for pc, rng in enumerate(rngs)])
        won = draws < safe_prefixes[1]
        opened = np.where(draws >= safe_prefixes[0], 1, 2)
        gains = np.where(won, 8, -10)
        duration = timing["play"] * (1 + won.astype(int)) + opened * timing["tile"]
        cycles = duration + timing["reveal"] + timing["between"] + (~won) * timing["after_loss"]
        starts = now + np.cumsum(cycles, axis=1) - cycles
        ends = starts + duration
        before = cash[:, None] + np.cumsum(gains, axis=1) - gains
        # A start sees only earlier results on this laptop, never its own outcome or duration.
        valid = np.logical_and.accumulate((before >= 10) & (starts < deadline_seconds)
                                          & (columns < quota[:, None]), axis=1)
        if not np.any(valid):
            status = "deadline"
            stop = end = deadline_seconds
            break
        batches += 1
        event_times, profits, peaks = financial_path(valid, ends, gains, settled, peak)
        hit = np.flatnonzero((peaks - profits >= drawdown_cents) & (event_times < deadline_seconds))
        drawdown_stop = float(event_times[hit[0]]) if hit.size else None
        if drawdown_stop is not None:
            # Stop new starts at the first observed loss crossing; drain bets already open.
            valid &= starts < drawdown_stop
            event_times, profits, peaks = financial_path(valid, ends, gains, settled, peak)
        count = valid.sum(axis=1)
        minimum = np.minimum(minimum, np.where(valid, before - 10, np.iinfo(np.int64).max).min(axis=1))
        cash += np.where(valid, gains, 0).sum(axis=1)
        rounds += count
        settled = int(profits[-1])
        peak = int(peaks[-1])
        max_drawdown = max(max_drawdown, int(np.max(peaks - profits)))
        end = float(event_times[-1])
        assert int(cash.sum()) - initial == settled
        assert np.all(cash >= 0)
        if drawdown_stop is not None:
            status, stop = "drawdown", drawdown_stop
            break
        time_limited = np.any((count < quota) & (cash >= 10) & (rounds < round_cap))
        if time_limited:
            end = max(end, deadline_seconds)
        # All actual bets are now settled. Only this boundary can satisfy the profit target.
        if settled >= target_cents:
            status, stop, target_floor = "target", end, settled
            break
        if time_limited or end >= deadline_seconds:
            status, stop, end = "deadline", deadline_seconds, max(end, deadline_seconds)
            break
        active = (cash >= 10) & (rounds < round_cap)
        if not np.any(active):
            status = "insufficient_funds" if np.any(cash < 10) else "round_cap_or_funds"
            stop = end
            break
        # Synchronized restart also respects each laptop's final reveal/result delay.
        now = float(np.max((starts + cycles)[valid]))
    return {
        "profit": settled / 100, "status": status, "hours": end / 3600, "stop_hours": stop / 3600,
        "settlement_overrun_seconds": max(0, end - deadline_seconds),
        "pending_drain_seconds": max(0, end - stop), "max_settled_drawdown": max_drawdown / 100,
        "target_stop_cash_floor": None if target_floor is None else target_floor / 100,
        "pc_final_cash_cents": cash.tolist(), "pc_minimum_cash_cents": minimum.tolist(),
        "pc_final_cash": (cash / 100).tolist(), "pc_minimum_cash": (minimum / 100).tolist(),
        "pc_rounds": rounds.tolist(), "pc_unfunded_at_close": (cash < 10).tolist(),
        "batches": batches,
    }


def run_chunk(arguments):
    months, batch_size, stream, mines = arguments
    with patch.object(validation, "simulate_day", partial(simulate_batch_day, batch_size=batch_size, mines=mines)), \
         patch.object(validation.secrets, "randbits", return_value=stream):
        result = validation.run_validation(months=months, days_per_month=30, picks=2, payout_cents=18,
                                           initial_bankroll_cents=2000, sessions_per_day=2,
                                           laptop_count=4, target_cents=300, total_power_watts=240)
    result["simulation"]["batch_size_per_laptop"] = batch_size
    result["simulation"]["synchronized_batch_barrier"] = True
    plan = result["simulation"]
    plan.update(mines=mines, cells=25, difficulty="medium" if mines == 6 else "custom")
    assert (plan["stake"], plan["payout_on_win"], plan["picks"], plan["initial_bankroll_per_laptop"],
            plan["global_session_target"], plan["sessions_per_day"]) == (.1, .18, 2, 20, 3, 2)
    return result


def batch_theory(size, mines=6):
    if type(size) is not int or size < 1 or type(mines) is not int or not 0 <= mines <= 25:
        raise ValueError("Positive integer batch size and integer mine count from 0 to 25 required")
    games = 4 * size
    win = Fraction(math.comb(25 - mines, 2), math.comb(25, 2))
    probability = float(win)
    expected_cents = 18 * win - 10
    return {"games_per_laptop": size, "group_games": games, "mines": mines,
            "win_probability": probability, "expected_profit_per_game_cents": float(expected_cents),
            "return_to_player_percent": float(100 * win * Fraction(18, 10)),
            "mean_group_profit_eur": float(games * expected_cents / 100),
            "negative_group_batch_probability": sum(math.comb(games, w) * probability ** w * (1 - probability) ** (games - w)
                                                     for w in range(math.ceil(games * 10 / 18))),
            "note": "One complete funded batch; not the probability of a negative day or month."}


def run_research(months=3000, workers=4, mines=6):
    if any(type(n) is not int or n < 1 for n in (months, workers)):
        raise ValueError("Positive integer months and workers required")
    batch_theory(50, mines)  # Validate the mine count before starting worker processes.
    started = time.monotonic()
    print(f"{mines} mines, 50/100-game batches: {months} fresh months per size, {workers} workers", flush=True)
    counts = [months // workers + (i < months % workers) for i in range(workers)]
    jobs = [(count, size, secrets.randbits(128), mines) for size in (50, 100) for count in counts if count]
    assert len({stream for _, _, stream, _ in jobs}) == len(jobs)
    results = {50: [], 100: []}
    with ProcessPoolExecutor(max_workers=workers) as executor:
        for job, chunk in zip(jobs, executor.map(run_chunk, jobs)):
            results[job[1]].append(chunk)
            print(f"Batch {job[1]}: {sum(len(c['monthly_rows']) for c in results[job[1]])}/{months} fresh months", flush=True)
    samples = {}
    for size, chunks in results.items():
        rows = [dict(row) for chunk in chunks for row in chunk["monthly_rows"]]
        for number, row in enumerate(rows, 1):
            row["month"] = number
            assert sum(round(c * 100) for c in row["final_cash_per_pc"]) - 8000 == round(row["gross_profit"] * 100)
            assert row["electricity_cost_example"] == round(.240 * .30 * row["elapsed_hours"], 2)
        samples[str(size)] = {"simulation": {**chunks[0]["simulation"], "independent_months": months},
                              "observed_simulation": observed(chunks), "monthly_rows": rows,
                              "theoretical_single_batch": batch_theory(size, mines)}
    return {
        "created_at": datetime.now(timezone.utc).isoformat(), "script": "analysis/medium_batches.py",
        "source": "fresh_synthetic_uniform_independent_boards", "previous_reports_reused_as_samples": False,
        "real_games_started": False, "gui_or_live_bot_changed": False,
        "independent_streams": [{"months": n, "batch_size": size, "stream": stream, "mines": mine_count}
                                for n, size, stream, mine_count in jobs],
        "method": "Each laptop completes its own fixed batch, then waits for all other active laptops. "
                  "The master checks the settled group profit only at batch boundaries. Restarts synchronize after "
                  "all result/reveal delays. Stakes are fixed at 10 cents, total wins 18 cents. "
                  "Array prefixes admit bets using only earlier own settlements and starts strictly before the deadline. "
                  "Chronological replay enforces the 500 EUR drawdown and drains already open games. "
                  "Funds, the game cap or the 12-hour daily start deadline may force an incomplete batch.",
        "timing_seconds": results[50][0]["timing_seconds"],
        "electricity_example": results[50][0]["electricity_example"],
        "samples": samples,
        "limitations": ["Uniform independent boards and exact 18-cent total payment are unverified site assumptions.",
                        "Zero observed losses do not imply zero risk.",
                        "The modeled synchronization waits require a coordinator; real latencies are not measured."],
        "runtime_seconds": time.monotonic() - started,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mines", type=int, default=6)
    arguments = parser.parse_args()
    report = run_research(mines=arguments.mines)
    directory = ROOT / "bulk_results"
    directory.mkdir(exist_ok=True)
    path = directory / f"medium_batches_{arguments.mines}_mines_{datetime.now(timezone.utc):%Y%m%d_%H%M%S_%fZ}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
    print("Report:", path, flush=True)
    for size, sample in report["samples"].items():
        summary = {**sample["observed_simulation"]}
        summary["sessions"] = {k: v for k, v in summary["sessions"].items()
                               if k != "not_reaching_session_target_detail"}
        print(json.dumps({"batch_size": size, **{k: v for k, v in summary.items() if k != "laptops"}}, indent=2), flush=True)
    print("Runtime seconds:", report["runtime_seconds"], flush=True)
