"""Research independent PCs and global stops; never controls the live bot."""

from collections import Counter
from datetime import datetime, timezone
import argparse
import heapq
import json
import math
from pathlib import Path
import random
import secrets
from statistics import mean
import time


ROOT = Path(__file__).resolve().parents[1]
STAKE = 10
PAYOUT = 68
BANKROLL = 100000
SAFE_PREFIXES = [math.comb(19, j) / math.comb(25, j) for j in range(1, 9)]
SURVIVAL = SAFE_PREFIXES[:6]


def sample_round(rng, picks=6):
    """Nested safe-prefix probabilities give the actual first mine clicked."""
    if type(picks) is not int or not 1 <= picks <= 8:
        raise ValueError("picks must be an integer from 1 to 8")
    draw = rng.random()
    for opened, probability in enumerate(SAFE_PREFIXES[:picks], 1):
        if draw >= probability:
            return opened, False
    return picks, True


def timing_from_settings(settings):
    timing = {
        "play": settings.get("sleep_play_or_collect", 1.0),
        "tile": sum(settings.get(key, fallback) for key, fallback in (
            ("sleep_after_play", .5), ("sleep_click_tile", 1.0),
            ("sleep_after_tile_click", .5))),
        "after_loss": settings.get("sleep_after_result", 1.0),
        "reveal": settings.get("tile_reveal_delay", 1.0)
                  if settings.get("tile_record_enabled", True) else 0.0,
        "between": 0.0,
    }
    if any(isinstance(v, bool) or not math.isfinite(v) or v < 0 for v in timing.values()):
        raise ValueError("Timing values must be finite and nonnegative")
    if timing["play"] + timing["tile"] <= 0:
        raise ValueError("A round must take positive time")
    return timing


