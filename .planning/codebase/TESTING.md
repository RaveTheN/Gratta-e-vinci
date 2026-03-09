# Testing Patterns

**Analysis Date:** 2026-03-09

## Test Framework

**Runner:**
- No test framework configured (no pytest, unittest discovery, etc.)
- Manual test scripts using `if __name__ == "__main__"` entry points

**Assertion Library:**
- No formal assertion library
- Manual validation using `if` statements and print feedback
- User confirmation prompts in interactive tests

**Run Commands:**
```bash
python test_playM_safe.py          # Safe simulation without real mouse clicks
python test_coordinates.py         # Interactive position tester
python test_setup.py               # Verify dependencies and basic functionality
python mouseMonitoring.py          # Live mouse position tracking
```

## Test File Organization

**Location:**
- Co-located with main scripts in project root
- Test files in same directory as code they test: `/c/Progetti/Gratta e vinci/`

**Naming:**
- Prefix pattern: `test_*.py`
- Examples: `test_playM_safe.py`, `test_playM_safe_fixed.py`, `test_coordinates.py`, `test_setup.py`

**Structure:**
```
/c/Progetti/Gratta e vinci/
├── gratta_e_vinci_gui.py          # Main app (no tests in file)
├── playM.py                        # Game engine (no tests in file)
├── test_playM_safe.py              # Safe simulation tests
├── test_playM_safe_fixed.py        # Fixed simulation tests
├── test_coordinates.py             # Interactive coordinate validation
├── test_setup.py                   # Dependency verification
└── mouseMonitoring.py              # Mouse position utility
```

## Test Structure

**Suite Organization:**

Test files use procedural scripts rather than test suites. Each test file has single entry point:

```python
if __name__ == "__main__":
    # Test execution
    asyncio.run(test_main_game_logic())
```

**Patterns:**
- Setup: Initialize global variables at module level (lines 46-63 in `test_playM_safe.py`)
- Execution: Async function calls or interactive prompts
- Teardown: Print final results, cleanup resources
- No setUp/tearDown methods; state managed globally

**Example from `test_playM_safe.py` (lines 135-280):**
```python
async def test_main_game_logic():
    """Test the main game logic without actual automation"""
    global current_cash, highest_cash, bet, highest_bet, picks, tries, rounds, loss, escape_pressed

    # Start keyboard listener for escape key detection
    keyboard_listener = start_keyboard_listener()

    print("🎮 === SAFE TEST MODE - NO ACTUAL MOUSE ACTIONS ===")
    print(f"🚀 Starting with cash: {format_money(current_cash)}")

    # Main game loop
    while True:
        # Check for escape key press
        if escape_pressed:
            print("🛑 Test stopped by escape key")
            break

        # [Main test logic: pick tiles, check colors, update cash]

    # Cleanup keyboard listener
    keyboard_listener.stop()

    print("\n🏆 === TEST COMPLETED ===")
    # [Print final statistics]
```

## Mocking

**Framework:** Manual mock implementations via simulation functions

**Patterns:**

Simulated clicks without actual automation:
```python
# From test_playM_safe.py (lines 73-75)
async def simulate_click(point, action_name):
    await asyncio.sleep(0.1)  # Simulate delay
    print(f"[SIMULATED] {action_name} at {point}")
```

Simulated color detection with configurable outcomes:
```python
# From test_playM_safe.py (lines 77-88)
async def simulate_color_check():
    """Simulate color detection - 19 blue tiles, 6 red tiles out of 25"""
    await asyncio.sleep(0.1)
    rand = random.random()
    if rand < 0.76:  # 76% chance blue (19/25)
        return "blue"
    elif rand < 0.95:  # 19% chance red (6/25 ≈ 24%)
        return "red"
    else:
        return "unknown"  # 5% chance unknown (test retry mechanism)
```

**What to Mock:**
- Mouse clicks: use `simulate_click()` instead of `pyautogui.click()`
- Color detection: use `simulate_color_check()` instead of reading actual pixels
- Time delays: use `await asyncio.sleep()` for realistic timing simulation
- Keyboard input: use pynput Listener for actual ESC key detection (not mocked)

**What NOT to Mock:**
- Game state variables (cash, bets, picks): Use real variables to test logic
- Betting sequence logic: Test against actual betting mode arrays
- Keyboard listener: Real pynput listener to test ESC key functionality
- Event handlers: Real handler implementations (just call them in tests)

## Fixtures and Factories

**Test Data:**

Initial state fixture in `test_playM_safe.py` (lines 46-70):
```python
# Simulate game variables
starting_cash = 50
current_cash = 50
highest_cash = 50
bet = 0.1
highest_bet = 0.1
picks = 0
tries = 0
rounds = 0
randoms = []
loss = 0
max_loss = 10
max_rounds = 10
max_picks = 3
target_win = 100

modes = {
    "normal": [0.1, 0.2, 0.3, 0.5, 0.8, 1.4, 2.5, 4.5, 8.0, 14.0, 20.0],
    "safe": [0.1, 0.1, 0.2, 0.3, 0.5, 1.0, 1.8, 3.0, 5.0, 9.0, 15.0, 20.0]
}
selected_mode = modes["safe"]
multiplier = 2.4
```

Helper functions for test data generation:
- `test_generate_random_tile()`: Generate unique random tile numbers without replacement
- `test_empty_randoms()`: Reset tile selection state
- `test_log_state()`: Print current game state snapshot

**Location:**
- Fixtures defined at module level in test files
- Global variables initialized before main test execution
- No separate fixtures directory

## Coverage

**Requirements:** No coverage enforcement detected

**View Coverage:**
- Not configured
- Manual testing via print statements and visual validation
- Test completion indicated by final statistics output

