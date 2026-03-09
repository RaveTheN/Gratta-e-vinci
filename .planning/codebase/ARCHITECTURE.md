# Architecture

**Analysis Date:** 2026-03-09

## Pattern Overview

**Overall:** Event-driven GUI application with asynchronous game automation engine

**Key Characteristics:**
- Desktop GUI built with Tkinter managing UI state and user interaction
- Separate async game loop running in daemon thread for automation
- Mouse control via pyautogui with color detection for game state evaluation
- Settings persistence via JSON configuration file
- Threading model: GUI thread (main) + daemon async game thread + daemon mouse monitoring thread

## Layers

**Presentation Layer:**
- Purpose: User interface and user input management
- Location: `gratta_e_vinci_gui.py` (class `GrattaEVinciGUI`, lines 353-3201)
- Contains: 7 Tkinter tabs (Settings, Coordinates, Betting Modes, Initialization, Game Control, Statistics, Pause), dialogs, and real-time displays
- Depends on: Game engine methods, settings persistence, logging system
- Used by: Direct user interaction (clicks, combobox selection, text entry)

**Game Engine Layer:**
- Purpose: Core automation logic and game state management
- Location: `gratta_e_vinci_gui.py` (methods: `main_game_loop`, `play_real_game_round`, game control methods)
- Contains: Game loop, round execution, betting strategy application, difficulty management, state tracking
- Depends on: Mouse control layer, color detection, configuration
- Used by: Presentation layer's start/stop buttons and test mode

**Mouse Control & Input Layer:**
- Purpose: Automated mouse clicks, keyboard monitoring, screenshot capture
- Location: `gratta_e_vinci_gui.py` (methods: `click_tile`, `play_or_collect`, `set_bet_value`, `set_difficulty`, `read_color_at_point`)
- Contains: pyautogui wrappers, pynput keyboard listener, pixel color reading
- Depends on: Coordinate mappings, tile/button positions
- Used by: Game engine for all interactions with the game

**Configuration & Persistence Layer:**
- Purpose: Load/save game settings and coordinates
- Location: `gratta_settings.json` (persistent) and `gratta_e_vinci_gui.py` (in-memory state)
- Contains: Game parameters, tile coordinates, betting modes, sleep timings, custom betting strategies
- Depends on: File system
- Used by: Presentation and game engine for initialization and settings management

**Coordinate Recording Layer:**
- Purpose: Interactive UI for mapping game button and tile positions
- Location: `gratta_e_vinci_gui.py` (class `CoordinateRecorder`, lines 35-351)
- Contains: Mouse listener for clicks, overlay window, step-based recording UI
- Depends on: pynput mouse events, Tkinter window management
- Used by: User during initial setup via "Coordinates" tab

## Data Flow

**Game Initialization:**

1. User clicks "Start Game" button → `start_game()` validates settings
2. `initialize_game_variables()` sets cash, bet, rounds to initial state
3. `update_tiles_from_gui()` loads tile coordinates from GUI entries (or JSON)
4. `execute_init_steps()` runs pre-game configuration (set min bet, adjust difficulty)
5. `main_game_loop()` async function starts

**Single Round Flow:**

1. `play_real_game_round()` called within `main_game_loop()`
2. `_get_round_config_for_strategy()` determines: bet amount, max picks, difficulty (based on mode)
3. If custom mode: adjust difficulty via `set_difficulty()`
4. `play_or_collect()` clicks Play button → cash deducted immediately
5. Loop: `generate_random_tile()` → `click_tile()` → `read_color_at_point()` → color classification
6. Per tile: if BLUE, increment `picks`; if RED, end round (LOSS); if unknown, retry with `sleep_color_retry`
7. Win condition: `picks >= max_picks` → `play_or_collect()` (Collect) → add winnings to cash
8. Loss condition: RED tile detected → calculate loss, apply Martingale adjustment
9. Next round or stop based on exit conditions (max rounds, target win, max loss, insufficient cash)

**State Management:**

- Current cash, highest cash, bet amount, picks, rounds, loss tracking maintained in instance variables
- After each win: bet resets to minimum (via `set_bet_value()`)
- After each loss: bet advances one step in betting mode sequence
- Grinding mode: activates when loss exceeds threshold; uses fixed high bet until balance recovers

## Key Abstractions

**Point Class:**
- Purpose: Represent 2D coordinates for mouse clicks
- Examples: `gratta_e_vinci_gui.py` line 26, `playM.py` line 13
- Pattern: Simple data holder with `x`, `y` attributes and `__repr__` for logging

