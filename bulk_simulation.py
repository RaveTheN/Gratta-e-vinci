"""Repeatable bulk simulations, independent of Tk and the global random generator."""

from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from itertools import product
from functools import lru_cache
import math
import random
import secrets
from statistics import mean, median, stdev
import time

from game_config import GRINDING_STEP, TEST_MODE_BOARD_SIZE, BETTING_MODES, MAX_PICKS


SIMULATOR_VERSION = "3.1"
STOP_STATUSES = ("target", "max_loss", "max_rounds", "insufficient_funds", "interrupted",
                 "time_limit", "preventive_stop", "total_loss", "period_end")
DIFFICULTIES = ("low", "medium", "high")


def _number(value, name, minimum=0, positive=False):
    if isinstance(value, bool):
        raise ValueError(f"{name}: inserire un numero, non un valore booleano")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{name}: inserire un numero valido") from exc
    if not math.isfinite(number) or number < minimum or (positive and number == 0):
        raise ValueError(f"{name}: valore finito {'positivo' if positive else f'>= {minimum}'} richiesto")
    return number


def _integer(value, name, minimum=0):
    number = _number(value, name, minimum)
    if number != int(number):
        raise ValueError(f"{name}: inserire un intero")
    return int(number)


def _money(value, name, positive=True):
    number = round(_number(value, name, positive=positive), 2)
    if positive and number < 0.01:
        raise ValueError(f"{name}: almeno 0.01 richiesto")
    if not math.isfinite(number * 100):
        raise ValueError(f"{name}: importo troppo grande")
    return number


def _validate_snapshot(settings):
    """Copy and normalize one simulation's inputs, including JSON multiplier keys."""
    snap = deepcopy(settings)
    if snap["mode"] not in (*BETTING_MODES, "custom"):
        raise ValueError("Modalita non disponibile")
    for key in ("starting_cash", "target_profit", "max_loss"):
        snap[key] = _money(snap[key], key)
    snap["max_rounds"] = _integer(snap["max_rounds"], "max_rounds", 1)
    snap["grinding_range"] = _money(snap.get("grinding_range", 0), "grinding_range", positive=False)
    for key in ("grinding_enabled", "p_random"):
        if not isinstance(snap.get(key, False), bool):
            raise ValueError(f"{key}: valore booleano richiesto")
        snap[key] = snap.get(key, False)
    snap["max_picks"] = _integer(snap["max_picks"], "max_picks", 1)
    if snap["max_picks"] > MAX_PICKS:
        raise ValueError(f"max_picks: scegliere da 1 a {MAX_PICKS}")
    if snap["difficulty"] not in DIFFICULTIES:
        raise ValueError("Difficoltà non valida")

    for difficulty in DIFFICULTIES:
        mines = _integer(snap["mine_config"][difficulty], f"Mine {difficulty}")
        if mines > TEST_MODE_BOARD_SIZE:
            raise ValueError(f"Mine {difficulty}: massimo {TEST_MODE_BOARD_SIZE}")
        snap["mine_config"][difficulty] = mines
        multipliers = snap["win_multipliers"][difficulty]
        snap["win_multipliers"][difficulty] = {
            picks: _number(multipliers.get(picks, multipliers.get(str(picks))),
                           f"Moltiplicatore {difficulty}/{picks}", positive=True)
            for picks in range(1, MAX_PICKS + 1)
            if picks <= 4 or picks in multipliers or str(picks) in multipliers
        }

    allowed = None
    if "bet_values" in snap:
        snap["bet_values"] = [_money(value, "Puntata ammessa") for value in snap["bet_values"]]
        if not snap["bet_values"]:
            raise ValueError("La lista delle puntate ammesse è vuota")
        allowed = set(snap["bet_values"])

    def validate_bet(value):
        bet = _money(value, "Puntata")
        if allowed is not None and bet not in allowed:
            raise ValueError(f"Puntata {bet:g} non presente nei valori ammessi")
        if any(not math.isfinite(bet * 100 * multiplier)
               for multipliers in snap["win_multipliers"].values()
               for multiplier in multipliers.values()):
            raise ValueError("Puntata/moltiplicatore troppo grandi")
        return bet

    if "betting_modes" in snap:
        snap["betting_modes"] = {
            name: [_money(value, f"Puntata {name}") for value in sequence]
            for name, sequence in snap["betting_modes"].items()
        }
    steps = snap.get("custom_mode", [])
    for step in steps:
        step["b"] = (validate_bet(step["b"]) if snap["mode"] == "custom"
                     else _money(step["b"], "Puntata custom"))
        step["p"] = _integer(step["p"], "Picks custom", 1)
        if step["p"] > MAX_PICKS or step["d"] not in DIFFICULTIES:
            raise ValueError(f"Step custom: picks 1..{MAX_PICKS} e difficoltà low/medium/high richiesti")
        if step["p"] not in snap["win_multipliers"][step["d"]]:
            raise ValueError(f"Moltiplicatore mancante per {step['d']} con {step['p']} celle")
    if snap["mode"] == "custom":
        if not steps:
            raise ValueError("La modalità custom non contiene step")
        snap["betting_sequence"] = [step["b"] for step in steps]
    else:
        if snap["max_picks"] not in snap["win_multipliers"][snap["difficulty"]]:
            raise ValueError(f"Moltiplicatore mancante per {snap['difficulty']} con {snap['max_picks']} celle")
        sequences = snap.get("betting_modes", {})
        sequence = sequences.get(snap["mode"], snap.get("betting_sequence", []))
        if not sequence:
            raise ValueError(f"Sequenza puntate vuota: {snap['mode']}")
        snap["betting_sequence"] = [validate_bet(value) for value in sequence]
    if snap["grinding_enabled"]:
        validate_bet(GRINDING_STEP["b"])
    return snap


