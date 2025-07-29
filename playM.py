import asyncio
import pyautogui
import pytesseract
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
import time
import random
import math

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
    1: Point(1581, 849),
    2: Point(1613, 780),
    3: Point(1565, 780),
    4: Point(1581, 780),
    5: Point(1613, 849),
    6: Point(1565, 849),
    7: Point(1581, 780),
    8: Point(1613, 780),
    9: Point(1565, 780),
    10: Point(1581, 849),
    11: Point(1613, 780),
    12: Point(1565, 780),
    13: Point(1581, 780),
    14: Point(1613, 849),
    15: Point(1565, 849),
    16: Point(1581, 780),
    17: Point(1613, 780),
    18: Point(1565, 780),
    19: Point(1581, 849),
    20: Point(1613, 780),
    21: Point(1565, 780),
    22: Point(1581, 780),
    23: Point(1613, 849),
    24: Point(1565, 849),
    25: Point(1581, 780)
}

# Main control points
play_collect = Point(1581, 849)
raise_bet = Point(1613, 780)
lower_bet = Point(1565, 780)

color = {"r": 0, "g": 0, "b": 0, "a": 0}

# Define target colors
target_blue = {"r": 0, "g": 0, "b": 255}  # Pure blue
target_red = {"r": 255, "g": 0, "b": 0}   # Pure red

# Global variables
starting_cash = round(50, 2)  # Round to 2 decimal places
current_cash = round(0, 2)  # Round to 2 decimal places
highest_cash = round(0, 2)  # Round to 2 decimal places
bet = round(0.1, 2)  # Round to 2 decimal places
picks = 0
tries = 0
rounds = 0
randoms = []
temp_random = 0
loss = round(0, 2)  # Round to 2 decimal places
max_loss = round(10, 2)  # Round to 2 decimal places
max_rounds = 100
max_picks = 3
target_win = round(100, 2)  # Round to 2 decimal places
wait_selected = False
bet_values = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0,1.2,1.4,1.5,1.6,1.8,2.0,2.5,3.0,3.5,4.0,4.5,5.0,6.0,7.0,8.0,9.0,10.0,12.0,14.0,16.0,18.0,20.0,25.0]

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

# Function to increase bet
async def increase_bet():
    await sleep(0.5)  # Small delay to ensure click is registered
    pyautogui.click(raise_bet.x, raise_bet.y)
    global bet
    current_index = bet_values.index(bet) if bet in bet_values else 0
    bet = round(bet_values[min(current_index + 1, len(bet_values) - 1)], 2)  # Increase bet to next value and round
    print(f"Bet increased to: {format_money(bet)}")

# Function to decrease bet  
async def decrease_bet():
    await sleep(0.5)
    pyautogui.click(lower_bet.x, lower_bet.y)
    global bet
    current_index = bet_values.index(bet) if bet in bet_values else 0
    bet = round(bet_values[max(current_index - 1, 0)], 2)  # Decrease bet to previous value and round
    print(f"Bet decreased to: {format_money(bet)}")

# Function to play/collect
async def play_or_collect():
    await sleep(0.5)
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
    print(f"Current cash: {format_money(current_cash)}, Highest cash: {format_money(highest_cash)}, Bet: {format_money(bet)}, Picks: {picks}, Tries: {tries}, Rounds: {rounds}")

# Function to save new highest cash
async def save_new_highest_cash():
    global highest_cash, current_cash
    if current_cash > highest_cash:
        highest_cash = round(current_cash, 2)  # Round to 2 decimal places
        print(f"New highest cash saved: {format_money(highest_cash)}")

# Function to get corresponding bet value from mode array
def get_bet_from_mode_array():
    global bet, tries, selected_mode
    if tries < len(selected_mode):
        bet = round(selected_mode[tries], 2)  # Round to 2 decimal places
        print(f"Bet set from mode array: {bet}")
    else:
        bet = round(0, 2)  # Round to 2 decimal places
        print("Bet set to 0 - beyond mode array")