**Game Mode System:**
- Purpose: Encapsulate different betting strategies
- Examples in `gratta_settings.json` (lines 192-238): `normal`, `medium`, `high`, `safe`, `custom`
- Pattern: Each mode is array of bet amounts (standard) or array of dicts with `b` (bet), `p` (picks), `d` (difficulty) (custom)

**WIN_MULTIPLIERS Lookup Table:**
- Purpose: Resolve payout based on difficulty and picks
- Location: `gratta_e_vinci_gui.py` (lines 16-20)
- Pattern: Nested dict `{difficulty: {picks: multiplier}}` keyed by game difficulty level and number of blue tiles picked
- Examples: low difficulty + 2 picks = 1.1× bet; high difficulty + 4 picks = 8.7× bet

**Round Configuration Object:**
- Purpose: Encapsulate all strategy parameters for a single round
- Location: Returned by `_get_round_config_for_strategy()` (around line 2430)
- Contents: selected_mode_name, step_idx, max_step_idx, round_difficulty, max_picks, multiplier, grinding_enabled
- Used by: `play_real_game_round()` to determine how to execute a round

**Color Detection Abstraction:**
- Purpose: Map RGB pixel values to game state (blue tile, red tile, unknown)
- Methods: `read_color_at_point()`, `is_color_in_range_blue()`, `is_color_in_range_red()`
- Tolerance: ±50 per RGB channel from target colors
- Target colors defined in `__init__`: `target_blue` (1, 108, 238), `target_red` (200, 13, 1)

## Entry Points

**Main GUI Application:**
- Location: `gratta_e_vinci_gui.py` (entire file, instantiated at module end)
- Triggers: User double-clicks or runs `python gratta_e_vinci_gui.py`
- Responsibilities: Create Tkinter window, load settings, start mouse monitoring, display 7 tabs

**Game Start Button:**
- Location: `start_game()` method, called when user clicks "Start Game" button
- Triggers: User interaction on Game Control tab
- Responsibilities: Validate settings, confirm with user, spawn async game thread, start keyboard listener

**Test Mode Button:**
- Location: `start_test_mode()` method
- Triggers: User interaction on Game Control tab
- Responsibilities: Simulate game without mouse control, useful for debugging betting logic

**Coordinate Recording:**
- Location: `CoordinateRecorder.start()` method, triggered by "Start Recording" in Coordinates tab
- Triggers: User clicks button to begin coordinate mapping
- Responsibilities: Show overlay, listen for mouse clicks, capture positions of game elements

**Standalone Automation (Legacy):**
- Location: `playM.py` (module-level execution)
- Triggers: `python playM.py` (no GUI, uses hardcoded coordinates)
- Responsibilities: Automation engine without UI (used for testing or headless operation)

## Error Handling

**Strategy:** Try-catch blocks with user feedback via messagebox and log messages

**Patterns:**

- **Settings Validation:** `validate_settings()` checks required fields, displays error dialog if missing (e.g., missing tile coordinates)
- **Color Detection Retry:** If color is unknown (not blue or red), retry up to 3 times with `sleep_color_retry` delay before treating as failure
- **Keyboard Listener Safety:** Wrapped in try-catch; if setup fails, shows error dialog and cancels recording
- **Async Error Recovery:** Game loop checks `self.escape_pressed` at critical points; graceful exit on keyboard interrupt
- **Mouse Failsafe:** `pyautogui.FAILSAFE = True` triggers abort if mouse moved to top-left corner

## Cross-Cutting Concerns

**Logging:**
- Central method `log_message(message)` appends to scrolled text widget in Statistics tab
- Includes emoji prefixes for readability: 🎰 start, 💸 loss, 💰 win, 🛑 stop, ⚠️ warning

**Validation:**
- Field-level: Tkinter variables use IntVar/DoubleVar/StringVar with setter callbacks
- Settings-level: `validate_settings()` checks tiles dict is not empty, coordinates are numeric
- Betting-level: Validates bet doesn't exceed player cash, bet values in allowed list

**Authentication:**
- None (local desktop application)

**Async Coordination:**
- Main game loop runs in daemon thread spawned by `start_game()`
- Mouse monitoring runs in separate daemon thread with `start_mouse_monitoring()`
- Keyboard listener runs in pynput's internal thread via `keyboard.Listener()`
- All cross-thread updates to GUI use `self.root.after()` to marshal to main thread

**Difficulty Management:**
- Current difficulty tracked in `self.current_difficulty`
- Standard modes: difficulty set once at game start via `set_difficulty()`
- Custom modes: difficulty adjusted per round based on custom_mode steps
- Grinding mode: difficulty adjusted while grinding is active

---

*Architecture analysis: 2026-03-09*
