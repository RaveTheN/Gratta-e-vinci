import asyncio
import pyautogui
# import pytesseract  # Comment out for now
# import cv2          # Comment out for now  
# import numpy as np  # Comment out for now
import random
from pynput import keyboard

# Configure mouse speed (pyautogui uses duration for speed control)
pyautogui.PAUSE = 0.1  # Pause between pyautogui calls
pyautogui.FAILSAFE = True  # Move mouse to corner to abort

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def __repr__(self):
        return f"Point({self.x}, {self.y})"
    
# Click point positions
# Dictionary of tiles with their positions
tiles = {
    1: Point(1283, 417),
    2: Point(1363, 417),
    3: Point(1443, 417),
    4: Point(1523, 417),
    5: Point(1603, 417),
    6: Point(1283, 476),
    7: Point(1363, 476),
    8: Point(1443, 476),
    9: Point(1523, 476),
    10: Point(1603, 476),
    11: Point(1283, 535),
    12: Point(1363, 535),
    13: Point(1443, 535),
    14: Point(1523, 535),
    15: Point(1603, 535),
    16: Point(1283, 594),
    17: Point(1363, 594),
    18: Point(1443, 594),
    19: Point(1523, 594),
    20: Point(1603, 594),
    21: Point(1283, 594),
    22: Point(1363, 594),
    23: Point(1443, 594),
    24: Point(1523, 594),
    25: Point(1603, 594)
}

# Main control points
play_collect = Point(1528, 829)
raise_bet = Point(1411, 889)
lower_bet = Point(1238, 889)
# lower_bet = Point(1028, 666)

color = {"r": 0, "g": 0, "b": 0, "a": 0}

# Define target colors
target_blue = {"r": 1, "g": 108, "b": 238}  # Actual blue tile color
target_red = {"r": 200, "g": 13, "b": 1}    # Updated red tile color

# Global variables
starting_cash = round(2001.50, 2)  # Round to 2 decimal places
current_cash = round(0, 2)  # Round to 2 decimal places
highest_cash = round(0, 2)  # Round to 2 decimal places
bet = round(0.1, 2)  # Round to 2 decimal places
highest_bet = round(0.1, 2)  # Track highest bet placed
picks = 0
tries = 0
rounds = 0
randoms = []
temp_random = 0
loss = round(0, 2)  # Round to 2 decimal places
max_loss = round(10, 2)  # Round to 2 decimal places
max_rounds = 100
max_picks = 3
target_win = round(2100, 2)  # Round to 2 decimal places
wait_selected = False
bet_values = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0,1.2,1.4,1.5,1.6,1.8,2.0,2.5,3.0,3.5,4.0,4.5,5.0,6.0,7.0,8.0,9.0,10.0,12.0,14.0,16.0,18.0,20.0,25.0]

# Escape key detection
escape_pressed = False

# Multiplier for bet increase
multiplier = round(2.4, 2)  # Round to 2 decimal places

#Modes

modes={
    "normal": [0.1, 0.2, 0.3, 0.5, 0.8, 1.4, 2.5, 4.5, 8.0, 14.0, 20.0],
    "medium": [0.1, 0.2, 0.3, 0.5, 0.9, 1.5, 3.0, 5.0, 9.0, 15.0, 20.0],
    "high": [0.2, 0.3, 0.6, 1.0, 1.8, 3.0, 5.0, 9.0, 16.0, 20.0],
    "safe": [0.1, 0.1, 0.2, 0.3, 0.5, 1.0, 1.8, 3.0, 5.0, 9.0, 15.0, 20.0]
}

selected_mode = modes["normal"]  # Default mode

# Functions

# Sleep function
async def sleep(seconds):
    await asyncio.sleep(seconds)


# Function to generate a random number from 1 to 25
def get_random_number():
    return random.randint(1, 25)

# Function to get a random number of minutes for the waiting period
async def random_await():
    await sleep(random.randint(1*60, 6*60))  # Random wait between 1 and 6 minutes

# Function to format number to always show 2 decimal places
def format_money(value):
    """Format a number to always show exactly 2 decimal places"""
    return f"{round(value, 2):.2f}"

# Function to handle escape key press
def on_key_press(key):
    global escape_pressed
    if key == keyboard.Key.esc:
        print("\n🛑 ESCAPE key pressed - stopping game...")
        escape_pressed = True
        return False  # Stop the listener

# Function to start keyboard listener
def start_keyboard_listener():
    global escape_pressed
    escape_pressed = False
    listener = keyboard.Listener(on_press=on_key_press)
    listener.start()
    return listener

