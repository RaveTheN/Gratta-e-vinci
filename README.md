# Gratta-e-Vinci Automation GUI

A standalone GUI application for automating the Gratta-e-Vinci gambling game with configurable settings and real-time mouse coordinate display.

## Features

### 🎮 Game Control
- **Start/Stop automation** with escape key support
- **Real-time mouse coordinates** display
- **Test mode** for simulation without real clicks
- **Configurable betting strategies** (normal, medium, high, safe)

### ⚙️ Configurable Settings
- **Starting cash** and target win amounts
- **Maximum loss** and round limits
- **Betting mode** selection
- **Control point coordinates** (play/collect, raise/lower bet buttons)
- **25-tile grid positions** (5x5 layout)
- **Auto-save/load settings** to JSON file

### 📊 Real-time Statistics
- Current cash and highest cash reached
- Current bet and highest bet placed
- Round count and consecutive losses
- Total loss from peak cash
- Progress bar with round indicator

### 🖱️ Mouse Coordinate Tools
- **Live coordinate display** updated every 100ms
- **Copy coordinates** to clipboard
- **Auto-generate grid** for tile positions
- **Test click** functionality for validation

## Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application:**
   ```bash
   python gratta_e_vinci_gui.py
   ```
   
   Or use the batch file on Windows:
   ```bash
   run_gui.bat
   ```

## Required Dependencies

- `pynput==1.8.1` - Keyboard monitoring for escape key detection
- `pyautogui==0.9.54` - Mouse automation and screen capture
- `Pillow==10.4.0` - Image processing for color detection

## Usage Guide

### 1. Settings Tab
Configure your game parameters:
- **Starting Cash**: Your initial bankroll
- **Target Win**: Stop when you reach this amount
- **Max Loss**: Stop when losses exceed this amount
- **Max Rounds**: Maximum number of rounds to play
- **Max Picks**: Choose 2 or 3 picks per round
- **Betting Mode**: Select your risk strategy
- **Control Points**: Set coordinates for game buttons

### 2. Coordinates Tab
Set up your screen coordinates:
- **Mouse Position**: Real-time coordinate display
- **Copy Current Position**: Save coordinates to clipboard
- **Tile Positions**: Configure the 5x5 grid of scratch tiles
- **Auto-Generate Grid**: Automatically calculate grid positions
- **Test Click**: Verify tile positions work correctly

### 3. Game Control Tab
Control the automation:
- **🎰 START GAME**: Begin REAL automated play with mouse control
- **🛑 STOP GAME**: Stop automation immediately
- **🧪 TEST MODE**: Run simulation WITHOUT mouse control (safe testing)
- **Status Log**: View real-time game events and statistics

⚠️ **Important Difference:**
- **START GAME**: Controls your mouse and interacts with the actual game
- **TEST MODE**: Only simulates betting strategy without touching your mouse

### 4. Statistics Tab
Monitor your progress:
- **Current Game Stats**: Cash, bets, rounds, losses
- **Progress Bar**: Visual progress through max rounds
- **Real-time Updates**: Statistics update during gameplay

## Safety Features

### ⚠️ Important Safety Notes
- **Escape Key**: Press ESC at any time to stop automation
- **Test Mode**: Use test mode to verify settings before real play
- **Manual Override**: You can always click the STOP button
- **Settings Backup**: Settings are automatically saved to `gratta_settings.json`

### 🛡️ Risk Management
- Set reasonable **max loss** limits
- Use **target win** amounts to lock in profits
- Monitor **highest bet** to control risk escalation
- Review **statistics** regularly during play

## Configuration Files

### gratta_settings.json
Automatically saves all your settings:
```json
{
  "starting_cash": 2001.50,
  "target_win": 2100.0,
  "max_loss": 10.0,
  "max_rounds": 100,
  "max_picks": 3,
  "mode": "normal",
  "tiles": {
    "1": [1640, 740],
    "2": [1810, 740],
    ...
  }
}
```

## Screen Resolution Setup

The default coordinates are set for:
- **Screen Resolution**: 1920x1080 or higher
- **Game Window**: Full screen or maximized
- **Tile Grid**: 5x5 layout starting at (1640, 740)
- **Spacing**: 170px horizontal, 128px vertical

### Custom Resolution Setup
1. Go to **Coordinates Tab**
2. Use **mouse position display** to find your coordinates
3. **Copy current position** for each button and tile
4. **Test click** to verify positions work
5. **Save settings** to preserve your configuration

## Troubleshooting

### Common Issues
1. **Wrong coordinates**: Use the coordinate display to find correct positions
2. **Automation not working**: Check if game window is active and visible
3. **Settings not saving**: Ensure write permissions in the application folder
4. **Escape key not working**: Check if pynput is installed correctly

### Performance Tips
- Close unnecessary applications for better responsiveness
- Use test mode to verify setup before real play
- Monitor statistics to optimize betting strategy
- Save successful configurations for future use

## Disclaimer

This software is for educational purposes only. Gambling involves risk, and automated gambling systems should be used responsibly with proper risk management. The authors are not responsible for any financial losses incurred through the use of this software.

## Support

For issues or questions:
1. Check the status log for error messages
2. Verify all dependencies are installed
3. Test with test mode before real gameplay
4. Ensure proper screen coordinates are configured
