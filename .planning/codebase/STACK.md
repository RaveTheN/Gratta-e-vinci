# Technology Stack

**Analysis Date:** 2026-03-09

## Languages

**Primary:**
- Python 3.11 - Main automation and GUI application

**Secondary:**
- JavaScript (Node.js) - Legacy automation engine (not actively maintained)

## Runtime

**Environment:**
- Windows only (uses Windows-specific mouse/keyboard event filtering)

**Package Manager:**
- pip (Python) - Primary dependency manager
- npm (Node.js) - Secondary, for legacy JavaScript version

## Frameworks

**GUI:**
- Tkinter (built-in Python library) - Main GUI framework in `gratta_e_vinci_gui.py`
  - ttk (themed widgets)
  - scrolledtext (for logging/output displays)

**Concurrency:**
- asyncio - Asynchronous game loop management
- threading - Daemon threads for mouse monitoring and background game loop

**Keyboard/Mouse Input:**
- pynput - Cross-platform keyboard and mouse listener for input detection

## Key Dependencies

**Critical:**
- pyautogui 0.9.54 - Mouse automation and screenshot capture
- pynput 1.8.1 - Keyboard and mouse event listeners
- Pillow 10.4.0 - Image processing and pixel color detection
- numpy 1.24.3 - Numerical operations for image analysis

**Legacy/Inactive:**
- pytesseract 0.3.10 - OCR support (commented out, not actively used)
- opencv-python 4.8.1.78 - Image processing (commented out, not actively used)

**JavaScript Legacy Stack:**
- @nut-tree-fork/nut-js ^4.2.2 - Node.js automation library
- tesseract.js ^5.1.1 - Browser-based OCR
- screenshot-desktop ^1.15.0 - Screenshot capture
- jimp ^1.6.0 - Image processing library

## Configuration

**Environment:**
- No `.env` file required - All settings stored in JSON
- Settings file: `gratta_settings.json` - Persisted configuration with game parameters, coordinates, betting modes

**Build:**
- No build process required
- Virtual environment: `.venv/` directory (created via `setup.bat`)

**Startup:**
- `run_gui.bat` - Batch script that activates virtual environment and launches main GUI
- `setup.bat` - Setup script that creates venv and installs dependencies

## Platform Requirements

**Development:**
- Windows OS (tested on Windows 10/11)
- Python 3.11+
- Virtual environment support

**Production:**
- Windows OS with multi-monitor support
- Display resolution support for variable game positions
- Mouse and keyboard hardware
- Browser window with "Gratta e Vinci" game loaded

## Settings Persistence

**JSON Structure** (`gratta_settings.json`):
- Game parameters: `starting_cash`, `target_win`, `max_loss`, `max_rounds`, `max_picks`
- Difficulty levels: `low`, `medium`, `high`
- Betting modes: `normal`, `medium`, `high`, `safe`, `custom`
- Coordinates: 25 tile positions (X, Y) + control button positions
- Timing parameters: Sleep durations between actions (in seconds)
- Custom betting sequences: Configurable bet progressions with difficulty/picks combinations

## Color Detection System

**Pixel-based tile state detection:**
- Blue tile (Win): RGB(1, 108, 238) ± tolerance of 50 per channel
- Red tile (Loss): RGB(200, 13, 1) ± tolerance of 50 per channel
- Detected via `pyautogui.pixel()` after each tile click

---

*Stack analysis: 2026-03-09*