def simulate_day(seed, timing, protected=True, target_cents=300,
                 drawdown_cents=50000, deadline_seconds=43200, round_cap=4000,
                 floor_lock=False, laptop_count=3, starting_cash_cents=None,
                 picks=6, payout_cents=None):
    payout_cents = PAYOUT if payout_cents is None else payout_cents
    if (type(target_cents) is not int or target_cents <= 0
            or type(drawdown_cents) is not int or drawdown_cents <= 0
            or type(round_cap) is not int or round_cap < 1
            or type(laptop_count) is not int or laptop_count < 1
            or not math.isfinite(deadline_seconds) or deadline_seconds <= 0):
        raise ValueError("Positive target, drawdown, deadline and integer round cap required")
    if (type(picks) is not int or not 1 <= picks <= 8
            or type(payout_cents) is not int or payout_cents <= 0):
        raise ValueError("Integer picks from 1 to 8 and positive integer payout cents required")
    rngs = [random.Random(f"{seed}:laptop:{pc}") for pc in range(laptop_count)]
    if starting_cash_cents is not None and not isinstance(starting_cash_cents, (list, tuple)):
        raise ValueError("starting_cash_cents must be a list of integer balances")
    starting_cash = [BANKROLL] * laptop_count if starting_cash_cents is None else list(starting_cash_cents)
    if len(starting_cash) != laptop_count or any(type(value) is not int or value < 0 for value in starting_cash):
        raise ValueError("starting_cash_cents must contain one nonnegative integer balance per laptop")
    cash = list(starting_cash)
    initial_total = sum(starting_cash)
    minimum_cash = list(cash)
    rounds = [0] * laptop_count
    pending = [False] * laptop_count
    # Event 0 is the deadline, 1 is an observed settlement, 2 is a PC ready to start.
    events = [(deadline_seconds, 0, -1, 0, False)]
    for pc in range(laptop_count):
        heapq.heappush(events, (0.0, 2, pc, 0, False))
    settled = peak = max_drawdown = 0
    stopped = None
    target_cash_floor = None
    capital_protected = False
    first_lock_cash_floor = minimum_locked_floor = None
    lock_time = None
    waiting = set()
    restarting = set()
    floor_waits = floor_resumptions = 0
    stop_time = now = 0.0
    while events and (stopped is None or any(pending)):
        at, kind, pc, opened, won = heapq.heappop(events)
        if stopped is not None and kind != 1:
            continue
        now = at
        if kind == 0:
            stopped, stop_time = "deadline", now
            continue
        if kind == 2:
            # Never inspect a future outcome or duration before allowing this stake.
            if rounds[pc] >= round_cap:
                continue
            if cash[pc] < STAKE:
                if all(rounds[p] >= round_cap or cash[p] < STAKE for p in range(laptop_count)) and not any(pending):
                    stopped, stop_time = "insufficient_funds", now
                continue
            if capital_protected and sum(cash) - initial_total < STAKE:
                if any(pending):
                    waiting.add(pc)
                    floor_waits += 1
                else:
                    stopped, stop_time = "protected_floor", now
                continue
            if pc in restarting:
                floor_resumptions += 1
                restarting.remove(pc)
            cash[pc] -= STAKE
            if capital_protected:
                minimum_locked_floor = min(minimum_locked_floor, sum(cash) - initial_total)
                assert minimum_locked_floor >= 0
            minimum_cash[pc] = min(minimum_cash[pc], cash[pc])
            rounds[pc] += 1
            pending[pc] = True
            opened, won = sample_round(rngs[pc]) if picks == 6 else sample_round(rngs[pc], picks)
            duration = timing["play"] + opened * timing["tile"]
            if won:
                duration += timing["play"]
            heapq.heappush(events, (now + duration, 1, pc, opened, won))
            continue
        pending[pc] = False
        cash[pc] += payout_cents if won else 0
        settled += payout_cents - STAKE if won else -STAKE
        peak = max(peak, settled)
        max_drawdown = max(max_drawdown, peak - settled)
        cash_floor = sum(cash) - initial_total
        if floor_lock and not capital_protected and cash_floor > 0:
            capital_protected = True
            first_lock_cash_floor = minimum_locked_floor = cash_floor
            lock_time = now
        if stopped is None:
            if (cash_floor if protected or floor_lock else settled) >= target_cents:
                stopped, stop_time = "target", now
                target_cash_floor = cash_floor
            elif peak - settled >= drawdown_cents:
                stopped, stop_time = "drawdown", now
            elif capital_protected and cash_floor < STAKE and not any(pending):
                stopped, stop_time = "protected_floor", now
            elif all(rounds[p] >= round_cap or cash[p] < STAKE for p in range(laptop_count)) and not any(pending):
                stopped, stop_time = ("insufficient_funds" if any(value < STAKE for value in cash)
                                      else "round_cap_or_funds"), now
        if stopped is None:
            for blocked_pc in sorted(waiting):
                heapq.heappush(events, (now, 2, blocked_pc, 0, False))
                restarting.add(blocked_pc)
            waiting.clear()
            delay = timing["reveal"] + timing["between"]
            if not won:
                delay += timing["after_loss"]
            heapq.heappush(events, (now + delay, 2, pc, 0, False))
    assert not any(pending)
    assert sum(cash) - initial_total == settled
    if (protected or floor_lock) and stopped == "target":
        assert settled >= target_cents
    if capital_protected:
        assert settled >= 0
    elif floor_lock:
        assert settled >= -drawdown_cents - laptop_count * STAKE
    return {
        "profit": settled / 100,
        "status": stopped,
        "hours": now / 3600,
        "stop_hours": stop_time / 3600,
        "settlement_overrun_seconds": max(0.0, now - deadline_seconds),
        "pending_drain_seconds": max(0.0, now - stop_time),
        "max_settled_drawdown": max_drawdown / 100,
        "target_stop_cash_floor": None if target_cash_floor is None else target_cash_floor / 100,
        "capital_protected": capital_protected,
        "first_lock_cash_floor": None if first_lock_cash_floor is None else first_lock_cash_floor / 100,
        "minimum_cash_floor_after_lock": None if minimum_locked_floor is None else minimum_locked_floor / 100,
        "lock_time_hours": None if lock_time is None else lock_time / 3600,
        "floor_waits": floor_waits,
        "floor_resumptions": floor_resumptions,
        "pc_final_cash": [value / 100 for value in cash],
        "pc_final_cash_cents": list(cash),
        "pc_starting_cash": [value / 100 for value in starting_cash],
        "pc_minimum_cash": [value / 100 for value in minimum_cash],
        "pc_minimum_cash_cents": list(minimum_cash),
        "pc_rounds": rounds,
        "pc_profits": [(value - start) / 100 for value, start in zip(cash, starting_cash)],
        "pc_unfunded_at_close": [value < STAKE for value in cash],
    }


