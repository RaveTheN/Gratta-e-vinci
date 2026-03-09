# Coding Conventions

**Analysis Date:** 2026-03-09

## Naming Patterns

**Files:**
- Snake case for all Python files: `gratta_e_vinci_gui.py`, `playM.py`, `test_playM_safe.py`
- Test files follow pattern: `test_*.py` (e.g., `test_setup.py`, `test_coordinates.py`)

**Functions:**
- Snake case for all function/method names: `log_message()`, `read_color_at_point()`, `format_money()`
- Private/internal methods prefixed with single underscore: `_on_click()`, `_create_overlay()`, `_build_steps()`
- Async functions use `async def` with same snake_case naming: `async def increase_cash()`, `async def sleep()`

**Variables:**
- Snake case for local and instance variables: `current_cash`, `highest_bet`, `max_loss`, `target_win`
- Constants in UPPER_CASE with underscores: `TEST_MODE_BOARD_SIZE`, `WIN_MULTIPLIERS`, `GRINDING_STEP`
- Global variables follow lowercase pattern: `escape_pressed`, `selected_mode`, `tiles`
- Dictionary keys in lowercase: `{"r": 0, "g": 0, "b": 0, "a": 255}` (RGB color format)

**Types/Classes:**
- Class names in PascalCase: `Point`, `CoordinateRecorder`, `GrattaEVinciGUI`
- Constructor: `__init__()` following Python convention
- String representation: `__repr__()` method implemented

## Code Style

**Formatting:**
- No automated linter/formatter detected (no .pylintrc, .flake8, pyproject.toml)
- Indentation: 4 spaces (Python standard)
- Line length: varies, typically under 100 characters but some lines exceed this
- Docstrings: Triple-quoted strings on single or multiple lines

**Linting:**
- No configured linting tool
- Code follows general PEP 8 style loosely
- Mix of styles observed (some files more consistent than others)

## Import Organization

**Order:**
1. Standard library imports (asyncio, json, os, random, time, threading)
2. Third-party imports (tkinter, pyautogui, pynput, PIL, cv2, pytesseract)
3. Local imports (Point class definitions, custom modules)

**Path Aliases:**
- No aliases used in codebase
- Relative imports from same modules: `from pynput import keyboard, mouse`
- All imports at top of file

**Example from `gratta_e_vinci_gui.py` (lines 5-14):**
```python
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import asyncio
import pyautogui
import random
import time
from pynput import keyboard, mouse
import json
import os
```

## Error Handling

**Patterns:**
- Try-except blocks wrap risky operations (screenshot capture, file I/O, color detection)
- Generic exception catching with `Exception as e` (broad, not type-specific)
- Error messages logged to UI via `self.log_message()` when available
- Graceful degradation: functions return default values on error (e.g., return `{"r": 0, "g": 0, "b": 0, "a": 255}` on color read fail)

**Example from `gratta_e_vinci_gui.py` (lines 2202-2219):**
```python
def read_color_at_point(self, point):
    """Read color at a point on screen"""
    try:
        screenshot = pyautogui.screenshot()
        pixel_color = screenshot.getpixel((point.x, point.y))
        if len(pixel_color) == 3:  # RGB
            r, g, b = pixel_color
            a = 255
        else:  # RGBA
            r, g, b, a = pixel_color
        return {"r": r, "g": g, "b": b, "a": a}
    except Exception as e:
        self.log_message(f"❌ Error reading color: {e}")
        return {"r": 0, "g": 0, "b": 0, "a": 255}
```

## Logging

**Framework:** Console print statements and custom `log_message()` method in GUI

**Patterns:**
- `log_message()` method in `GrattaEVinciGUI` class adds timestamp and routes to UI text widget
- Emoji prefixes for visual distinction: `🎰`, `❌`, `✅`, `🎯`, `💰`, `📈`
- Timestamp format: `[HH:MM:SS] message` added by `log_message()` method (lines 2865-2870)
- Simple `print()` statements in utility scripts and tests
- Debug logging with emoji indicators for game events