def build_configurations(base, modes=None, difficulties=None, picks=None, grinding=None):
    """Build distinct combinations; retained for the engine convenience API."""
    selections = (
        list(modes) if modes is not None else [base["mode"]],
        list(difficulties) if difficulties is not None else [base["difficulty"]],
        list(picks) if picks is not None else [base["max_picks"]],
        list(grinding) if grinding is not None else [base.get("grinding_enabled", False)],
    )
    if any(not selection for selection in selections):
        raise ValueError("Selezionare almeno un valore per ogni parametro di confronto")
    configurations, seen = [], set()
    for mode, difficulty, max_picks, grinding_enabled in product(*selections):
        key = (mode, None if mode == "custom" else difficulty,
               None if mode == "custom" else max_picks, grinding_enabled)
        if key in seen:
            continue
        seen.add(key)
        snap = deepcopy(base)
        snap.update(mode=mode, grinding_enabled=grinding_enabled)
        if mode != "custom":
            if "betting_modes" in snap and mode not in snap["betting_modes"]:
                raise ValueError(f"Modalità non disponibile: {mode}")
            snap.update(difficulty=difficulty, max_picks=max_picks)
        snap = _validate_snapshot(snap)
        strategy = "step custom" if mode == "custom" else f"{difficulty}, {max_picks} picks"
        snap["label"] = f"{mode} | {strategy} | grinding {'sì' if grinding_enabled else 'no'}"
        configurations.append(snap)
    return configurations


@lru_cache(maxsize=(TEST_MODE_BOARD_SIZE + 1) * MAX_PICKS)
def win_probability(mines, picks):
    return math.comb(TEST_MODE_BOARD_SIZE - mines, picks) / math.comb(TEST_MODE_BOARD_SIZE, picks)


def wilson_interval(successes, total):
    """95% Wilson interval as percentages; an empty sample has no interval."""
    if not total:
        return None, None
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, (center - spread) * 100), min(100.0, (center + spread) * 100)


