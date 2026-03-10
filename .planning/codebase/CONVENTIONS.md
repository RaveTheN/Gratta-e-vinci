# Coding Conventions

**Analysis Date:** 2026-03-10

## Naming Patterns

**Files:**
- Use `snake_case.py` for all Python modules: `game_config.py`, `color_detector.py`, `settings_manager.py`
- Exception: `mouseMonitoring.py` uses camelCase (legacy, not actively maintained)
- Main GUI file: `gratta_e_vinci_gui.py`
- Settings file: `gratta_settings.json`

**Classes:**
- Use `PascalCase`: `GrattaEVinciGUI`, `GameEngine`, `TkAutomationAdapter`, `ColorDetector`, `CoordinateManager`, `CoordinateRecorder`, `SettingsManager`, `Point`
- One primary class per module (except `game_engine.py` which has `GameEngine` + `TkAutomationAdapter`)

**Functions/Methods:**
- Use `snake_case` for all methods: `start_game()`, `validate_settings()`, `play_or_collect()`
- Private methods prefixed with single underscore: `_is_running()`, `_get_min_bet_for_selected_mode()`, `_apply_test_win()`
- Callback methods use `on_` prefix: `on_save_settings()`, `on_load_settings()`
- Internal event handlers use `_on_` prefix: `_on_mode_var_changed()`, `_on_grinding_toggle()`, `_on_color_tolerance_changed()`

**Variables:**
- Tkinter variables use `_var` suffix: `starting_cash_var`, `mode_var`, `play_x_var`, `sleep_after_play_var`
- Tkinter labels use `_label` suffix: `current_cash_label`, `progress_label`
- Boolean flags use descriptive names: `game_running`, `escape_pressed`, `mouse_monitoring`, `grinding_active`
- Sleep/pause variables follow `sleep_<action>_var` pattern: `sleep_play_or_collect_var`, `sleep_click_tile_var`

**Constants:**
- Use `UPPER_SNAKE_CASE` in `game_config.py`: `BETTING_MODES`, `WIN_MULTIPLIERS`, `BET_VALUES`, `TARGET_BLUE`, `COLOR_TOLERANCE`, `GRINDING_STEP`

**Tkinter Widget References:**
- Buttons: `start_button`, `stop_button`
- Frames: `control_frame`, `stats_grid`
- Trees: `init_tree`

## Code Style

**Formatting:**
- No automated formatter detected (no `.prettierrc`, `pyproject.toml`, `setup.cfg`, or linting config)
- 4-space indentation throughout
- Line length varies; some lines exceed 120 characters (especially in `game_engine.py` condition checks)
- Use double quotes for strings consistently in newer modules (`game_engine.py`, `settings_manager.py`, `color_detector.py`)
- Mixed quote styles in `gratta_e_vinci_gui.py` (both single and double)

**Linting:**
- No linting tool configured (no `.flake8`, `pylintrc`, `ruff.toml`, or equivalent)
- Recommend adding `ruff` or `flake8` for consistency

**Type Hints:**
- Used in newer extracted modules: `color_detector.py`, `settings_manager.py`, `game_engine.py`
- Pattern: `from __future__ import annotations` at top of newer modules
- Not used in `gratta_e_vinci_gui.py` (legacy monolith) or `game_config.py`
- Use `dict[str, int]` and `list[str]` (modern syntax with `__future__` annotations)
- Use `| None` union syntax: `target_blue: dict[str, int] | None = None`

## Import Organization

**Order:**
1. Standard library: `import tkinter`, `import threading`, `import asyncio`, `import json`, `import os`, `import time`, `import random`
2. Third-party: `import pyautogui`, `from pynput import keyboard, mouse`, `from PIL import ImageGrab`
3. Local modules: `import color_detector`, `from game_config import ...`, `from game_engine import GameEngine`

**Patterns:**
- Mix of module imports (`import color_detector`) and named imports (`from game_config import Point, BETTING_MODES`)
- In `gratta_e_vinci_gui.py`, both styles are used for the same module (e.g., `import color_detector` AND `from color_detector import ColorDetector`)
- Lazy imports inside functions: `from tkinter import filedialog` and `import datetime` used inside method bodies for rarely-used features

**Path Aliases:**
- None. All imports are direct module names (flat structure, no packages)

## Error Handling

**Patterns:**
- Broad `except Exception as e` used throughout for safety in GUI context
- User-facing errors shown via `messagebox.showerror()`: `on_save_settings()`, `start_game()`
- Non-critical errors logged via `self.log_message(f"[WARN] ...")` or `self.log_message(f"... Error: {e}")`
- Settings validation returns a list of error strings: `SettingsManager.validate()` in `settings_manager.py`
- Game engine validation raises `ValueError` for invalid settings: `GameEngine.validate_settings()` in `game_engine.py`
- Color detection returns fallback value on error: `{"r": 0, "g": 0, "b": 0, "a": 255}` in `game_engine.py` line 85