# Function to increase bet
async def increase_bet():
    await sleep(2)  # Small delay to ensure click is registered
    pyautogui.click(raise_bet.x, raise_bet.y)
    global bet
    current_index = bet_values.index(bet) if bet in bet_values else tries
    bet = round(bet_values[min(current_index + 1, len(bet_values) - 1)], 2)  # Increase bet to next value and round
    print(f"Bet increased to: {format_money(bet)}")

# Function to decrease bet  
async def decrease_bet():
    await sleep(1)
    pyautogui.click(lower_bet.x, lower_bet.y)
    global bet
    current_index = bet_values.index(bet) if bet in bet_values else 0
    bet = round(bet_values[max(current_index - 1, 0)], 2)  # Decrease bet to previous value and round
    print(f"Bet decreased to: {format_money(bet)}")

# Function to play/collect
async def play_or_collect():
    await sleep(1)
    pyautogui.click(play_collect.x, play_collect.y)
    print("Clicked play/collect button")

# Function to force decrease bet
async def decrease_bet_force():
    global bet
    for i in range(len(bet_values)):
        await sleep(0.05)
        pyautogui.click(lower_bet.x, lower_bet.y)
    bet = round(0.1, 2)  # Ensure bet is set to minimum and rounded
    print("Bet forced to minimum: 0.1")

# Function to increase the value of the current cash
async def increase_cash():
    global current_cash, highest_cash
    await sleep(0.5)
    current_cash += bet * multiplier
    current_cash = round(current_cash, 2)  # Round to 2 decimal places
    if current_cash > highest_cash:
        highest_cash = round(current_cash, 2)  # Round to 2 decimal places
    print(f"Current cash increased to: {format_money(current_cash)}, Highest cash: {format_money(highest_cash)}")

# Function to decrease the value of the current cash
async def decrease_cash():
    global current_cash
    await sleep(0.5)
    current_cash -= bet
    current_cash = round(current_cash, 2)  # Round to 2 decimal places
    print(f"Current cash decreased to: {format_money(current_cash)}")

# Function to click on a tile based on its number
async def click_tile(tile_number):
    if tile_number in tiles:
        point = tiles[tile_number]
        await sleep(0.5)  # Small delay to ensure click is registered
        pyautogui.click(point.x, point.y)
        print(f"Clicked on tile {tile_number} at position {point}")

#Function to generate a random tile, if it has not been selected yet
def generate_random_tile():
    global randoms, temp_random
    while True:
        temp_random = get_random_number()
        if temp_random not in randoms:
            randoms.append(temp_random)
            print(f"Generated random tile: {temp_random}")
            return temp_random
        
# Function to empty the randoms list
def empty_randoms():
    global randoms
    randoms = []
    print("Randoms list emptied")

# Function to increase the value of picks
def increase_picks():
    global picks
    picks += 1
    print(f"Picks increased to: {picks}")

# Function to decrease the value of picks
def decrease_picks():
    global picks
    if picks > 0:
        picks -= 1
    print(f"Picks decreased to: {picks}")

# Function to increase the value of tries
def increase_tries():
    global tries
    tries += 1
    print(f"Tries increased to: {tries}")

# Function to decrease the value of tries
def decrease_tries():
    global tries
    if tries > 0:
        tries -= 1
    print(f"Tries decreased to: {tries}")

# Function to increase the value of rounds
def increase_rounds():
    global rounds
    rounds += 1
    print(f"Rounds increased to: {rounds}")

# Function to decrease the value of rounds
def decrease_rounds():
    global rounds
    if rounds > 0:
        rounds -= 1
    print(f"Rounds decreased to: {rounds}")

# Function to log color information for debugging
def log_color_debug(point, color):
    print(f"🎨 Color at {point}: RGB({color['r']}, {color['g']}, {color['b']})")
    print(f"   Blue match (tolerance 50): {is_color_in_range_blue(color, target_blue, 50)}")
    print(f"   Red match (tolerance 50): {is_color_in_range_red(color, target_red, 50)}")

# Function to read color at a point on screen
def read_color_at_point(point):
    # Take screenshot
    screenshot = pyautogui.screenshot()
    
    # Get pixel color at specified point
    pixel_color = screenshot.getpixel((point.x, point.y))
    
    # Convert to RGBA format
    if len(pixel_color) == 3:  # RGB
        r, g, b = pixel_color
        a = 255
    else:  # RGBA
        r, g, b, a = pixel_color
    
    return {"r": r, "g": g, "b": b, "a": a}