def summarize_runs(runs, risk_threshold=100):
    """Summarize completed sessions only; preserve counts of interrupted sessions."""
    complete = [run for run in runs if run["status"] != "interrupted"]
    counts = Counter(run["status"] for run in runs)
    total = len(complete)
    summary = {
        "completed_runs": total,
        "interrupted_runs": counts["interrupted"],
        "stop_counts": {status: counts[status] for status in STOP_STATUSES},
    }
    for name in ("target_rate", "positive_rate", "avg_profit", "median_profit", "min_profit",
                 "max_profit", "p05_profit", "p95_profit", "avg_rounds", "max_drawdown",
                 "target_ci_low", "target_ci_high", "positive_ci_low", "positive_ci_high"):
        summary[name] = None
    if not total:
        return summary
    profits = sorted(run["profit"] for run in complete)

    def percentile(fraction):
        position = (total - 1) * fraction
        lower = math.floor(position)
        upper = math.ceil(position)
        return profits[lower] + (profits[upper] - profits[lower]) * (position - lower)

    positives = sum(profit > 0 for profit in profits)
    summary.update(
        target_rate=100 * counts["target"] / total,
        positive_rate=100 * positives / total,
        avg_profit=mean(profits), median_profit=median(profits),
        min_profit=profits[0], max_profit=profits[-1],
        p05_profit=percentile(0.05), p95_profit=percentile(0.95),
        avg_rounds=mean(run["rounds"] for run in complete),
        max_drawdown=max(run["max_drawdown"] for run in complete),
    )
    summary["target_ci_low"], summary["target_ci_high"] = wilson_interval(counts["target"], total)
    summary["positive_ci_low"], summary["positive_ci_high"] = wilson_interval(positives, total)
    if counts["period_end"]:
        summary.update(target_rate=None, target_ci_low=None, target_ci_high=None)
    summary.update(economic_summary(complete, risk_threshold))
    return summary


def economic_summary(runs, risk_threshold=100):
    profits = sorted(run["profit"] for run in runs)
    n = len(profits)
    if not n:
        return {}
    average = mean(profits)
    # Normal approximation across independent replicas. Small/constant samples
    # deliberately have no interval: they cannot describe unseen rare losses.
    error = 1.959963984540054 * stdev(profits) / math.sqrt(n) if n >= 30 and profits[0] != profits[-1] else None
    result = {
        "total_profit": math.fsum(profits),
        "total_gains": math.fsum(p for p in profits if p > 0),
        "total_losses": math.fsum(p for p in profits if p < 0),
        "negative_rate": 100 * sum(p < 0 for p in profits) / n,
        "large_loss_rate": 100 * sum(p < -risk_threshold for p in profits) / n,
        "risk_threshold": risk_threshold,
        "worst5_avg": mean(profits[:max(1, math.ceil(n * .05))]),
        "profit_ci_low": average - error if error is not None else None,
        "profit_ci_high": average + error if error is not None else None,
        "funds_stop_rate": 100 * sum(r.get("funds_stops", int(r["status"] == "insufficient_funds")) > 0 for r in runs) / n,
        "avg_topups": mean(r.get("topups", 0) for r in runs),
        "avg_costs": mean(r.get("costs", 0) for r in runs),
        "avg_wagered": mean(r.get("wagered", 0) for r in runs),
    }
    return result


class _ProgressSummary:
    """Cheap progress summaries; exact percentiles are calculated only at a boundary."""
    def __init__(self, runs):
        self.n = self.positive = self.rounds = 0
        self.total = self.dd = 0.0
        self.low = self.high = None
        self.counts = Counter()
        for run in runs:
            self.add(run)

    def add(self, run):
        self.n += 1
        self.total += run["profit"]
        self.positive += run["profit"] > 0
        self.rounds += run["rounds"]
        self.dd = max(self.dd, run["max_drawdown"])
        self.low = run["profit"] if self.low is None else min(self.low, run["profit"])
        self.high = run["profit"] if self.high is None else max(self.high, run["profit"])
        self.counts[run["status"]] += 1

    def snapshot(self, partial):
        result = summarize_runs([])
        result.update(completed_runs=self.n, interrupted_runs=int(partial),
                      stop_counts={s: (int(partial) if s == "interrupted" else self.counts[s]) for s in STOP_STATUSES})
        if self.n:
            result.update(avg_profit=self.total / self.n, min_profit=self.low, max_profit=self.high,
                          avg_rounds=self.rounds / self.n, max_drawdown=self.dd,
                          positive_rate=self.positive / self.n * 100,
                          target_rate=self.counts["target"] / self.n * 100)
            result["positive_ci_low"], result["positive_ci_high"] = wilson_interval(self.positive, self.n)
            result["target_ci_low"], result["target_ci_high"] = wilson_interval(self.counts["target"], self.n)
            if self.counts["period_end"]:
                result.update(target_rate=None, target_ci_low=None, target_ci_high=None)
        return result


