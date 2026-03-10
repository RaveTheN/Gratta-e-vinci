# Architecture

**Analysis Date:** 2026-03-10

## Pattern Overview

**Overall:** Monolithic GUI application with partial extraction toward a layered architecture (ongoing refactor)

**Key Characteristics:**
- Single Tkinter GUI class (`GrattaEVinciGUI`, ~2963 lines) acts as both presentation and application controller
- Game engine (`GameEngine`) extracted as a separate class but tightly coupled to the GUI via `self.app` back-reference
- Adapter pattern (`TkAutomationAdapter`) bridges engine I/O actions to physical mouse/screen automation
- Shared constants module (`game_config`) provides domain types and configuration values
- Settings persistence via a dedicated `SettingsManager` class
- Coordinate grid logic extracted to `CoordinateManager` / `CoordinateRecorder`

## Layers

**Presentation (GUI):**
- Purpose: Tkinter window with 7 tabbed panes; renders settings, coordinates, betting modes, init steps, game control, statistics, and pause configuration
- Location: `gratta_e_vinci_gui.py` (class `GrattaEVinciGUI`)
- Contains: All widget creation (`create_*_tab` methods), user event handlers, modal editor windows
- Depends on: `game_engine`, `color_detector`, `coordinate_manager`, `settings_manager`, `game_config`
- Used by: Entry point at bottom of `gratta_e_vinci_gui.py`

**Game Engine:**
- Purpose: Owns the runtime game loop, strategy/state transitions, test mode simulation, and initialization step execution
- Location: `game_engine.py` (class `GameEngine`)
- Contains: `main_game_loop`, `play_real_game_round`, `run_test_mode`, bet/difficulty management, win/loss application
- Depends on: `game_config` (constants), `TkAutomationAdapter` (I/O), GUI app instance for state (via `self.app`)
- Used by: `GrattaEVinciGUI.start_game()`, `GrattaEVinciGUI.start_test_mode()`

**Automation Adapter:**
- Purpose: Translates high-level game actions (click tile, increase bet, read color) into physical pyautogui calls and screen reads
- Location: `game_engine.py` (class `TkAutomationAdapter`)
- Contains: `play_or_collect`, `increase_bet`, `decrease_bet`, `click_tile`, `read_color`, `set_difficulty`
- Depends on: `pyautogui`, `ColorDetector`, GUI app instance for coordinate/sleep variables
- Used by: `GameEngine`

**Color Detection:**
- Purpose: Screenshot a single pixel and classify it as blue (win), red (loss), or unknown
- Location: `color_detector.py` (class `ColorDetector`)
- Contains: `read_color_at_point`, `is_color_in_range_blue`, `is_color_in_range_red`
- Depends on: `pyautogui`, `PIL.ImageGrab`, `game_config` (default color constants)
- Used by: `TkAutomationAdapter`

**Coordinate Management:**
- Purpose: Smart grid calculation (5x5 tile positions from 9 input points) and interactive recording overlay
- Location: `coordinate_manager.py` (classes `CoordinateManager`, `CoordinateRecorder`)
- Contains: `populate_tile_vars`, `build_tile_points`, `build_preview_text`, full recording workflow with keyboard/mouse listeners
- Depends on: `tkinter`, `pynput`, `game_config.Point`
- Used by: `GrattaEVinciGUI`

**Settings Persistence:**
- Purpose: Load/save/validate JSON settings with defaults and schema checks
- Location: `settings_manager.py` (class `SettingsManager`)
- Contains: `load_settings`, `save_settings`, `validate`, `merge_with_defaults`, `save_custom_mode`
- Depends on: `game_config.BETTING_MODES`
- Used by: `GrattaEVinciGUI`

**Shared Configuration:**
- Purpose: Domain types (`Point`), constants (betting modes, colors, multipliers), and utility functions
- Location: `game_config.py`
- Contains: `Point` class, `BETTING_MODES`, `WIN_MULTIPLIERS`, `BET_VALUES`, `TARGET_BLUE`, `TARGET_RED`, `COLOR_TOLERANCE`, `GRINDING_STEP`, `TEST_MODE_*`, `format_money`
- Depends on: Nothing (leaf module)
- Used by: All other modules

## Data Flow

**Real Game Round:**

1. User clicks "START GAME" in Game Control tab -> `GrattaEVinciGUI.start_game()`
2. GUI validates settings via `GameEngine.validate_settings()`, shows confirmation dialog
3. Sets `game_running=True`, `running_event`, initializes game variables
4. Spawns daemon thread running `GameEngine.run_game_async()` which creates a new asyncio event loop
5. Engine executes init steps (configurable sequence: force min bet, set difficulty, etc.)
6. Main loop: check stop conditions -> `play_real_game_round()`
7. Round: resolve strategy config -> set difficulty/bet via adapter -> click play -> pick random tiles
8. For each tile: `TkAutomationAdapter.click_tile()` -> sleep -> `read_color()` -> classify blue/red/unknown
9. Blue: increment picks, check if won. Red: apply loss, escalate bet per Martingale. Unknown: retry with sleep
10. Win: collect winnings, reset bet to minimum. Loss: increment tries, set next bet in sequence
11. GUI stats updated via `root.after(0, ...)` thread-safe callbacks

