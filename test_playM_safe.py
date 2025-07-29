"""
Safe test version of playM.py - No actual mouse clicks
This version simulates the game logic without performing real mouse actions
"""
import asyncio
import random

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def __repr__(self):
        return f"Point({self.x}, {self.y})"

def format_money(value):
    """Format monetary values to always show exactly 2 decimal places"""
    return f"{round(value, 2):.2f}"

# Simulate game variables
starting_cash = 50
current_cash = 50
highest_cash = 50
bet = 0.1
picks = 0
tries = 0
rounds = 0
randoms = []
loss = 0
max_loss = 10
max_rounds = 5  # Short test
max_picks = 3
target_win = 100

modes = {
    "normal": [0.1, 0.2, 0.3, 0.5, 0.8, 1.4, 2.5, 4.5, 8.0, 14.0, 20.0],
    "safe": [0.1, 0.1, 0.2, 0.3, 0.5, 1.0, 1.8, 3.0, 5.0, 9.0, 15.0, 20.0]
}
selected_mode = modes["safe"]
multiplier = 2.4

# Simulate mouse actions (no actual clicking)
async def simulate_click(point, action_name):
    await asyncio.sleep(0.1)  # Simulate delay
    print(f"[SIMULATED] {action_name} at {point}")

async def simulate_color_check():
    """Simulate color detection - returns random result for testing"""
    await asyncio.sleep(0.1)
    # 50% chance blue, 30% chance red, 20% chance unknown (to test retry)
    rand = random.random()
    if rand < 0.5:
        return "blue"
    elif rand < 0.8:
        return "red"
    else:
        return "unknown"

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
    global bet, tries, selected_mode
    if tries < len(selected_mode):
        bet = selected_mode[tries]
        print(f"Bet set from mode array: {format_money(bet)}")
    else:
        bet = 0
        print("Bet set to 0 - beyond mode array")

def test_log_state():
    print(f"💰 Cash: {format_money(current_cash)} | 📈 Highest: {format_money(highest_cash)} | 🎰 Bet: {format_money(bet)} | 🎯 Picks: {picks} | 🔄 Tries: {tries} | 🏁 Round: {rounds}")

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
    global current_cash, highest_cash, bet, picks, tries, rounds, loss
    
    print("🎮 === SAFE TEST MODE - NO ACTUAL MOUSE ACTIONS ===")
    print(f"🚀 Starting with cash: {format_money(current_cash)}")
    
    # Main game loop
    while True:
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

        print(f"\n=== Round {rounds + 1} ===")
        
        # Start new round
        picks = 0
        test_empty_randoms()
        round_active = True
        
        # Press play to start round and immediately deduct cash
        await simulate_click(Point(1581, 849), "PLAY - START ROUND")
        await test_decrease_cash()  # Deduct bet amount immediately when starting round
        print(f"🎰 Started round with bet: {format_money(bet)} - Cash deducted immediately")

        # Keep picking until 3 blues (win) or 1 red (lose)
        while round_active and picks < max_picks:
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
                        
                        # Collect winnings
                        await simulate_click(Point(1581, 849), "COLLECT WINNINGS")
                        await test_increase_cash()
                        
                        # Reset betting strategy after win - back to minimum bet
                        tries = 0  # Reset tries counter
                        bet = round(0.1, 2)  # Reset bet to minimum
                        print(f"🎯 WIN! Bet reset to minimum: {format_money(bet)}")
                        
                        # Reset for next round
                        picks = 0
                        round_active = False
                        
                    else:
                        print(f"🎯 Got {picks} blue(s), need {max_picks - picks} more...")
                        
                elif color_result == "red":
                    print(f"🔴 Tile {tile_num} is RED - ROUND LOST!")
                    color_detected = True
                    
                    # Cash already deducted when round started, just update strategy
                    tries += 1
                    test_get_bet_from_mode_array()
                    print(f"💸 LOSS! Bet increased to: {format_money(bet)} (try #{tries})")
                    
                    # Calculate loss and check limits
                    loss = round(highest_cash - current_cash, 2)
                    if loss >= max_loss:
                        print("📉 Reached maximum loss!")
                        break
                    
                    # Reset picks and end round
                    picks = 0
                    round_active = False
                    
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
        test_log_state()
        await asyncio.sleep(0.5)
    
    print("\n🏆 === TEST COMPLETED ===")
    print(f"Final Results:")
    print(f"💰 Final Cash: {format_money(current_cash)}")
    print(f"📈 Highest Cash: {format_money(highest_cash)}")
    print(f"🏁 Rounds Completed: {rounds}")
    print(f"📉 Total Loss: {format_money(loss)}")
    print(f"🎯 Final Picks: {picks}")
    print(f"🔄 Final Tries: {tries}")

if __name__ == "__main__":
    print("🧪 Running safe test of game logic...")
    try:
        asyncio.run(test_main_game_logic())
        print("✅ Test completed successfully!")
    except KeyboardInterrupt:
        print("\n⚠️ Test stopped by user")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
