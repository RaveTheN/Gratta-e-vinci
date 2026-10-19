"""Compare constant bets under an ideal collective stop; never plays online."""

from datetime import datetime, timezone
import json
import math
from pathlib import Path
import secrets
from statistics import mean
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from analysis.stable_daily_search import candidates
from bulk_simulation import (_new_run, _play_run, _validate_snapshot,
                             summarize_runs, wilson_interval)


BETS = (.1, .2, .5, 1)
DRAWDOWNS = (10, 25, 50, 100, 500)
VALIDATION = ((.1, 50), (.1, 500), (.2, 500), (.5, 500), (.2, 50))


def collective_settings(bet, drawdown):
    settings = candidates()[0]
    settings.update(starting_cash=3000, target_profit=3, max_loss=drawdown,
                    max_rounds=12000, grinding_enabled=False,
                    label=f"Medium 6, bet {bet:g} EUR, global drawdown {drawdown:g} EUR")
    settings["custom_mode"] = [{"b": bet, "p": 6, "d": "medium"}]
    return _validate_snapshot(settings)


def evaluate(settings, days, progress=None):
    if isinstance(days, bool) or not isinstance(days, int) or days < 1:
        raise ValueError("days must be a positive integer")
    settings = _validate_snapshot(settings)
    runs, stream = [], secrets.randbits(128)
    for day in range(1, days + 1):
        run = _new_run(day, settings["starting_cash"], [])
        _play_run(settings, run, [], lambda: False, lambda: None,
                  f"{stream}:collective:{day}")
        runs.append(run)
        if progress and day % 500 == 0:
            progress(day, days)
    summary = summarize_runs(runs)
    losses = sorted(-run["profit"] for run in runs if run["profit"] < 0)
    zeroes = sum(run["profit"] == 0 for run in runs)
    low, high = wilson_interval(len(losses), days)
    summary.update(negative_days=len(losses), zero_days=zeroes,
                   nonpositive_rate=100 * (len(losses) + zeroes) / days,
                   negative_ci_low=low, negative_ci_high=high,
                   avg_loss_on_negative_day=mean(losses) if losses else None,
                   loss_p95_on_negative_day=losses[math.ceil(.95 * len(losses)) - 1] if losses else None)
    return {"settings": settings, "days": days, "group": summary}


def main():
    started = time.monotonic()
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "synthetic_uniform_independent_boards",
        "confirmed_rules": {"medium_mines": 6, "board_size": 25,
                            "six_pick_total_multiplier": 6.8},
        "costs_included": False, "real_history_used": False,
        "implemented_in_real_bot": False,
        "method": "Three IID PC streams have the same aggregate financial law as "
                  "one stream of settled constant bets. The global target is 3 EUR; "
                  "capital resets to 3000 EUR each day and the global cap is 12000 bets. "
                  "Individual PC balances, timing and pending simultaneous bets are not modeled.",
        "selection": "The five validation combinations were declared before screening; "
                     "each uses fresh independent streams. No adaptive winner selection.",
        "loss_p95_method": "Nearest-rank 95th percentile of positive loss amounts on negative days only.",
        "validation_shortlist": [{"bet": bet, "global_drawdown": loss} for bet, loss in VALIDATION],
        "screening": [], "validation": [],
    }
    for phase, combinations, days in (
        ("screening", [(bet, loss) for bet in BETS for loss in DRAWDOWNS], 1000),
        ("validation", VALIDATION, 10000),
    ):
        for bet, drawdown in combinations:
            settings = collective_settings(bet, drawdown)
            label = f"{phase}: {settings['label']}"
            result = evaluate(settings, days,
                progress=lambda done, total: print(f"{label}: {done}/{total}", flush=True))
            report[phase].append(result)
            group = result["group"]
            print(f"{label}: negative {group['negative_rate']:.3f}%, "
                  f"mean {group['avg_profit']:.4f} EUR, worst {group['min_profit']:.2f} EUR", flush=True)
    report["elapsed_seconds"] = time.monotonic() - started
    output_dir = ROOT / "bulk_results"
    output_dir.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%fZ")
    path = output_dir / f"collective_bet_search_{stamp}.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)
    print(f"Report: {path}", flush=True)


if __name__ == "__main__":
    main()