**Test Mode (Simulation):**

1. User clicks "TEST MODE" -> `GrattaEVinciGUI.start_test_mode()`
2. Same init as real mode but spawns `GameEngine.run_test_mode()` in daemon thread
3. Each round: `_simulate_test_board()` creates randomized 5x5 grid with mines/coins
4. Board result determines win/loss; applies via `_apply_test_win()` / `_apply_test_loss()`
5. No physical mouse clicks; runs at high speed with minimal delays
6. Verbosity: first 5 rounds detailed, then every 25th round summarized

**Settings Load/Save:**

1. On startup: `SettingsManager.load_settings("gratta_settings.json")` -> merge with defaults
2. GUI populates all `tk.*Var` widgets from loaded payload
3. On save: GUI collects all widget values into payload dict -> `SettingsManager.save_settings()`

**State Management:**
- Game state is stored as instance variables on `GrattaEVinciGUI`: `current_cash`, `highest_cash`, `bet`, `tries`, `rounds`, `loss`, `grinding_active`, etc.
- `GameEngine` and `TkAutomationAdapter` access state via `self.app` back-reference
- Thread synchronization: `threading.Event` objects (`stop_event`, `running_event`) plus `game_running` boolean
- GUI updates from game thread use `root.after(0, callback)` for thread safety
- `pynput.keyboard.Listener` runs in its own thread for ESC key detection

## Key Abstractions

**Point:**
- Purpose: Represents a screen coordinate (x, y)
- Examples: `game_config.py` line 6
- Pattern: Simple value object with `.x` and `.y` attributes

**Betting Mode (Standard):**
- Purpose: Array of escalating bet values indexed by loss count (`tries`)
- Examples: `game_config.BETTING_MODES["normal"]` = `[0.1, 0.2, 0.3, ...]`
- Pattern: Dictionary of string keys to float arrays

**Betting Mode (Custom):**
- Purpose: Array of step objects with bet, picks, and difficulty per step
- Examples: `self.custom_mode = [{"b": 0.1, "p": 2, "d": "low"}, ...]`
- Pattern: List of dicts, each step controls all round parameters

**Round Config:**
- Purpose: Resolved configuration for current round (picks, difficulty, bet, multiplier)
- Examples: returned by `GameEngine._get_round_config_for_strategy()`
- Pattern: Dict with keys: `selected_mode_name`, `strategy_source`, `max_picks`, `round_difficulty`, `target_bet`, `multiplier`, etc.

**Init Steps:**
- Purpose: User-defined sequence of actions to run before the game loop starts
- Examples: `[{"action": "set_bet_min"}, {"action": "raise_difficulty", "times": 2}]`
- Pattern: List of dicts with `action` key and action-specific parameters

## Entry Points

**Main Application:**
- Location: `gratta_e_vinci_gui.py` (bottom of file, `if __name__ == "__main__"` block)
- Triggers: `run_gui.bat` or direct `python gratta_e_vinci_gui.py`
- Responsibilities: Creates Tk root, instantiates `GrattaEVinciGUI`, runs main loop

**Mouse Monitoring Utility:**
- Location: `mouseMonitoring.py`
- Triggers: Direct execution `python mouseMonitoring.py`
- Responsibilities: Prints mouse coordinates to stdout in real-time (standalone utility)

**Setup Script:**
- Location: `setup.bat`
- Triggers: First-time setup
- Responsibilities: Creates `.venv`, installs dependencies from `requirements.txt`

## Error Handling

**Strategy:** Mostly try/except at boundary points; no centralized error handling

**Patterns:**
- `GameEngine.validate_settings()` raises `ValueError` on invalid config, caught by GUI to show messagebox
- `ColorDetector.read_color_at_point()` raises `ValueError` for out-of-bounds coordinates; caught in `TkAutomationAdapter.read_color()` returning black pixel
- Color detection retry loop: unknown colors trigger infinite retry with configurable sleep, no timeout
- Test mode wraps entire loop in try/except/finally to ensure `_finish_test_mode()` runs
- `pyautogui.FAILSAFE` (move to top-left corner) as emergency stop mechanism
- `pynput` keyboard listener catches ESC key to trigger graceful shutdown

## Cross-Cutting Concerns

**Logging:** Custom `log_message()` method on `GrattaEVinciGUI` that appends timestamped text to a `ScrolledText` widget. No file logging. All game engine logging goes through `self.app.log_message()`.

**Validation:** `SettingsManager.validate()` checks mode, difficulty, picks, color_tolerance, custom_mode schema. `GameEngine.validate_settings()` checks starting_cash and max_picks. No runtime validation of coordinate values.

**Threading:** Three concurrent threads during gameplay: (1) main Tkinter UI thread, (2) daemon game loop thread with its own asyncio event loop, (3) pynput keyboard listener thread. Mouse monitoring runs as a separate daemon thread at all times.

**Localization:** Mixed English/Italian strings throughout. GUI labels and log messages use both languages inconsistently.

---

*Architecture analysis: 2026-03-10*
