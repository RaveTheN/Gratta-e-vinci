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
t1 = Point(1581, 849)
t2 = Point(1613, 780)
t3 = Point(1565, 780)
t4 = Point(1581, 780)
t5 = Point(1613, 849)
t6 = Point(1565, 849)
t7 = Point(1581, 780)
t8 = Point(1613, 780)
t9 = Point(1565, 780)
t10 = Point(1581, 849)
t11 = Point(1613, 780)
t12 = Point(1565, 780)
t13 = Point(1581, 780)
t14 = Point(1613, 849)
t15 = Point(1565, 849)
t16 = Point(1581, 780)
t17 = Point(1613, 780)
t18 = Point(1565, 780)
t19 = Point(1581, 849)
t20 = Point(1613, 780)
t21 = Point(1565, 780)
t22 = Point(1581, 780)
t23 = Point(1613, 849)
t24 = Point(1565, 849)
t25 = Point(1581, 780)

# Main control points
play_collect = Point(1581, 849)
raise_bet = Point(1613, 780)
lower_bet = Point(1565, 780)

color = {"r": 0, "g": 0, "b": 0, "a": 0}

# Define target colors
target_blue = {"r": 0, "g": 0, "b": 255}  # Pure blue
target_red = {"r": 255, "g": 0, "b": 0}   # Pure red

# Global variables
starting_cash = 0
current_cash = 0
highest_cash = 0
bet = 0.1
picks = 0
tries = 0
rounds = 0
randoms = []
temp_random = 0
max_loss = 10
max_rounds = 100
max_picks = 3
target_win = 100
wait_selected = False
bet_values = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0,1.2,1.4,1.5,1.6,1.8,2.0,2.5,3.0,3.5,4.0,4.5,5.0,6.0,7.0,8.0,9.0,10.0,12.0,14.0,16.0,18.0,20.0,25.0]

# Multiplier for bet increase
multiplier = 2.4

#Modes

modes={
    "normal": [0.1, 0.2, 0.3, 0.5, 0.8, 1.4, 2.5, 4.5, 8.0, 14.0, 20.0],
    "medium": [0.1, 0.2, 0.3, 0.5, 0.9, 1.5, 3.0, 5.0, 9.0, 15.0, 20.0],
    "high": [0.2, 0.3, 0.6, 1.0, 1.8, 3.0, 5.0, 9.0, 16.0, 20.0],
    "safe": [0.1, 0.1, 0.2, 0.3, 0.5, 1.0, 1.8, 3.0, 5.0, 9.0, 15.0, 20.0]
}

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

# Function to raise bet
async def raise_bet():
    await sleep(0.5)  # Small delay to ensure click is registered
    pyautogui.click(raise_bet.x, raise_bet.y)
    global bet
    bet = bet_values[min(bet_values.index(bet) + 1, len(bet_values) - 1)]  # Increase bet to next value
    print(f"Bet increased to: {bet}")

# Function to lower bet
async def lower_bet():
    await sleep(0.5)
    pyautogui.click(lower_bet.x, lower_bet.y)
    global bet
    bet = bet_values[max(bet_values.index(bet) - 1, 0)]  # Decrease bet to previous value
    print(f"Bet decreased to: {bet}")

# Function to play/collect
async def play_or_collect():
    await sleep(0.5)
    pyautogui.click(play_collect.x, play_collect.y)
    print("Clicked play/collect button")

# Function to force decrease bet (click 100 times)
async def decrease_bet_force():
    global bet
    for i in range(len(bet_values)):
        await sleep(0.5)
        pyautogui.click(lower_bet.x, lower_bet.y)
        print(f"Bet decreased to: {bet}")
    bet = 0.1  # Ensure bet doesn't go below minimum

# Function to increase the value of the current cash
async def increase_cash():
    global current_cash, highest_cash
    await sleep(0.5)
    current_cash += bet
    if current_cash > highest_cash:
        highest_cash = current_cash
    print(f"Current cash increased to: {current_cash}, Highest cash: {highest_cash}")

# Function to decrease the value of the current cash
async def decrease_cash():
    global current_cash
    await sleep(0.5)
    current_cash -= bet
    if current_cash < 0:
        current_cash = 0  # Ensure cash doesn't go below zero
    print(f"Current cash decreased to: {current_cash}")

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