def _thresholds(maximum, step):
    """All thresholds use cents and always end at the exact configured limit."""
    maximum_cents = int(round(maximum * 100))
    step_cents = int(round(step * 100))
    return [value / 100 for value in range(step_cents, maximum_cents, step_cents)] + [maximum]


def _payout_cents(bet_cents, multiplier):
    """Match runtime's round(bet * multiplier, 2), then keep balances in cents."""
    return int(round(round((bet_cents / 100) * multiplier, 2) * 100))


def _play_run(snap, run, profit_thresholds, stop_check, checkpoint, rng_seed):
    rng = random.Random(rng_seed)
    picks_rng = random.Random(f"{rng_seed}:grinding")
    cash = start = int(round(snap["starting_cash"] * 100))
    peak, max_drawdown, tries = cash, 0, 0
    target = int(round(snap["target_profit"] * 100))
    loss_limit = int(round(snap["max_loss"] * 100))
    grinding_range = int(round(snap["grinding_range"] * 100))
    steps = (snap["custom_mode"] if snap["mode"] == "custom" else
             [{"b": bet, "p": snap["max_picks"], "d": snap["difficulty"]}
              for bet in snap["betting_sequence"]])
    profit_cents = [int(round(value * 100)) for value in profit_thresholds]
    grinding_active, grinding_target, reached = False, None, 0
    status = "max_rounds"
    run["wagered"] = 0.0
    for _ in range(snap["max_rounds"]):
        if stop_check():
            status = "interrupted"
            break
        step_index = min(tries, len(steps) - 1)
        step = steps[step_index]
        bet = int(round((GRINDING_STEP["b"] if grinding_active else step["b"]) * 100))
        difficulty = GRINDING_STEP["d"] if grinding_active else step["d"]
        picks = step["p"]
        if grinding_active:
            for picks in (1, 2, 3):
                payout = _payout_cents(bet, snap["win_multipliers"][difficulty][picks])
                if cash - bet + payout >= grinding_target:
                    break
            else:
                picks = picks_rng.randint(1, 3) if snap["p_random"] else 3
        if cash < bet:
            status = "insufficient_funds"
            break
        cash -= bet
        run["wagered"] = round(run["wagered"] + bet / 100, 2)
        # Exact probability of drawing only safe tiles without replacement.
        # Each session draws from its laptop's own stream, without allocating a board.
        hit_mine = rng.random() >= win_probability(snap["mine_config"][difficulty], picks)
        if hit_mine:
            if snap["grinding_enabled"] and not grinding_active and step_index == 0:
                grinding_target = peak - grinding_range
            tries += 1
            if (snap["grinding_enabled"] and not grinding_active
                    and step_index == len(steps) - 1
                    and bet == int(round(GRINDING_STEP["b"] * 100))
                    and grinding_target is not None):
                grinding_active = True
        else:
            cash += _payout_cents(bet, snap["win_multipliers"][difficulty][picks])
            if not grinding_active or cash >= grinding_target:
                grinding_active = False
                tries = 0
        peak = max(peak, cash)
        max_drawdown = max(max_drawdown, peak - cash)
        profit = cash - start
        while reached < len(profit_cents) and profit >= profit_cents[reached]:
            run["threshold_drawdowns"][reached] = max_drawdown / 100
            reached += 1
        run.update(rounds=run["rounds"] + 1, final_cash=cash / 100, profit=profit / 100,
                   peak_cash=peak / 100, max_drawdown=max_drawdown / 100)
        if profit >= target:
            status = "target"
            break
        if max_drawdown >= loss_limit:
            status = "max_loss"
            break
        checkpoint()
    run["status"] = status