def ideal_day(seed, target_cents=300, drawdown_cents=50000, round_cap=4000, laptop_count=3):
    """Immediate settled stop with no pending bets or actual 12-hour deadline."""
    if type(laptop_count) is not int or laptop_count < 1:
        raise ValueError("laptop_count must be a positive integer")
    rngs = [random.Random(f"{seed}:laptop:{pc}") for pc in range(laptop_count)]
    cash = [BANKROLL] * laptop_count
    rounds = [0] * laptop_count
    settled = peak = 0
    for index in range(laptop_count * round_cap):
        pc = index % laptop_count
        _, won = sample_round(rngs[pc])
        profit = PAYOUT - STAKE if won else -STAKE
        cash[pc] += profit
        rounds[pc] += 1
        settled += profit
        peak = max(peak, settled)
        if settled >= target_cents or peak - settled >= drawdown_cents:
            break
    return {
        "profit": settled / 100,
        "status": "target" if settled >= target_cents else
                  "drawdown" if peak - settled >= drawdown_cents else "round_cap",
        "pc_final_cash": [value / 100 for value in cash],
        "pc_rounds": rounds,
    }


def summarize(days):
    profits = [day["profit"] for day in days]
    n = len(days)
    laptop_count = len(days[0]["pc_final_cash"])
    negatives = sum(value < 0 for value in profits)
    zeroes = sum(value == 0 for value in profits)
    summary = {
        "days": n,
        "laptop_count": laptop_count,
        "initial_total_bankroll": laptop_count * BANKROLL / 100,
        "negative_days": negatives,
        "zero_days": zeroes,
        "nonpositive_days": negatives + zeroes,
        "negative_rate_percent": 100 * negatives / n,
        "average_profit": mean(profits),
        "mean_negative_profit": mean(value for value in profits if value < 0) if negatives else None,
        "worst_profit": min(profits),
        "status_counts": dict(Counter(day["status"] for day in days)),
        "target_stops_finishing_below_target": sum(
            day["status"] == "target" and day["profit"] < 3 for day in days),
        "average_total_rounds": mean(sum(day["pc_rounds"]) for day in days),
        "minimum_pc_final_cash": min(min(day["pc_final_cash"]) for day in days),
        "average_final_cash_per_pc": [mean(day["pc_final_cash"][pc] for day in days) for pc in range(laptop_count)],
        "average_rounds_per_pc": [mean(day["pc_rounds"][pc] for day in days) for pc in range(laptop_count)],
    }
    if "hours" in days[0]:
        summary.update(
            average_hours=mean(day["hours"] for day in days),
            maximum_hours=max(day["hours"] for day in days),
            average_settlement_overrun_seconds=mean(day["settlement_overrun_seconds"] for day in days),
            maximum_settlement_overrun_seconds=max(day["settlement_overrun_seconds"] for day in days),
            minimum_pc_cash_with_open_stakes=min(min(day["pc_minimum_cash"]) for day in days),
        )
        locked = [day for day in days if day["capital_protected"]]
        summary.update(
            locked_days=len(locked),
            latch_fail_days=n - len(locked),
            post_lock_negative_days=sum(day["profit"] < 0 for day in locked),
            post_lock_zero_days=sum(day["profit"] == 0 for day in locked),
            minimum_post_lock_cash_floor=min(day["minimum_cash_floor_after_lock"] for day in locked) if locked else None,
            days_waiting_for_pending_rounds=sum(day["floor_waits"] > 0 for day in days),
            days_resuming_after_pending_rounds=sum(day["floor_resumptions"] > 0 for day in days),
        )
        assert summary["post_lock_negative_days"] == 0
    return summary


