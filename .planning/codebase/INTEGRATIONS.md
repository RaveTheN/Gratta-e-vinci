# External Integrations

**Analysis Date:** 2026-03-10

## APIs & External Services

**None.** This application does not call any external APIs or web services. It is a desktop automation tool that interacts with a browser-based game purely through screen coordinates, mouse clicks, and pixel color reading.

## Data Storage

**Databases:**
- None - no database used

**File Storage:**
- Local filesystem only
  - `gratta_settings.json` - Settings persistence (read/write via `settings_manager.py`)
  - JSON format, loaded on startup, saved manually by user

**Caching:**
- None

## Authentication & Identity

**Auth Provider:**
- Not applicable - standalone desktop tool with no user accounts
- Game authentication is handled by the user manually in their browser before starting the bot

## Monitoring & Observability

**Error Tracking:**
- None - errors logged to GUI scrolled text widget only

**Logs:**
- In-app only via `log_message()` method in `gratta_e_vinci_gui.py`
- Displayed in the Game Control tab's scrolled text area
- No file-based logging, no log rotation
- Messages use emoji prefixes for visual categorization

## CI/CD & Deployment

**Hosting:**
- Local desktop only - no server or cloud deployment

**CI Pipeline:**
- None configured

## Environment Configuration

**Required env vars:**
- None - all configuration via `gratta_settings.json`

**Secrets location:**
- Not applicable - no secrets or API keys

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None

## Hardware/OS Integrations

**Screen Interaction (primary integration):**
- `pyautogui` - Reads screen size, performs mouse clicks at absolute screen coordinates
  - Used in: `game_engine.py` (TkAutomationAdapter), `color_detector.py`, `mouseMonitoring.py`
  - Failsafe: moving mouse to top-left corner triggers `pyautogui.FailSafeException`

**Screenshot Capture:**
- `Pillow` (`PIL.ImageGrab`) - Captures single-pixel screenshots for color detection
  - Used in: `color_detector.py` via `ImageGrab.grab(bbox=(x, y, x+1, y+1))`
  - Reads RGB values to determine if a scratched tile is blue (win) or red (loss)

**Keyboard/Mouse Hooks:**
- `pynput.keyboard.Listener` - Global keyboard hook for ESC key to stop game
  - Used in: `game_engine.py` (GameEngine.start_keyboard_listener)
- `pynput.mouse.Listener` - Global mouse hook for coordinate recording workflow
  - Used in: `coordinate_manager.py` (CoordinateRecorder)
  - Uses Win32-specific `win32_event_filter` for click suppression during recording

## Browser Game Interface

The application automates a browser-based "Gratta e Vinci" scratch card game. Integration is entirely coordinate-based:

**Configured UI Elements (screen coordinates stored in settings):**
- Play/Collect button: `play_x`, `play_y`
- Raise bet button: `raise_x`, `raise_y`
- Lower bet button: `lower_x`, `lower_y`
- Raise difficulty button: `raise_diff_x`, `raise_diff_y`
- Lower difficulty button: `lower_diff_x`, `lower_diff_y`
- 25 tile positions (5x5 grid): `tiles` dict mapping tile number to `[x, y]`

**Color Detection Protocol:**
- After clicking a tile, reads pixel color at tile coordinates
- Blue RGB(1, 108, 238) with tolerance +/-50 = positive tile (coin)
- Red RGB(200, 13, 1) with tolerance +/-50 = negative tile (mine/loss)
- Unknown color triggers retry loop with configurable delay

---

*Integration audit: 2026-03-10*