def _new_run(index, cash, thresholds):
    return {"index": index, "status": "interrupted", "rounds": 0,
            "final_cash": cash, "profit": 0.0, "max_drawdown": 0.0,
            "peak_cash": cash, "threshold_drawdowns": [None] * len(thresholds)}


def run_bulk_batch(settings_list, n_runs, seed, progress_cb, log_cb, stop_check,
                   show_logs, checkpoint_cb=None):
    """Run independent sessions. The optional RNG initializer is internal, never exported."""
    n_runs = _integer(n_runs, "Numero simulazioni", 1)
    if seed is None:
        seed = secrets.randbits(63)
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise ValueError("Seed: inserire un intero >= 0")
    settings_list = [_validate_snapshot(settings) for settings in settings_list]
    if not settings_list:
        raise ValueError("Nessuna configurazione da simulare")
    start_time = time.monotonic()
    batch = {"schema_version": 3, "simulator_version": SIMULATOR_VERSION,
             "created_at": datetime.now(timezone.utc).isoformat(), "requested_runs": n_runs, "status": "running",
             "elapsed_seconds": 0.0, "configurations": []}
    for index, snap in enumerate(settings_list, 1):
        profits = _thresholds(snap["target_profit"], max(1, math.ceil(snap["target_profit"] / 100)))
        losses = _thresholds(snap["max_loss"], max(5, math.ceil(snap["max_loss"] / 100)))
        batch["configurations"].append({
            "id": index, "label": snap.get("label", snap["mode"]), "settings": snap,
            "profit_thresholds": profits, "loss_thresholds": losses,
            "success_counts": [[0 for _ in profits] for _ in losses],
            "runs": [], "summary": summarize_runs([]),
        })

    completed = sum(len(c["runs"]) for c in batch["configurations"])
    total = n_runs * len(settings_list)
    last_checkpoint = start_time
    active = None
    accumulator = None

    def checkpoint(force=False):
        nonlocal last_checkpoint
        now = time.monotonic()
        if force or (checkpoint_cb is not None and now - last_checkpoint >= 5):
            batch["elapsed_seconds"] = now - start_time
            if active is not None:
                active["summary"] = (summarize_runs(active["runs"], active["settings"].get("risk_threshold", 100))
                                     if force else accumulator.snapshot(
                                         bool(active["runs"] and active["runs"][-1]["status"] == "interrupted")))
            if checkpoint_cb is not None:
                checkpoint_cb(batch)
            last_checkpoint = now

    checkpoint(force=True)
    interrupted = False
    for active in batch["configurations"]:
        accumulator = _ProgressSummary(active["runs"])
        for index in range(len(active["runs"]) + 1, n_runs + 1):
            if stop_check():
                interrupted = True
                break
            run = _new_run(index, active["settings"]["starting_cash"], active["profit_thresholds"])
            active["runs"].append(run)
            # Each laptop/session owns a distinct random stream, even when its
            # settings are identical to another laptop. No outcomes are shared.
            _play_run(active["settings"], run, active["profit_thresholds"], stop_check, checkpoint,
                      f"{seed}:laptop:{active['id']}:session:{index}")
            if run["status"] == "interrupted":
                interrupted = True
                break
            accumulator.add(run)
            for column, drawdown in enumerate(run["threshold_drawdowns"]):
                if drawdown is not None:
                    for row, loss in enumerate(active["loss_thresholds"]):
                        if drawdown <= loss:
                            active["success_counts"][row][column] += 1
            completed += 1
            progress_cb(completed, total)
            if show_logs():
                log_cb(f"[{active['id']}/{len(settings_list)} · Run {index}/{n_runs}] "
                       f"{run['status']} | profitto {run['profit']:+.2f} | "
                       f"DD max {run['max_drawdown']:.2f} | round {run['rounds']}")
            checkpoint()
        checkpoint(force=True)
        if interrupted:
            break
    batch["status"] = "interrupted" if interrupted else "completed"
    checkpoint(force=True)
    return batch