def run_experiment(days=10000, floor_lock=False, drawdown_cents=50000, laptop_count=3):
    if type(days) is not int or days < 1:
        raise ValueError("days must be a positive integer")
    if type(drawdown_cents) is not int or drawdown_cents <= 0:
        raise ValueError("drawdown_cents must be a positive integer")
    if type(laptop_count) is not int or laptop_count < 1:
        raise ValueError("laptop_count must be a positive integer")
    settings = json.loads((ROOT / "gratta_settings.json").read_text(encoding="utf-8"))
    timing = timing_from_settings(settings)
    master = secrets.randbits(128)
    started = time.monotonic()
    results = ({"parallel_floor_lock": []} if floor_lock else
               {"ideal_immediate_settled_stop": [], "parallel_raw_settled_target": [],
                "parallel_protected_cash_floor": []})
    for day in range(days):
        seed = f"{master}:day:{day}"
        if floor_lock:
            results["parallel_floor_lock"].append(simulate_day(
                seed, timing, floor_lock=True, drawdown_cents=drawdown_cents, laptop_count=laptop_count))
        else:
            results["ideal_immediate_settled_stop"].append(ideal_day(
                seed, drawdown_cents=drawdown_cents, laptop_count=laptop_count))
            results["parallel_raw_settled_target"].append(simulate_day(
                seed, timing, protected=False, drawdown_cents=drawdown_cents, laptop_count=laptop_count))
            results["parallel_protected_cash_floor"].append(simulate_day(
                seed, timing, protected=True, drawdown_cents=drawdown_cents, laptop_count=laptop_count))
        if (day + 1) % 1000 == 0:
            print(f"Parallel timing experiment: {day + 1}/{days} days", flush=True)
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "synthetic_uniform_independent_boards",
        "real_history_used": False,
        "actual_autoplay_changed": False,
        "costs_included": False,
        "configuration": {"laptops": laptop_count, "bankroll_per_pc": 1000, "stake": .1,
                          "difficulty": "medium", "picks": 6, "multiplier": 6.8,
                          "global_target": 3, "global_settled_drawdown_limit": drawdown_cents / 100,
                          "round_cap_per_pc": 4000, "deadline_hours": 12,
                          "floor_lock_enabled": floor_lock,
                          "wait_selected": False, "voluntary_pause_seconds": 0},
        "conservative_prelock_profit_lower_bound": -(drawdown_cents + laptop_count * STAKE) / 100 if floor_lock else None,
        "timing_seconds": timing,
        "method": "Independent PC worlds; first mine from nested exact safe-prefix probabilities. "
                  "Outcomes settle by actual configured click/collect times. Stakes reserved at start; "
                  "global stop decisions use only current settled profit/cash, never pending outcomes. "
                  "Deadline blocks new starts at 12 hours; already open rounds are drained. "
                  "Protected target uses total cash minus initial bankroll, including all open stake deductions. "
                  "Floor-lock mode latches at first strictly positive cash lower bound, then allows stakes only "
                  "when the cash lower bound covers the full stake, preserving a zero global principal floor. "
                  "Blocked PCs wait for actual pending settlements; no future winnings release a stake. "
                  "Drawdown uses settled profit and its previous peak. Ideal baseline omits timing/pending bets.",
        "limitations": ["Synthetic boards, not verified real-site randomization.",
                        "Setup, network delays, color retries, coordinator latency and faults are not measured.",
                        "One successful board reveal delay modeled; repeated read attempts are excluded.",
                        "Final settlement may exceed 12 hours; overrun is explicitly reported.",
                        "Stopping future starts on other PCs requires a coordinator absent from the current live bot."],
        "results": {name: summarize(rows) for name, rows in results.items()},
        "runtime_seconds": time.monotonic() - started,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--floor-lock", action="store_true")
    parser.add_argument("--laptops", type=int, default=3)
    options = parser.parse_args()
    report = run_experiment(floor_lock=options.floor_lock, laptop_count=options.laptops)
    prefix = "collective_floor_lock" if options.floor_lock else "collective_parallel"
    path = ROOT / "bulk_results" / f"{prefix}_{datetime.now(timezone.utc):%Y%m%d_%H%M%S_%f}.json"
    path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(path)
    print(json.dumps(report["results"], indent=2))
