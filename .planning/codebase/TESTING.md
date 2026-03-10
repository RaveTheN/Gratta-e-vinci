# Testing Patterns

**Analysis Date:** 2026-03-10

## Test Framework

**Runner:**
- No test framework installed or configured
- No `pytest`, `unittest`, `nose`, or any test runner in `requirements.txt`
- No test configuration files (`pytest.ini`, `conftest.py`, `tox.ini`, `pyproject.toml`)
- `.gitignore` excludes `*.test.js`, `*.test.ts`, `*.spec.js`, `*.spec.ts` but these are irrelevant (project is Python)

**Assertion Library:**
- None configured

**Run Commands:**
```bash
# No test commands available
# Recommend adding pytest:
pip install pytest
pytest
```

## Test File Organization

**Location:**
- No test files exist in the project
- No `tests/` directory
- No co-located test files alongside source

**Recommended Structure:**
```
tests/
  test_game_config.py      # Constants and Point class
  test_color_detector.py    # Color detection logic
  test_coordinate_manager.py # Grid calculation
  test_settings_manager.py  # Settings load/save/validate
  test_game_engine.py       # Game logic (testable via mocked adapter)
```

## Built-in Test Mode (Not Automated Tests)

The project has a **manual test mode** (simulation) built into the game engine, which is not an automated test suite but rather a simulation feature for the user.

**Location:** `game_engine.py` lines 430-634, `gratta_e_vinci_gui.py` lines 1921-2062

**What it does:**
- Simulates a 5x5 board with mines and coins
- Runs the full betting strategy loop without mouse automation
- Uses `_simulate_test_board()` to generate random board outcomes
- Reports final statistics (profit/loss, rounds played, highest bet)

**Entry point:** "TEST MODE" button in Game Control tab, calls `GameEngine.run_test_mode()`

**Key simulation methods:**
```python
# game_engine.py
def _simulate_test_board(self, round_difficulty, max_picks):
    """Simulates a 5x5 board with mines based on difficulty."""
    mine_count = TEST_MODE_MINE_CONFIG[round_difficulty]
    board = ["mine"] * mine_count + ["coin"] * (TEST_MODE_BOARD_SIZE - mine_count)
    random.shuffle(board)
    # ... opens tiles sequentially until hit_mine or max_picks reached

def _apply_test_win(self, round_config, verbose=True):
    """Apply winning round outcome to game state."""

def _apply_test_loss(self, round_config, verbose=True):
    """Apply losing round outcome to game state."""
```

## Testability Assessment

**Easily testable modules (pure logic, no GUI dependency):**

1. **`game_config.py`** - Constants and `Point` class, trivially testable
   - `format_money()` function
   - `Point` class
   - Constant value verification

2. **`settings_manager.py`** - JSON load/save with validation
   - `SettingsManager.validate()` returns error list -- ideal for unit tests
   - `SettingsManager.merge_with_defaults()` pure function
   - `SettingsManager.load_settings()` / `save_settings()` need filesystem (use `tmp_path`)

3. **`color_detector.py`** - Color matching logic
   - `ColorDetector.is_color_in_range_blue()` / `is_color_in_range_red()` are pure functions
   - `ColorDetector.read_color_at_point()` requires screen capture (mock `ImageGrab`)

4. **`coordinate_manager.py`** - Grid calculation
   - `CoordinateManager.populate_tile_vars()` needs Tkinter `IntVar` (can be mocked or created headless)
   - `CoordinateManager.build_tile_points()` returns dict of `Point` objects
   - `CoordinateRecorder` is heavily GUI-coupled

**Harder to test (GUI-coupled):**

5. **`game_engine.py`** - Core game logic
   - `GameEngine` depends on `self.app` (the GUI instance) for all state
   - `TkAutomationAdapter` wraps `pyautogui` calls -- must be mocked
   - Test mode methods (`run_test_mode`, `_simulate_test_board`, `_apply_test_win`, `_apply_test_loss`) contain testable logic but access `self.app.*` extensively

6. **`gratta_e_vinci_gui.py`** - 2963 lines, deeply coupled to Tkinter
   - Contains duplicated legacy methods alongside refactored versions
   - Not unit-testable in current form without significant mocking

## Mocking

**Framework:** Not established. Recommend `unittest.mock` (stdlib) or `pytest-mock`.

