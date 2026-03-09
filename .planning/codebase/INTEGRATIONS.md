# External Integrations

**Analysis Date:** 2026-03-09

## APIs & External Services

**Not Applicable**

This project does not integrate with external APIs or remote services. All operations are local and self-contained.

## Data Storage

**Local Filesystem Only:**
- Settings file: `gratta_settings.json` (JSON format)
  - Contains: Game configuration, coordinates, betting modes, timing parameters
  - Auto-loaded on startup from `GrattaEVinciGUI._load_settings()` in `gratta_e_vinci_gui.py`
  - Manually saved via "Save Settings" button
  - Location: Project root directory

**No Database:**
- No SQL database integration
- No ORM layer
- No cloud database connections

**File Operations:**
- Settings persistence: JSON read/write via Python's `json` module
- Screenshots: Temporary in-memory via `pyautogui.screenshot()` using PIL
- No file storage integrations

## Authentication & Identity

**Not Applicable**

No authentication system. Application is a standalone desktop automation tool with no user accounts or identity management.

## Monitoring & Observability

**Logging:**
- Console logging via Python's `print()` statements
- GUI logging: Output to scrolled text widget in Game Control tab
- Log levels: Not formally implemented
- No external log aggregation

**Error Handling:**
- Try/except blocks for critical operations (mouse listeners, file I/O)
- User-facing error dialogs via `tkinter.messagebox`
- No error tracking service

**Debugging:**
- `mouseMonitoring.py` utility script for real-time mouse coordinate printing
- Test scripts: `test_coordinates.py`, `test_playM_safe.py`, `test_setup.py`

## CI/CD & Deployment

**Hosting:**
- Desktop application only - no hosting required
- Runs locally on Windows machine

**CI Pipeline:**
- Not applicable - no automated CI/CD
- Manual setup via `setup.bat` batch script

**Deployment:**
- Manual: Copy project files to target Windows machine
- Virtual environment setup: Run `setup.bat` once
- Execution: Run `run_gui.bat` to start

## Environment Configuration

**Required Environment:**
- Windows OS (no environment variables required for operation)
- Python 3.11 in system PATH for initial setup
- `.venv` virtual environment with dependencies

**No Environment Variables:**
- No `.env` file used
- All configuration via `gratta_settings.json`

## Webhooks & Callbacks

**Not Applicable**

No incoming or outgoing webhooks. Application is purely local with no network communication.

## Browser Integration

**Game Target:**
- Game runs in web browser (specific website not specified in code)
- Application controls mouse/keyboard to interact with browser-based "Gratta e Vinci" game
- Game loads at configurable screen coordinates

**Interaction Method:**
- PyAutoGUI mouse control: Click coordinates for tiles, buttons
- Pixel color detection: Read RGB values to determine game state
- No JavaScript injection or DOM manipulation
- No browser automation framework (Selenium, Playwright, etc.)

## Dependencies with External Calls

**Pyautogui:**
- Relies on OS mouse/keyboard APIs
- `pyautogui.FAILSAFE = True` - Move mouse to top-left corner to abort automation

**Pynput:**
- Keyboard listener with `win32_event_filter` for Windows-specific event filtering
- Mouse listener with Windows button constant mapping

## Offline Operation

**Fully Offline:**
- No internet connection required
- No cloud sync
- No update mechanism
- No telemetry or analytics

---

*Integration audit: 2026-03-09*