# Function to check if color is in blue range
def is_color_in_range_blue(color, target_color, tolerance=50):
    return (
        abs(color["r"] - target_color["r"]) <= tolerance and
        abs(color["g"] - target_color["g"]) <= tolerance and
        abs(color["b"] - target_color["b"]) <= tolerance
    )

# Function to check if color is in red range  
def is_color_in_range_red(color, target_color, tolerance=50):
    return (
        abs(color["r"] - target_color["r"]) <= tolerance and
        abs(color["g"] - target_color["g"]) <= tolerance and
        abs(color["b"] - target_color["b"]) <= tolerance
    )

# Function to log the current state
def log_state():
    print(f"Current cash: {format_money(current_cash)}, Highest cash: {format_money(highest_cash)}, Bet: {format_money(bet)}, Highest bet: {format_money(highest_bet)}, Picks: {picks}, Tries: {tries}, Rounds: {rounds}")

# Function to save new highest cash
async def save_new_highest_cash():
    global highest_cash, current_cash
    if current_cash > highest_cash:
        highest_cash = round(current_cash, 2)  # Round to 2 decimal places
        print(f"New highest cash saved: {format_money(highest_cash)}")

# Function to update highest bet
def update_highest_bet():
    global highest_bet, bet
    if bet > highest_bet:
        highest_bet = round(bet, 2)  # Round to 2 decimal places
        print(f"🎯 New highest bet recorded: {format_money(highest_bet)}")