**What to Mock:**
- `pyautogui.click()`, `pyautogui.position()`, `pyautogui.size()` - Mouse automation
- `PIL.ImageGrab.grab()` - Screenshot capture
- `pynput.keyboard.Listener`, `pynput.mouse.Listener` - Input listeners
- `tkinter` variables and widgets when testing `GameEngine` methods
- File I/O for `SettingsManager` tests (or use `tmp_path` fixture)

**Recommended mocking pattern for GameEngine:**
```python
# Create a mock app object that mimics GrattaEVinciGUI attributes
class MockApp:
    def __init__(self):
        self.bet = 0.1
        self.current_cash = 2000.0
        self.highest_cash = 2000.0
        self.tries = 0
        self.picks = 0
        self.rounds = 0
        self.loss = 0.0
        self.total_win = 0.0
        self.randoms = []
        self.grinding_active = False
        self.grinding_saved_balance = None
        self.highest_bet = 0.1
        self.custom_mode = [{"b": 0.1, "p": 2, "d": "low"}]
        self.betting_modes = {"normal": [0.1, 0.2, 0.3]}
        # ... mock tk.StringVar, tk.IntVar, etc.

    def log_message(self, msg):
        pass  # or collect for assertions

    def format_money(self, value):
        return f"{round(value, 2):.2f}"
```

**What NOT to Mock:**
- `game_config.py` constants -- use real values
- `SettingsManager` internal logic -- test directly
- `ColorDetector` color-matching math -- test directly
- `random` module -- seed it for deterministic tests: `random.seed(42)`

## Fixtures and Factories

**Test Data:**
- Settings defaults are defined in `settings_manager.py` `_build_defaults()` -- use as test fixture base
- Betting modes defined in `game_config.py` `BETTING_MODES` -- use directly
- Color targets: `TARGET_BLUE = {"r": 1, "g": 108, "b": 238}`, `TARGET_RED = {"r": 200, "g": 13, "b": 1}`

**Recommended fixture location:**
- `tests/conftest.py` for shared pytest fixtures

## Coverage

**Requirements:** None enforced. No coverage tool configured.

**Recommended setup:**
```bash
pip install pytest pytest-cov
pytest --cov=. --cov-report=html
```

## Test Types

**Unit Tests:**
- Priority targets: `settings_manager.py`, `color_detector.py`, `game_config.py`, `coordinate_manager.py`
- These modules have clean interfaces and minimal external dependencies

**Integration Tests:**
- Test `GameEngine` with mocked `TkAutomationAdapter` and mock app object
- Test settings round-trip: save then load and verify values match
- Test coordinate grid: set key coordinates, verify all 25 tiles calculated correctly

**E2E Tests:**
- Not practical for this project (requires real browser game running)
- The built-in TEST MODE serves as a manual E2E simulation

## Recommended Test Priority

1. **`settings_manager.py`** - Highest value: validate() covers many edge cases, load/save are critical for user data
2. **`color_detector.py`** - Color matching is core game logic, easy to test
3. **`game_config.py`** - Quick wins: verify constants, format_money()
4. **`coordinate_manager.py`** - Grid math is deterministic and testable
5. **`game_engine.py`** - Most complex; start with `_simulate_test_board`, `_get_target_bet_for_try`, `_get_round_config_for_strategy`

## Example Test Patterns

**Testing SettingsManager validation:**
```python
def test_validate_rejects_invalid_mode():
    sm = SettingsManager()
    payload = sm.merge_with_defaults({"mode": "invalid"})
    errors = sm.validate(payload)
    assert any("mode" in e for e in errors)

def test_validate_accepts_valid_settings():
    sm = SettingsManager()
    payload = sm.merge_with_defaults(None)  # all defaults
    errors = sm.validate(payload)
    assert errors == []
```

**Testing ColorDetector:**
```python
def test_is_blue_within_tolerance():
    cd = ColorDetector(tolerance=50)
    color = {"r": 10, "g": 100, "b": 230}
    assert cd.is_color_in_range_blue(color) is True

def test_is_red_outside_tolerance():
    cd = ColorDetector(tolerance=10)
    color = {"r": 100, "g": 100, "b": 100}
    assert cd.is_color_in_range_red(color) is False
```

**Testing format_money:**
```python
from game_config import format_money

def test_format_money_two_decimals():
    assert format_money(1.1) == "1.10"
    assert format_money(0.1 + 0.2) == "0.30"
    assert format_money(100) == "100.00"
```

---

*Testing analysis: 2026-03-10*
