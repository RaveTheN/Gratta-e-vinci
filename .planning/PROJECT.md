# Gratta e Vinci Refactor

## What This Is

A structural refactor of the Gratta e Vinci scratch card automation bot. The existing 3200-line monolith GUI file gets split into 5 focused modules, duplicate code is eliminated by removing the legacy `playM.py`, and fragile/buggy patterns are hardened — all without changing external behavior.

## Core Value

The codebase becomes maintainable: each module has a single responsibility, bugs can be found and fixed without reading 3000+ lines, and future features can be added without fear of breaking unrelated code.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ 5×5 tile grid automation with mouse control — existing
- ✓ Color detection (blue=win, red=loss) via pixel RGB reading — existing
- ✓ Martingale betting strategy with multiple modes (normal, medium, high, safe, custom) — existing
- ✓ Smart grid coordinate system (input key tiles, auto-calculate rest) — existing
- ✓ Interactive coordinate recording via mouse clicks — existing
- ✓ Settings persistence via JSON file — existing
- ✓ 7-tab Tkinter GUI (Settings, Coordinates, Betting Modes, Initialization, Game Control, Statistics, Pause) — existing
- ✓ Test mode for simulating games without mouse control — existing
- ✓ Stop conditions: max rounds, target win, max loss, ESC key, failsafe — existing
- ✓ Grinding mode for recovery after heavy losses — existing
- ✓ Custom betting mode with per-step difficulty/picks/bet control — existing
- ✓ Real-time mouse position monitoring — existing
- ✓ Difficulty management (set once or per-round for custom modes) — existing

### Active

<!-- Current scope. Building toward these. -->

- [ ] Split monolith into 5 modules: GameEngine, ColorDetector, CoordinateManager, SettingsManager, GUIController
- [ ] Delete playM.py and all its duplicate logic
- [ ] Fix bare except clauses — use specific exception types with logging
- [ ] Fix thread safety — replace boolean flags with threading.Event
- [ ] Fix hardcoded pause inconsistencies — consolidate all sleeps
- [ ] Fix color detection tolerance mismatch (debug says 25, code uses 50)
- [ ] Add screen bounds validation before pixel reading
- [ ] Add betting mode schema validation on load
- [ ] Optimize screenshot capture — use region grab instead of full screen

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Test coverage — separate effort after refactor stabilizes
- GUI redesign or framework change — Tkinter stays, only restructure code
- New features — pure structural refactor, no behavior changes
- playM.py migration — deleting it entirely, not merging unique logic
- Multi-account support — separate feature, not a refactor concern

## Context

- Existing brownfield codebase with codebase map already completed
- `gratta_e_vinci_gui.py` is 3201 lines with GUI, game logic, color detection, threading, async, and persistence all in one class
- `playM.py` is a legacy standalone engine with 30+ global variables, duplicating most GUI logic
- Concerns documented in `.planning/codebase/CONCERNS.md` — tech debt, known bugs, fragile areas, performance bottlenecks
- Platform: Windows only, Python 3.11+, Tkinter GUI

## Constraints

- **Behavior**: Refactored code must behave identically to current version — no functional changes
- **Framework**: Stay with Tkinter — no GUI framework changes
- **Platform**: Windows only — no cross-platform concerns
- **Dependencies**: Keep existing dependency set — no new major libraries

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 5-module split (GameEngine, ColorDetector, CoordinateManager, SettingsManager, GUIController) | Matches natural responsibility boundaries identified in architecture analysis | — Pending |
| Delete playM.py entirely | Legacy, unused, duplicates GUI logic — not worth maintaining or merging | — Pending |
| Keep Tkinter | Works fine, refactor is structural not visual — no reason to change | — Pending |
| Skip test coverage | Separate effort — refactor first, then add tests against clean modules | — Pending |

---
*Last updated: 2026-03-09 after initialization*
