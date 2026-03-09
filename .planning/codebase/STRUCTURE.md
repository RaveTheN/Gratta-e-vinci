# Codebase Structure

**Analysis Date:** 2026-03-09

## Directory Layout

```
C:\Progetti\Gratta e vinci/
├── gratta_e_vinci_gui.py          # Main GUI application (3201 lines)
├── playM.py                        # Standalone automation engine (542 lines)
├── mouseMonitoring.py              # Utility to display mouse coords (9 lines)
├── gratta_settings.json            # Persistent game settings (JSON)
├── requirements.txt                # Python dependencies
├── test_playM_safe.py              # Safe test simulation (286 lines)
├── test_playM_safe_fixed.py        # Alternative test version (264 lines)
├── test_setup.py                   # Setup validation tests (141 lines)
├── test_coordinates.py             # Coordinate mapping tests (161 lines)
├── README.md                        # Project documentation
├── TESTING_GUIDE.md                # Testing patterns and procedures
├── ROUNDING_FIX.md                 # Notes on decimal rounding
├── run_gui.bat                     # Windows batch file to launch GUI
├── setup.bat                       # Windows setup script
├── autoplay.js                     # Legacy JavaScript automation
├── playM.js                        # Legacy JavaScript engine
├── package.json                    # Node.js dependencies (legacy)
├── package-lock.json               # Node.js lockfile
├── eng.traineddata                 # Tesseract OCR data (not used)
├── .planning/                      # GSD planning documents
│   └── codebase/                   # Generated analysis documents
│       ├── ARCHITECTURE.md
│       └── STRUCTURE.md
├── __pycache__/                    # Python bytecode cache
├── .venv/                          # Virtual environment (generated)
└── .git/                           # Git repository metadata
```

## Directory Purposes

**Root Directory:**
- Purpose: Contains all application code, config, and documentation
- Contains: Python source files, settings, tests, batch scripts
- Key files: `gratta_e_vinci_gui.py` (entry point), `gratta_settings.json` (config)

**.planning/codebase/:**
- Purpose: GSD (Get Shit Done) analysis documents
- Contains: Auto-generated architectural analysis (ARCHITECTURE.md, STRUCTURE.md, etc.)
- Generated: Yes
- Committed: Yes (planning documents are tracked)

**.venv/:**
- Purpose: Python virtual environment
- Generated: Yes (created by `setup.bat`)
- Committed: No (excluded in .gitignore)

**.git/:**
- Purpose: Git version control metadata
- Generated: Yes
- Committed: N/A (internal git directory)

## Key File Locations

**Entry Points:**

- `gratta_e_vinci_gui.py` (line 1): Main GUI application, instantiated at module level; execute via `python gratta_e_vinci_gui.py` or `run_gui.bat`
- `playM.py` (line 1-542): Standalone automation without GUI; execute via `python playM.py` (uses hardcoded coordinates)
- `mouseMonitoring.py` (line 1-9): Utility script to print real-time mouse coordinates; execute to find game element positions

**Configuration:**

- `gratta_settings.json` (3737 bytes): Persistent game configuration including starting cash, target win, max loss, max rounds, tile coordinates, betting modes, sleep timings, custom mode steps, difficulty levels
- `requirements.txt` (130 bytes): Python package dependencies

**Core Logic:**

- `gratta_e_vinci_gui.py` (class `GrattaEVinciGUI`, lines 353-3201): Main application class with game engine, UI creation, state management
- `gratta_e_vinci_gui.py` (async `main_game_loop()`, lines 2500-2561): Game loop that manages rounds, checks stop conditions, handles wins/losses
- `gratta_e_vinci_gui.py` (async `play_real_game_round()`, lines 2562-2750+): Single round execution with tile clicking and color detection
- `gratta_e_vinci_gui.py` (class `CoordinateRecorder`, lines 35-351): Interactive coordinate capture for game button positions

**Testing:**

- `test_playM_safe.py` (286 lines): Safe simulation testing (no real mouse clicks); tests betting logic, round simulation, game state
- `test_playM_safe_fixed.py` (264 lines): Alternative test implementation
- `test_setup.py` (141 lines): Validates installation and dependencies
- `test_coordinates.py` (161 lines): Tests coordinate mapping and tile position validation
- `TESTING_GUIDE.md`: Documentation on how to run tests

**Documentation:**

- `README.md` (27 KB): Full project documentation including requirements, installation, architecture overview, usage guide
- `ROUNDING_FIX.md`: Technical notes on decimal rounding to prevent floating-point errors
- `TESTING_GUIDE.md`: Testing procedures and test file descriptions

**Legacy Code (Not Maintained):**

- `autoplay.js`: JavaScript version using nut-js and tesseract
- `playM.js`: JavaScript game engine
- `package.json` (Node.js): Dependencies for legacy JavaScript