**Example from `gratta_e_vinci_gui.py` (lines 2865-2870):**
```python
def log_message(self, message):
    """Add a message to the status log"""
    timestamp = time.strftime("%H:%M:%S")
    full_message = f"[{timestamp}] {message}\n"
    self.root.after(0, lambda: self.status_text.insert(tk.END, full_message))
    self.root.after(0, lambda: self.status_text.see(tk.END))
```

## Comments

**When to Comment:**
- Function docstrings provided for public/complex methods
- Sparse inline comments; mostly self-documenting code
- Comments appear on complex logic (e.g., color tolerance checks, betting strategy)
- TODO/FIXME comments minimal (not observed in scanned files)

**JSDoc/TSDoc:**
- Not applicable (Python codebase)
- Docstrings use triple quotes: `"""Description."""`
- Single-line docstrings for simple functions
- Multi-line docstrings for complex logic

**Example from `playM.py` (lines 131-133):**
```python
def format_money(value):
    """Format a number to always show exactly 2 decimal places"""
    return f"{round(value, 2):.2f}"
```

## Function Design

**Size:** Functions vary widely (5-200+ lines)
- Small utility functions: 5-10 lines (e.g., `format_money()`, `get_random_number()`)
- Complex logic functions: 50-100+ lines (e.g., `run_game_async()`, `run_test_mode()`)
- Event handlers: 20-50 lines

**Parameters:**
- Mostly positional parameters
- Default parameters used: `tolerance=50` in color detection methods
- Instance variables accessed via `self` in class methods
- Some functions accept optional `tries`, `selected_mode_name` parameters for flexibility

**Return Values:**
- Boolean for validation: `validate_settings()`, `is_color_in_range_blue()`
- Dictionary for color data: `{"r": r, "g": g, "b": b, "a": a}`
- None for state-modifying operations (logging, incrementing counters)
- Numbers/strings for utility functions: `format_money()` returns formatted string

**Example from `gratta_e_vinci_gui.py` (lines 2221-2235):**
```python
def is_color_in_range_blue(self, color, target_color, tolerance=50):
    """Check if color is in blue range"""
    return (
        abs(color["r"] - target_color["r"]) <= tolerance and
        abs(color["g"] - target_color["g"]) <= tolerance and
        abs(color["b"] - target_color["b"]) <= tolerance
    )

def is_color_in_range_red(self, color, target_color, tolerance=50):
    """Check if color is in red range"""
    return (
        abs(color["r"] - target_color["r"]) <= tolerance and
        abs(color["g"] - target_color["g"]) <= tolerance and
        abs(color["b"] - target_color["b"]) <= tolerance
    )
```

## Module Design

**Exports:**
- No explicit `__all__` declarations observed
- All public methods/classes accessible
- Private methods use `_` prefix convention to signal internal use

**Barrel Files:**
- Not used; no aggregating import files

**Structure Pattern:**
- Single-responsibility: `playM.py` contains game logic; `gratta_e_vinci_gui.py` contains UI
- Utility scripts are standalone: `mouseMonitoring.py`, `test_setup.py`, `test_coordinates.py`

## Async/Threading Patterns

**Asyncio:**
- Used in main game loop via `asyncio.run()` in separate daemon thread
- Async functions for click simulation and delays: `async def sleep()`, `async def simulate_click()`
- Mixed async/sync: some functions (like `log_state()`, `empty_randoms()`) are synchronous even in async context

**Threading:**
- Main application spawns daemon threads for game loop and mouse monitoring
- Pattern: `threading.Thread(target=method, daemon=True).start()` in `start_game()` (line 2270)
- Event listeners (keyboard, mouse) run in separate threads via pynput

**Example from `gratta_e_vinci_gui.py` (lines 2269-2273):**
```python
# Start game in separate thread
threading.Thread(target=self.run_game_async, daemon=True).start()

# Start keyboard listener
self.start_keyboard_listener()
```

---

*Convention analysis: 2026-03-09*