#Main function to run the game logic  
async def main():
    global current_cash, highest_cash, bet, highest_bet, picks, tries, rounds, loss, multiplier, max_loss, max_rounds, max_picks, target_win, wait_selected, selected_mode, escape_pressed

    # Start keyboard listener for escape key detection
    keyboard_listener = start_keyboard_listener()

    #if max picks is not set, default to 3
    if max_picks <= 0:
        max_picks = 3
    
    # If max rounds is not set, default to 100
    if max_rounds <= 0:
        max_rounds = 100
    
    # If max loss is not set, default to 10
    if max_loss <= 0:
        max_loss = 10

    # If max picks is 2 set multipliter to 1.8, if 3 set to 2.4
    if max_picks == 2:
        multiplier = round(1.8, 2)
    elif max_picks == 3:
        multiplier = round(2.4, 2)

    # START - Initialize starting cash (startup old recast relevant data)
    current_cash = round(starting_cash, 2)  # Round to 2 decimal places
    highest_cash = round(starting_cash, 2)  # Round to 2 decimal places
    bet = round(0.1, 2)  # Round to 2 decimal places
    highest_bet = round(0.1, 2)  # Initialize highest bet tracking
    picks = 0
    tries = 0
    rounds = 0
    loss = round(0, 2)  # Round to 2 decimal places
    randoms.clear()  # Clear previous randoms

    print("=== GAME START ===")
    print("Starting game with initial cash:", format_money(current_cash))

    # Press start & Force set bet to 0.1
    await decrease_bet_force()
    log_state()

    # Main game loop
    while True:
        # Check for escape key press
        if escape_pressed:
            print("🛑 Game stopped by escape key")
            break
            
        # Check if we've reached target or max rounds
        if rounds >= max_rounds:
            print("Reached maximum rounds!")
            break
        if round(current_cash, 2) >= round(target_win, 2):  # Round both values for comparison
            print("Reached target win!")
            break
        if round(loss, 2) >= round(max_loss, 2):  # Round both values for comparison
            print("Reached maximum loss!")
            break

        # Check if we can afford the current bet
        if round(current_cash, 2) < round(bet, 2):
            print("Insufficient cash for bet!")
            break

        # Optional wait
        if wait_selected:
            await random_await()
        
        # Start new round - reset picks and prepare for new game
        picks = 0
        empty_randoms()
        round_active = True
        
        # Press play to start the round and immediately deduct cash
        await play_or_collect()
        print(f"Started new round {rounds + 1} with bet: {format_money(bet)} - Cash deducted")
        await decrease_cash()  # Deduct bet amount immediately when starting round
        
        # Keep picking tiles until we get 3 blues (win) or 1 red (lose)
        while round_active and picks < max_picks:
            # Check for escape key press during round
            if escape_pressed:
                print("🛑 Game stopped by escape key during round")
                round_active = False
                break
                
            # Generate random tile number
            generate_random_tile()
            
            # Wait for game to process
            await sleep(1)
            
            # Click on the corresponding tile
            await click_tile(randoms[-1])
            await sleep(1)

            # Check color of the revealed tile with retry mechanism
            color_detected = False
            retry_count = 0
            max_retries = 3
            
            while not color_detected and retry_count < max_retries:
                # Get the position of the tile we just clicked
                clicked_tile_position = tiles[randoms[-1]]
                color = read_color_at_point(clicked_tile_position)
                
                # Print the actual color values detected
                print(f"🎨 Color detected at tile {randoms[-1]} position ({clicked_tile_position.x}, {clicked_tile_position.y}): RGB({color['r']}, {color['g']}, {color['b']}, {color['a']})")
                
                if is_color_in_range_blue(color, target_blue):
                    # BLUE tile found
                    print(f"✅ Tile {randoms[-1]} is BLUE - Matches target blue RGB(115, 9, 131)")
                    increase_picks()
                    color_detected = True
                    
                    # Check if we got 3 blues (WIN)
                    if picks >= max_picks:
                        print("🎉 THREE BLUES! ROUND WON!")
                        
                        # Press collect to get winnings
                        await play_or_collect()
                        
                        # Increase cash by bet times multiplier (we win!)
                        await increase_cash()
                        await save_new_highest_cash()
                        
                        # Reset betting strategy after win - back to minimum bet
                        tries = 0  # Reset tries counter
                        picks = 0  # Reset picks for next round

                        #decrease bet down to minimum
                        while bet > 0.1:
                            await decrease_bet()

                        print(f"🎯 WIN! Bet reset to minimum: {format_money(bet)}")
                        
                        # Reset for next round
                        round_active = False
                        
                        log_state()
                        
                    else:
                        # Continue picking - we have less than 3 blues
                        print(f"Got {picks} blue(s), need {max_picks - picks} more...")
                        
                elif is_color_in_range_red(color, target_red):
                    # RED tile found - ROUND LOST
                    print(f"❌ Tile {randoms[-1]} is RED - Matches target red RGB(200, 13, 1)")
                    color_detected = True
                    
                    # Cash already deducted when round started, just update strategy
                    increase_tries()

                    # Reset picks and end round
                    picks = 0
                    round_active = False
                    
                    log_state()
                    
                    # Now update betting strategy after showing round results
                    print(f"Bet set from mode array: {format_money(selected_mode[tries])}")
                    while bet < selected_mode[tries]:
                        await increase_bet()
                    update_highest_bet()  # Track highest bet after increase
                    print(f"💸 LOSS! Bet increased to: {format_money(bet)} (try #{tries})")
                 
                    # Calculate loss and check limits
                    loss = round(highest_cash - current_cash, 2)  # Round to 2 decimal places
                    if round(loss, 2) >= round(max_loss, 2):  # Round both values for comparison
                        print("Reached maximum loss!")
                        break
                    
                else:
                    # Unknown color detected - retry after waiting
                    retry_count += 1
                    print(f"❓ Tile {randoms[-1]} - Unknown color detected (attempt {retry_count}/{max_retries})")
                    print(f"   Expected: Blue RGB(115, 9, 131) or Red RGB(200, 13, 1)")
                    print(f"   Actual: RGB({color['r']}, {color['g']}, {color['b']})")
                    print(f"   Blue match (tolerance 25): {is_color_in_range_blue(color, target_blue, 25)}")
                    print(f"   Red match (tolerance 50): {is_color_in_range_red(color, target_red, 50)}")
                    
                    if retry_count < max_retries:
                        print("   Waiting 1 second and retrying color detection...")
                        await sleep(1)
                    else:
                        print("   Max retries reached, skipping this tile...")
                        color_detected = True  # Exit the retry loop
                        continue  # Continue to next tile
        
        # Round completed, increment round counter
        increase_rounds()
    
    # Cleanup keyboard listener
    keyboard_listener.stop()
    
    print("=== GAME END ===")
    print(f"Final stats - Cash: {format_money(current_cash)}, Highest: {format_money(highest_cash)}, Highest bet: {format_money(highest_bet)}, Rounds: {rounds}, Loss: {format_money(loss)}")

if __name__ == "__main__":
    print("🎰 Starting Gratta-e-Vinci Automation")
    print("⚠️  WARNING: This will control your mouse and keyboard!")
    print("   Make sure your game window is positioned correctly.")
    print("   Press ESCAPE key or Ctrl+C to stop, or move mouse to top-left corner.")
    
    try:
        import asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Game stopped by user (Ctrl+C)")
    except Exception as e:
        print(f"\n❌ Error occurred: {e}")
        import traceback
        traceback.print_exc()