**Error display convention:**
```python
# Critical errors: messagebox
messagebox.showerror("Invalid Settings", str(e))

# Runtime errors: log with emoji prefix
self.log_message(f"[WARN] Mouse monitor stopped due to error: {e}")
self.log_message(f"... TEST MODE error: {e}")
```

## Logging

**Framework:** Custom `log_message()` method on `GrattaEVinciGUI` class (`gratta_e_vinci_gui.py` line 2495)

**Pattern:**
```python
def log_message(self, message):
    timestamp = time.strftime("%H:%M:%S")
    full_message = f"[{timestamp}] {message}\n"
    self.root.after(0, lambda: self.status_text.insert(tk.END, full_message))
    self.root.after(0, lambda: self.status_text.see(tk.END))
```

**Log message conventions:**
- Use emoji prefixes for visual categorization in log output
- Game events: `[HIT]`, `[LOSS]`, `[WIN]`, `[ROUND]`, `[BOARD]`, `[COLOR]`, `[GRIND]`, `[STOP]`, `[SUMMARY]`
- Warnings: `[WARN]`
- No structured logging library; all output goes to Tkinter `ScrolledText` widget
- Thread-safe via `self.root.after(0, ...)` to marshal to main thread

**When to log:**
- Every game action (tile click, color detection, bet change, round start/end)
- Settings load/save results
- Error conditions
- State transitions (grinding activation, game start/stop)

## Comments

**When to Comment:**
- Docstrings on all public methods in extracted modules (`game_engine.py`, `settings_manager.py`, `color_detector.py`)
- Module-level docstrings present on all `.py` files
- Inline comments for non-obvious logic (e.g., `# Click lower bet button multiple times to ensure minimum`)
- Section comments with `# ---` separators in `game_config.py` for grouping constants

**Docstring Style:**
```python
"""Short one-line description."""

"""Multi-line docstring.
Additional details on second line if needed.
"""
```

**Language:**
- Code comments and docstrings: predominantly English
- Some Italian strings in UI labels and log messages (mixed): `"Forza Bet al Minimo"`, `"Difficolt forzata al minimo"`, `"Nessuno step di inizializzazione configurato"`
- Italian is used for user-facing GUI labels in the Initialization Steps tab and Pauses tab

## Function Design

**Size:**
- Methods in `gratta_e_vinci_gui.py` range from 2-line wrappers to 100+ line GUI builders
- Game logic methods (`play_real_game_round`, `run_test_mode`) are 80-100+ lines
- Extracted modules have shorter methods (5-30 lines typically)

**Parameters:**
- Use `self.app` reference pattern: extracted modules (`GameEngine`, `TkAutomationAdapter`) hold a reference to the GUI app
- Dicts used for complex return values: `_get_round_config_for_strategy()` returns a dict with 8+ keys
- Optional params with `None` defaults: `_get_target_bet_for_try(self, tries=None, selected_mode_name=None)`

**Return Values:**
- Dicts for structured data: `{"r": 0, "g": 0, "b": 0, "a": 255}` for colors, `{"mine_count": ..., "hit_mine": ...}` for board simulation
- `round(value, 2)` used consistently for monetary values to avoid floating-point issues
- Boolean returns for validation: `validate_settings()` returns `True` or raises

## Module Design

**Exports:**
- Each module exports its primary class(es)
- `game_config.py` exports constants and the `Point` class (no `__all__` defined)
- No `__init__.py` files (flat module structure, not a package)

**Barrel Files:**
- Not used. Each module imported directly.

**Adapter Pattern:**
- `TkAutomationAdapter` in `game_engine.py` wraps GUI-specific I/O (mouse clicks, color reading)
- `GameEngine` delegates all physical actions through the adapter
- This separation enables test mode (simulated board) vs real mode (actual mouse automation)

## Threading Conventions

**Pattern:**
- Game loop runs in a daemon thread: `threading.Thread(target=..., daemon=True).start()`
- Asyncio event loop created per-thread: `loop = asyncio.new_event_loop()`
- GUI updates marshaled via `self.root.after(0, callback)` from worker threads
- Stop signaling via `threading.Event`: `stop_event`, `running_event`
- Mouse monitoring runs in a separate daemon thread with `time.sleep(0.1)` polling

**Thread Safety:**
- All GUI updates go through `root.after(0, ...)` -- follow this pattern strictly
- State flags (`game_running`, `escape_pressed`) accessed from multiple threads without locks
- `pynput.keyboard.Listener` and `pynput.mouse.Listener` run in their own threads

## Money/Value Formatting

**Pattern:**
- Always use `round(value, 2)` when setting monetary values
- Display via `format_money()` from `game_config.py`: `f"{round(value, 2):.2f}"`
- Instance wrapper: `self.format_money(value)` delegates to module-level `format_money()`

---

*Convention analysis: 2026-03-10*