**Coverage Gaps:**
- No automated coverage measurement
- Ad-hoc testing of game logic
- Missing: Unit tests for individual functions
- Missing: Integration tests for full game flow with real coordinates

## Test Types

**Unit Tests:**
- Minimal (ad-hoc functions in `test_playM_safe.py`)
- Scope: Individual game operations (increase/decrease cash, betting logic)
- Approach: Simulate operation, print result, verify via console output
- Examples: `test_increase_cash()`, `test_get_bet_from_mode_array()`, `test_log_state()`

**Integration Tests:**
- Main focus: `test_main_game_logic()` in `test_playM_safe.py`
- Scope: Full game loop with simulated tiles, colors, and betting
- Approach: Run complete game simulation with mocked mouse/color operations
- Tests: Round flow, cash management, win/loss conditions, ESC key handling

**E2E Tests:**
- Not used
- Real game automation only runs in production mode via GUI

## Common Patterns

**Async Testing:**

Test uses `asyncio.run()` to execute async game loop in synchronous test environment:
```python
# From test_playM_safe.py (lines 275-287)
if __name__ == "__main__":
    print("🧪 Running safe test of game logic...")
    print("   Press ESCAPE key or Ctrl+C to stop the test.")
    try:
        asyncio.run(test_main_game_logic())
        print("✅ Test completed successfully!")
    except KeyboardInterrupt:
        print("\n⚠️ Test stopped by user (Ctrl+C)")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
```

Async helper functions for simulating delays:
```python
# From test_playM_safe.py (lines 73-75)
async def simulate_click(point, action_name):
    await asyncio.sleep(0.1)  # Simulate delay
    print(f"[SIMULATED] {action_name} at {point}")

async def simulate_color_check():
    await asyncio.sleep(0.1)
    # Return simulated color
```

**Error Testing:**

Retry mechanism for uncertain color detection:
```python
# From test_playM_safe.py (lines 190-256)
color_detected = False
retry_count = 0
max_retries = 3

while not color_detected and retry_count < max_retries:
    color_result = await simulate_color_check()

    if color_result == "blue":
        # Handle blue tile
        color_detected = True
    elif color_result == "red":
        # Handle red tile
        color_detected = True
    else:
        # Unknown color - retry
        retry_count += 1
        print(f"❓ Unknown color for tile {tile_num} (attempt {retry_count}/{max_retries})")

        if retry_count < max_retries:
            print("   Waiting 1 second and retrying color detection...")
            await asyncio.sleep(1)
        else:
            print("   Max retries reached, skipping this tile...")
            color_detected = True
```

Stop condition testing via keyboard listener:
```python
# From test_playM_safe.py (lines 39-44)
def on_key_press(key):
    global escape_pressed
    if key == keyboard.Key.esc:
        print("\n🛑 ESCAPE key pressed - stopping test...")
        escape_pressed = True
        return False  # Stop the listener
```

**Coordinate Testing:**

Interactive tool in `test_coordinates.py` (lines 44-109) for validating click positions:
```python
def interactive_position_tester():
    """Interactive tool to test positions"""
    print("🎯 Interactive Position Tester")
    print("Commands:")
    print("  'pos' - Get current mouse position")
    print("  'click X Y' - Test click at coordinates")
    print("  'color X Y' - Get color at coordinates")
    print("  'screenshot X Y' - Take screenshot with crosshair")
    print("  'live' - Live mouse position tracking")

    while True:
        try:
            command = input("\n> ").strip().lower()

            if command == 'quit':
                break
            elif command == 'pos':
                x, y = get_mouse_position()
                print(f"Current mouse position: ({x}, {y})")
            # [More commands...]
```

**Dependency Testing:**

Module import verification in `test_setup.py`:
```python
# From test_setup.py (lines 16-44)
def test_imports():
    """Test if all required modules can be imported"""
    required_modules = [
        'asyncio', 'pyautogui', 'pytesseract', 'cv2', 'numpy', 'PIL', 'time', 'random', 'math'
    ]

    print("=== Testing Module Imports ===")
    failed_imports = []

    for module in required_modules:
        try:
            importlib.import_module(module)
            print(f"✅ {module} - OK")
        except ImportError as e:
            print(f"❌ {module} - FAILED: {e}")
            failed_imports.append(module)

    if failed_imports:
        print(f"\n⚠️  Missing modules: {failed_imports}")
        return False
    else:
        print("\n✅ All modules imported successfully!")
        return True
```

## Test Output & Feedback

**Console Output:**
- Emoji-prefixed messages for visual distinction (✅, ❌, 🎯, 💰, 📈)
- Real-time progress updates during game simulation
- Final summary with statistics (final cash, highest bet, rounds completed, losses)
- Color detection retries shown with attempt count

**Example output from `test_playM_safe.py`:**
```
🎮 === SAFE TEST MODE - NO ACTUAL MOUSE ACTIONS ===
🚀 Starting with cash: 50.00

=== Round 1 ===
[SIMULATED] PLAY - START ROUND at Point(1581, 849)
🎰 Started round with bet: 0.10 - Cash deducted immediately
🎲 Generated tile: 12
[SIMULATED] TILE 12 at Point(1512, 800)
🔵 Tile 12 is BLUE!
🎯 Got 1 blue(s), need 2 more...

...

🏆 === TEST COMPLETED ===
Final Results:
💰 Final Cash: 45.80
📈 Highest Cash: 50.00
🔝 Highest Bet: 0.20
🏁 Rounds Completed: 10
📉 Total Loss: 4.20
🎯 Final Picks: 0
🔄 Final Tries: 3
```

---

*Testing analysis: 2026-03-09*