#Main function to run the game logic  
async def main():
    global current_cash, highest_cash, bet, picks, tries, rounds, loss
    
    # START - Initialize starting cash (startup old recast relevant data)
    current_cash = round(starting_cash, 2)  # Round to 2 decimal places
    highest_cash = round(starting_cash, 2)  # Round to 2 decimal places
    bet = round(0.1, 2)  # Round to 2 decimal places
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

        # Optional wait
        if wait_selected:
            await random_await()
        
        # Start new round - reset picks and prepare for new game
        picks = 0
        empty_randoms()
        round_active = True
        
        # Press play to start the round (no cash deduction yet)
        await sleep(1)
        await play_or_collect()
        print(f"Started new round {rounds + 1} with bet: {format_money(bet)}")
        
        # Keep picking tiles until we get 3 blues (win) or 1 red (lose)
        while round_active and picks < max_picks:
            # Generate random tile number
            generate_random_tile()
            
            # Wait for game to process
            await sleep(5)
            
            # Click on the corresponding tile
            await click_tile(randoms[-1])
            await sleep(2)
            
            # Check color of the revealed tile with retry mechanism
            color_detected = False
            retry_count = 0
            max_retries = 3
            
            while not color_detected and retry_count < max_retries:
                color = read_color_at_point(Point(1581, 849))
                
                if is_color_in_range_blue(color, target_blue):
                    # BLUE tile found
                    print(f"Tile {randoms[-1]} is BLUE")
                    increase_picks()
                    color_detected = True
                    
                    # Check if we got 3 blues (WIN)
                    if picks >= max_picks:
                        print("🎉 THREE BLUES! ROUND WON!")
                        
                        # Press collect to get winnings
                        await sleep(1)
                        await play_or_collect()
                        
                        # Increase cash by bet times multiplier (we win!)
                        await increase_cash()
                        await save_new_highest_cash()
                        
                        # Reset for next round
                        picks = 0
                        tries = 0
                        round_active = False
                        
                        log_state()
                        
                    else:
                        # Continue picking - we have less than 3 blues
                        print(f"Got {picks} blue(s), need {max_picks - picks} more...")
                        
                elif is_color_in_range_red(color, target_red):
                    # RED tile found - ROUND LOST
                    print(f"❌ Tile {randoms[-1]} is RED - ROUND LOST!")
                    color_detected = True
                    
                    # Lose the bet amount
                    await decrease_cash()
                    
                    # Update tries and betting strategy
                    increase_tries()
                    
                    # Get next bet amount from mode array
                    get_bet_from_mode_array()
                    
                    # Check if we can afford the next bet
                    if round(current_cash, 2) < round(bet, 2):  # Round both values for comparison
                        print("Insufficient cash for next bet!")
                        break
                    
                    # Set the new bet amount in the game
                    await decrease_bet_force()
                    if bet > 0:
                        target_bet_index = bet_values.index(bet) if bet in bet_values else 0
                        for i in range(target_bet_index):
                            await increase_bet()
                    
                    # Calculate loss and check limits
                    loss = round(highest_cash - current_cash, 2)  # Round to 2 decimal places
                    if round(loss, 2) >= round(max_loss, 2):  # Round both values for comparison
                        print("Reached maximum loss!")
                        break
                    
                    # Reset picks and end round
                    picks = 0
                    round_active = False
                    
                    log_state()
                    
                else:
                    # Unknown color detected - retry after waiting
                    retry_count += 1
                    print(f"❓ Tile {randoms[-1]} - Unknown color detected (attempt {retry_count}/{max_retries})")
                    log_color_debug(Point(1581, 849), color)
                    
                    if retry_count < max_retries:
                        print("   Waiting 1 second and retrying color detection...")
                        await sleep(1)
                    else:
                        print("   Max retries reached, skipping this tile...")
                        color_detected = True  # Exit the retry loop
                        continue  # Continue to next tile
        
        # Round completed, increment round counter
        increase_rounds()
    
    print("=== GAME END ===")
    print(f"Final stats - Cash: {format_money(current_cash)}, Highest: {format_money(highest_cash)}, Rounds: {rounds}, Loss: {format_money(loss)}")

if __name__ == "__main__":
    print("🎰 Starting Gratta-e-Vinci Automation")
    print("⚠️  WARNING: This will control your mouse and keyboard!")
    print("   Make sure your game window is positioned correctly.")
    print("   Press Ctrl+C or move mouse to top-left corner to stop.")
    
    try:
        import asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Game stopped by user")
    except Exception as e:
        print(f"\n❌ Error occurred: {e}")
        import traceback
        traceback.print_exc()
