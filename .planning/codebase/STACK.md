# Technology Stack

**Analysis Date:** 2026-03-10

## Languages

**Primary:**
- Python 3.11.0 - All active application code (`gratta_e_vinci_gui.py`, `game_engine.py`, `game_config.py`, `color_detector.py`, `coordinate_manager.py`, `settings_manager.py`, `mouseMonitoring.py`)

**Secondary:**
- JavaScript (Node.js) - Legacy automation approach, not actively maintained. Dependencies in `package.json` but no `.js` source files on the GUI branch (deleted: `autoplay.js`, `playM.js`)

## Runtime

**Environment:**
- Python 3.11.0 via local virtual environment at `.venv/`
- Windows only (relies on Win32 APIs via pyautogui/pynput, and `.bat` launcher scripts)

**Package Manager:**
- pip (Python) - dependencies in `requirements.txt`
- Lockfile: Not present (no `pip freeze` lockfile; only `requirements.txt` with pinned versions)
- npm (Node.js legacy) - `package-lock.json` present (lockfileVersion 3)

## Frameworks

**Core:**
- Tkinter (stdlib) - GUI framework, builds the entire 5-tab interface with ttk widgets
- asyncio (stdlib) - Async game loop runs in a daemon thread via `asyncio.new_event_loop()`

**Testing:**
- None detected - no test framework configured, no test files present

**Build/Dev:**
- No build tools - pure Python scripts, no compilation step
- `setup.bat` - Creates `.venv`, installs requirements
- `run_gui.bat` - Launches the GUI via `.venv\Scripts\python.exe gratta_e_vinci_gui.py`

## Key Dependencies

**Critical (from `requirements.txt`):**
- `pyautogui==0.9.54` - Mouse/keyboard automation (clicking tiles, buttons). Used in `game_engine.py` and `color_detector.py`
- `pynput==1.8.1` - Keyboard listener (ESC to stop), mouse listener (coordinate recording). Used in `game_engine.py` and `coordinate_manager.py`
- `Pillow==10.4.0` - Screenshot capture and pixel color reading via `ImageGrab.grab()`. Used in `color_detector.py`

**Present but unused in active code:**
- `pytesseract==0.3.10` - OCR library, no imports found in current Python source. Legacy from JS approach
- `opencv-python==4.8.1.78` - Computer vision, no imports found in current Python source
- `numpy==1.24.3` - Numerical computing, no imports found in current Python source

**Note:** `pyautogui` is listed twice in `requirements.txt` (duplicate entry).

**Legacy Node.js dependencies (from `package.json`):**
- `@nut-tree-fork/nut-js ^4.2.2` - Desktop automation (Node equivalent of pyautogui)
- `jimp ^1.6.0` - Image processing
- `screenshot-desktop ^1.15.0` - Screen capture
- `tesseract.js ^5.1.1` - OCR in JavaScript

## Configuration

**Environment:**
- No `.env` files detected - all configuration via JSON settings file
- Settings stored in `gratta_settings.json` (auto-loaded on startup, manually saved via GUI)
- Settings managed by `SettingsManager` class in `settings_manager.py`

**Key settings categories:**
- Game parameters: `starting_cash`, `target_win`, `max_loss`, `max_rounds`, `max_picks`
- Betting mode: `mode` (normal/medium/high/safe/custom), `betting_modes` dict, `custom_mode` list
- UI coordinates: `play_x/y`, `raise_x/y`, `lower_x/y`, `tiles` dict (1-25), difficulty button coords
- Timing: 13 separate `sleep_*` parameters controlling delays between automation actions
- Color detection: `color_tolerance` (default 50)

**Build:**
- No build configuration - interpreted Python
- `setup.bat` - One-time environment setup script
- `run_gui.bat` - Application launcher

## Platform Requirements

**Development:**
- Windows (required - uses Win32 mouse hooks via pynput, `.bat` scripts)
- Python 3.11+ (type hints use `dict[str, Any]` syntax from 3.9+, `__future__.annotations` used)
- Screen with game window visible (pyautogui needs to click actual screen coordinates)

**Production:**
- Same as development - runs locally on Windows desktop
- No server deployment, no containerization
- Game must be open in a browser window at configured screen coordinates

## Standard Library Usage

Key stdlib modules used across the codebase:
- `tkinter` / `ttk` - GUI (`gratta_e_vinci_gui.py`)
- `asyncio` - Async game loop (`game_engine.py`)
- `threading` - Daemon threads for game loop and mouse monitoring (`gratta_e_vinci_gui.py`)
- `json` - Settings serialization (`settings_manager.py`)
- `random` - Tile selection, test mode board simulation (`game_engine.py`)
- `time` - Delays in test mode and mouse monitoring (`game_engine.py`, `mouseMonitoring.py`)
- `os` - File existence checks (`settings_manager.py`)
- `copy.deepcopy` - Settings default merging (`settings_manager.py`)

---

*Stack analysis: 2026-03-10*
