"""
Safe test version of playM.py - No actual mouse clicks with highest bet tracking
This version simulates the game logic without performing real mouse actions
"""
import asyncio
import random
from pynput import keyboard

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def __repr__(self):
        return f"Point({self.x}, {self.y})"

def format_money(value):
    """Format monetary values to always show exactly 2 decimal places"""
    return f"{round(value, 2):.2f}"

# Function to handle escape key press
def on_key_press(key):
    global escape_pressed
    if key == keyboard.Key.esc:
        print("\n🛑 ESCAPE key pressed - stopping test...")
        escape_pressed = True
        return False  # Stop the listener

# Function to start keyboard listener
def start_keyboard_listener():
    global escape_pressed
    escape_pressed = False
    listener = keyboard.Listener(on_press=on_key_press)
    listener.start()
    return listener

# Simulate game variables
starting_cash = 50
current_cash = 50
highest_cash = 50
bet = 0.1
highest_bet = 0.1  # Track highest bet placed
picks = 0
tries = 0
rounds = 0
randoms = []
loss = 0
max_loss = 10
max_rounds = 10  # Increased for better testing
max_picks = 3
target_win = 100

# Escape key detection
escape_pressed = False

# Game mode
multiplier = 2.4
selected_mode = [0.1, 0.2, 0.3, 0.5, 0.8, 1.4, 2.5, 4.5, 8.0, 14.0, 20.0]

async def simulate_click(point, action_name):
    """Simulate a mouse click"""
    await asyncio.sleep(0.1)
    print(f"[SIMULATED] {action_name} at {point}")

async def simulate_color_check():
    """Simulate color detection - 19 blue tiles, 6 red tiles out of 25"""
    await asyncio.sleep(0.1)
    # Simulate realistic game: 19 blue (76%), 6 red (24%)
    # Added small chance for unknown color to test retry mechanism
    rand = random.random()
    if rand < 0.76:  # 76% chance blue (19/25)
        return "blue"
    elif rand < 0.95:  # 19% chance red (6/25 ≈ 24%, but leaving 5% for unknown)
        return "red"
    else:
        return "unknown"  # 5% chance unknown (to test retry mechanism)

# Test functions
async def test_increase_cash():
    global current_cash, highest_cash
    current_cash += bet * multiplier
    current_cash = round(current_cash, 2)  # Round to 2 decimal places
    if current_cash > highest_cash:
        highest_cash = round(current_cash, 2)  # Round to 2 decimal places
    print(f"Cash increased to: {format_money(current_cash)}, Highest: {format_money(highest_cash)}")

async def test_decrease_cash():
    global current_cash
    current_cash -= bet
    current_cash = round(current_cash, 2)  # Round to 2 decimal places
    print(f"Cash decreased to: {format_money(current_cash)}")

def test_get_bet_from_mode_array():
    global bet, tries, selected_mode, highest_bet
    if tries < len(selected_mode):
        bet = selected_mode[tries]
        print(f"Bet set from mode array: {format_money(bet)}")
        # Update highest bet if this is a new high
        if bet > highest_bet:
            highest_bet = round(bet, 2)
            print(f"🎯 New highest bet recorded: {format_money(highest_bet)}")
    else:
        bet = 0
        print("Bet set to 0 - beyond mode array")

def test_log_state():
    print(f"💰 Cash: {format_money(current_cash)} | 📈 Highest: {format_money(highest_cash)} | 🎰 Bet: {format_money(bet)} | 🔝 Highest bet: {format_money(highest_bet)} | 🎯 Picks: {picks} | 🔄 Tries: {tries} | 🏁 Round: {rounds}")

def test_generate_random_tile():
    global randoms
    while True:
        temp_random = random.randint(1, 25)
        if temp_random not in randoms:
            randoms.append(temp_random)
            print(f"🎲 Generated tile: {temp_random}")
            return temp_random

def test_empty_randoms():
    global randoms
    randoms = []
    print("🗑️ Randoms cleared")

