# Testing Guide for playM.py

## Prerequisites

### 1. Install Python Dependencies
```powershell
pip install -r requirements.txt
```

### 2. Install Tesseract OCR
1. Download Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install it (usually to `C:\Program Files\Tesseract-OCR\`)
3. Add to your PATH or set the path in Python

### 3. If Tesseract Path Issues
Add this line to your script if needed:
```python
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

## Testing Steps

### Step 1: Test Environment Setup
```powershell
python test_setup.py
```
This will verify all dependencies are working.

### Step 2: Test Without Game (Dry Run)
Create a safe test mode by modifying the script temporarily.

### Step 3: Test With Game
⚠️ **IMPORTANT SAFETY WARNINGS** ⚠️
- The script will control your mouse automatically
- Have pyautogui.FAILSAFE = True (move mouse to corner to stop)
- Position your game window correctly
- Start with small values (low bet, short test)

## Manual Testing Process

### Phase 1: Static Testing
1. **Test Point Coordinates**: Verify all click positions are correct
2. **Test Color Detection**: Check if blue/red detection works
3. **Test Screenshot**: Verify screen capture works

### Phase 2: Interactive Testing  
1. **Test Single Click**: Test one tile click
2. **Test Bet Changes**: Test raise/lower bet functions
3. **Test Play/Collect**: Test the main game button

### Phase 3: Full Game Testing
1. **Short Run**: Set max_rounds = 1 for testing
2. **Monitor Output**: Watch console logs carefully
3. **Emergency Stop**: Keep mouse ready to move to corner

## Debugging Tips

### Common Issues:
1. **Wrong Click Positions**: Game window must be in exact same position
2. **Color Detection Fails**: Adjust tolerance values or target colors
3. **Timing Issues**: Increase sleep delays if clicks are too fast
4. **Tesseract Errors**: Check OCR installation

### Troubleshooting Commands:
```powershell
# Test mouse position
python -c "import pyautogui; print(pyautogui.position())"

# Test screenshot
python -c "import pyautogui; pyautogui.screenshot().save('test.png')"

# Test color at point
python -c "import pyautogui; print(pyautogui.screenshot().getpixel((1581, 849)))"
```

## Safety Features in Script

The script has these safety features:
- `pyautogui.FAILSAFE = True` - Move mouse to corner to stop
- `pyautogui.PAUSE = 0.1` - Pause between actions
- Cash/Loss limits to prevent unlimited losses
- Round limits to prevent infinite loops

## Recommended Test Settings

For initial testing, modify these values in playM.py:
```python
max_rounds = 3          # Test only 3 rounds
max_loss = 5           # Low loss limit
target_win = 60        # Low win target
wait_selected = False  # No random waits during testing
```

## Emergency Stop

If something goes wrong:
1. **Move mouse to top-left corner** (triggers pyautogui failsafe)
2. **Ctrl+C** in terminal
3. **Alt+Tab** to switch away from game window