**Utilities:**

- `run_gui.bat`: Batch script to launch GUI on Windows (activates venv, runs gratta_e_vinci_gui.py)
- `setup.bat`: Windows setup script (creates venv, installs dependencies, runs tests)

## Naming Conventions

**Files:**

- `gratta_e_vinci_*.py`: Application files (snake_case, prefixed with project name)
- `test_*.py`: Test files (snake_case with `test_` prefix)
- `*_gui.py`: GUI module (snake_case with `_gui` suffix)
- `*.json`: Configuration files (lowercase, no spaces)
- `*.md`: Documentation (markdown, UPPERCASE for primary docs)

**Directories:**

- `.planning/`: GSD planning structure (dot prefix for tool metadata)
- `.venv/`: Virtual environment (dot prefix, lowercase)
- `__pycache__/`: Python cache (double underscore prefix)

**Classes:**

- `GrattaEVinciGUI`: PascalCase (standard Python convention)
- `CoordinateRecorder`: PascalCase
- `Point`: PascalCase

**Functions/Methods:**

- `start_game()`: snake_case
- `play_real_game_round()`: snake_case, async-prefixed with `async def` when asynchronous
- `_on_click()`: snake_case with leading underscore for private/internal callbacks
- `create_settings_tab()`: snake_case for UI creation methods

**Variables:**

- `self.current_cash`: snake_case
- `self.mode_var`: snake_case with `_var` suffix for Tkinter variables (IntVar, DoubleVar, StringVar, BooleanVar)
- `self.starting_cash_var`: snake_case for Tkinter-bound variables
- `WIN_MULTIPLIERS`: UPPERCASE for module-level constants
- `target_blue`: snake_case for instance attributes

## Where to Add New Code

**New Feature (e.g., New Betting Mode):**

- Primary code: `gratta_e_vinci_gui.py` (add method in `GrattaEVinciGUI` class)
- Update settings UI: Add entries to `create_settings_tab()` or `create_betting_modes_tab()`
- Persist to JSON: Update `gratta_settings.json` schema
- Tests: Add to `test_playM_safe_fixed.py` to simulate new mode behavior

**New Tab in GUI:**

- Implementation: `gratta_e_vinci_gui.py` (lines 439-477: create `create_TABNAME_tab()` method, register in `create_widgets()`)
- Pattern: Follow existing tabs (Settings, Coordinates, Betting Modes, etc.)
- Place new methods after line 820 (after existing tab creation methods)

**New Game Automation Method (e.g., Click Behavior):**

- Location: `gratta_e_vinci_gui.py` within `GrattaEVinciGUI` class
- Pattern: Follow naming of `click_tile()`, `play_or_collect()`, `set_bet_value()`
- Async: Use `async def` if it involves sleep or mouse delay
- Logging: Use `self.log_message()` for user feedback

**Shared Utilities:**

- Mouse/Color utilities: Add to `GrattaEVinciGUI` class methods (not standalone module currently)
- Common helpers: Could be extracted to separate module (e.g., `utils.py`) if codebase grows

**Tests:**

- Simulation tests: Add to `test_playM_safe_fixed.py` (follows existing test pattern)
- Integration tests: Would go in new file `test_integration.py` following same pattern
- Place test functions in test files, run via `python test_*.py`

## Special Directories

**`.planning/codebase/`:**
- Purpose: GSD analysis documents (ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md)
- Generated: Yes (auto-created by `/gsd:map-codebase` command)
- Committed: Yes (documents tracked in git for team reference)

**`.venv/`:**
- Purpose: Python virtual environment with installed packages
- Generated: Yes (created by `setup.bat`)
- Committed: No (ignored via .gitignore)

**`__pycache__/`:**
- Purpose: Compiled Python bytecode
- Generated: Yes (auto-created by Python)
- Committed: No (ignored via .gitignore)

## Dependency Location Reference

**Key Dependencies in `requirements.txt`:**

- `pyautogui==0.9.54`: Mouse control, screenshot, automated clicks
- `pynput==1.8.1`: Keyboard listener for ESC key detection
- `Pillow==10.4.0`: Image processing and pixel color reading

**Tkinter:**
- Built into Python standard library (no pip installation needed on Windows)

**Configuration in `gratta_settings.json`:**

- Tile coordinates: `tiles` dict (keys "1"-"25", values [x, y])
- Button positions: `play_x/y`, `raise_x/y`, `lower_x/y`, `raise_diff_x/y`, `lower_diff_x/y`
- Betting modes: `betting_modes` dict with standard modes; `custom_mode` array for custom mode steps
- Sleep timings: `sleep_*` keys for delays between actions (all in seconds, float)

---

*Structure analysis: 2026-03-09*