async def test_main_game_logic():
    """Test the main game logic without actual automation"""
    global current_cash, highest_cash, bet, highest_bet, picks, tries, rounds, loss, escape_pressed
    
    # Start keyboard listener for escape key detection
    keyboard_listener = start_keyboard_listener()
    
    print("🎮 === SAFE TEST MODE - NO ACTUAL MOUSE ACTIONS ===")
    print(f"🚀 Starting with cash: {format_money(current_cash)}")
    
    # Main game loop
    while True:
        # Check for escape key press
        if escape_pressed:
            print("🛑 Test stopped by escape key")
            break
            
        # Check end conditions
        if rounds >= max_rounds:
            print("🏁 Reached maximum test rounds!")
            break
        if current_cash >= target_win:
            print("🎉 Reached target win!")
            break
        if loss >= max_loss:
            print("💸 Reached maximum loss!")
            break
        if current_cash < bet:
            print("💀 Insufficient cash for bet!")
            break

        # Start new round
        print(f"\n=== Round {rounds + 1} ===")
        picks = 0
        test_empty_randoms()
        round_active = True
        
        # Press play to start round and immediately deduct cash
        await simulate_click(Point(1581, 849), "PLAY - START ROUND")
        print(f"🎰 Started round with bet: {format_money(bet)} - Cash deducted immediately")
        await test_decrease_cash()  # Deduct bet amount immediately when starting round

        # Keep picking until 3 blues (win) or 1 red (lose)
        while round_active and picks < max_picks:
            # Check for escape key press during round
            if escape_pressed:
                print("🛑 Test stopped by escape key during round")
                round_active = False
                break
                
            # Generate and click tile
            tile_num = test_generate_random_tile()
            await simulate_click(Point(1500 + tile_num, 800), f"TILE {tile_num}")
            
            # Simulate color detection with retry mechanism
            color_detected = False
            retry_count = 0
            max_retries = 3
            
            while not color_detected and retry_count < max_retries:
                color_result = await simulate_color_check()
                
                if color_result == "blue":
                    print(f"🔵 Tile {tile_num} is BLUE!")
                    picks += 1
                    color_detected = True
                    
                    if picks >= max_picks:
                        print("🎊 THREE BLUES - ROUND WON!")
                        await simulate_click(Point(1581, 849), "COLLECT WINNINGS")
                        await test_increase_cash()
                        tries = 0  # Reset tries on win
                        round_active = False
                        print("🎯 WIN! Bet reset to minimum: 0.10")
                    else:
                        print(f"🎯 Got {picks} blue(s), need {max_picks - picks} more...")
                        
                elif color_result == "red":
                    print(f"🔴 Tile {tile_num} is RED - ROUND LOST!")
                    color_detected = True
                    
                    # Cash already deducted when round started, just update strategy
                    tries += 1
                    
                    # Reset picks and end round
                    picks = 0
                    round_active = False
                    
                    # Show round state first
                    test_log_state()
                    
                    # Then show betting strategy updates
                    test_get_bet_from_mode_array()
                    print(f"💸 LOSS! Bet increased to: {format_money(bet)} (try #{tries})")
                    
                    # Calculate loss and check limits
                    loss = round(highest_cash - current_cash, 2)
                    if loss >= max_loss:
                        print("📉 Reached maximum loss!")
                        break
                    
                else:
                    # Unknown color - retry
                    retry_count += 1
                    print(f"❓ Unknown color for tile {tile_num} (attempt {retry_count}/{max_retries})")
                    
                    if retry_count < max_retries:
                        print("   Waiting 1 second and retrying color detection...")
                        await asyncio.sleep(1)
                    else:
                        print("   Max retries reached, skipping this tile...")
                        color_detected = True
        
        # Round completed
        rounds += 1
        await asyncio.sleep(0.5)
    
    # Cleanup keyboard listener
    keyboard_listener.stop()
    
    print("\n🏆 === TEST COMPLETED ===")
    print(f"Final Results:")
    print(f"💰 Final Cash: {format_money(current_cash)}")
    print(f"📈 Highest Cash: {format_money(highest_cash)}")
    print(f"🔝 Highest Bet: {format_money(highest_bet)}")
    print(f"🏁 Rounds Completed: {rounds}")
    print(f"📉 Total Loss: {format_money(loss)}")
    print(f"🎯 Final Picks: {picks}")
    print(f"🔄 Final Tries: {tries}")

if __name__ == "__main__":
    print("🧪 Running safe test of game logic...")
    print("   Press ESCAPE key or Ctrl+C to stop the test.")
    try:
        asyncio.run(test_main_game_logic())
        print("✅ Test completed successfully!")
    except KeyboardInterrupt:
        print("\n⚠️ Test stopped by user (Ctrl+C)")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
