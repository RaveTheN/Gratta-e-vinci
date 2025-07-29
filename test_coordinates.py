"""
Coordinate Testing Tool
Use this to verify and set up correct click positions for your game
"""
import pyautogui
import time
from PIL import Image, ImageDraw, ImageFont

def get_mouse_position():
    """Get current mouse position"""
    return pyautogui.position()

def take_screenshot_with_crosshair(x, y, filename="test_position.png"):
    """Take screenshot and draw crosshair at specified position"""
    screenshot = pyautogui.screenshot()
    draw = ImageDraw.Draw(screenshot)
    
    # Draw crosshair
    crosshair_size = 20
    # Horizontal line
    draw.line([(x-crosshair_size, y), (x+crosshair_size, y)], fill='red', width=3)
    # Vertical line  
    draw.line([(x, y-crosshair_size), (x, y+crosshair_size)], fill='red', width=3)
    
    # Draw coordinates text
    try:
        font = ImageFont.truetype("arial.ttf", 16)
    except:
        font = ImageFont.load_default()
    
    text = f"({x}, {y})"
    draw.text((x+25, y-25), text, fill='red', font=font)
    
    screenshot.save(filename)
    print(f"Screenshot saved as {filename}")

def test_color_at_position(x, y):
    """Test what color is at a specific position"""
    screenshot = pyautogui.screenshot()
    pixel_color = screenshot.getpixel((x, y))
    print(f"Color at ({x}, {y}): RGB{pixel_color}")
    return pixel_color

def interactive_position_tester():
    """Interactive tool to test positions"""
    print("🎯 Interactive Position Tester")
    print("Commands:")
    print("  'pos' - Get current mouse position")
    print("  'click X Y' - Test click at coordinates")
    print("  'color X Y' - Get color at coordinates") 
    print("  'screenshot X Y' - Take screenshot with crosshair")
    print("  'live' - Live mouse position tracking")
    print("  'quit' - Exit")
    
    while True:
        try:
            command = input("\n> ").strip().lower()
            
            if command == 'quit':
                break
                
            elif command == 'pos':
                x, y = get_mouse_position()
                print(f"Current mouse position: ({x}, {y})")
                
            elif command == 'live':
                print("Live tracking (press Ctrl+C to stop):")
                try:
                    while True:
                        x, y = get_mouse_position()
                        print(f"\rMouse: ({x:4d}, {y:4d})", end='', flush=True)
                        time.sleep(0.1)
                except KeyboardInterrupt:
                    print("\nLive tracking stopped")
                    
            elif command.startswith('click'):
                parts = command.split()
                if len(parts) == 3:
                    x, y = int(parts[1]), int(parts[2])
                    print(f"Simulating click at ({x}, {y})")
                    # Don't actually click, just test the position
                    take_screenshot_with_crosshair(x, y, f"click_test_{x}_{y}.png")
                else:
                    print("Usage: click X Y")
                    
            elif command.startswith('color'):
                parts = command.split()
                if len(parts) == 3:
                    x, y = int(parts[1]), int(parts[2])
                    test_color_at_position(x, y)
                else:
                    print("Usage: color X Y")
                    
            elif command.startswith('screenshot'):
                parts = command.split()
                if len(parts) == 3:
                    x, y = int(parts[1]), int(parts[2])
                    take_screenshot_with_crosshair(x, y)
                else:
                    print("Usage: screenshot X Y")
                    
            else:
                print("Unknown command. Type 'quit' to exit.")
                
        except ValueError:
            print("Invalid coordinates. Use numbers only.")
        except Exception as e:
            print(f"Error: {e}")

def test_game_positions():
    """Test all the positions defined in your game"""
    positions = {
        "play_collect": (1581, 849),
        "raise_bet": (1613, 780),
        "lower_bet": (1565, 780),
        "tile_1": (1581, 849),
        "tile_2": (1613, 780),
        "tile_3": (1565, 780),
    }
    
    print("🎮 Testing Game Positions")
    for name, (x, y) in positions.items():
        print(f"Testing {name} at ({x}, {y})")
        color = test_color_at_position(x, y)
        take_screenshot_with_crosshair(x, y, f"test_{name}.png")
        
        response = input(f"Is {name} position correct? (y/n/skip): ").lower()
        if response == 'n':
            print("Move your mouse to the correct position and press Enter...")
            input()
            new_x, new_y = get_mouse_position()
            print(f"New position for {name}: ({new_x}, {new_y})")
            print(f"Update your script: {name} = Point({new_x}, {new_y})")

if __name__ == "__main__":
    print("🔧 Coordinate Testing Tool")
    print("Choose testing mode:")
    print("1. Interactive position tester")
    print("2. Test predefined game positions")
    print("3. Quick mouse position check")
    
    try:
        choice = input("Enter choice (1-3): ").strip()
        
        if choice == "1":
            interactive_position_tester()
        elif choice == "2":
            test_game_positions()
        elif choice == "3":
            print("Move mouse to position and press Enter...")
            input()
            x, y = get_mouse_position()
            print(f"Position: ({x}, {y})")
            take_screenshot_with_crosshair(x, y)
        else:
            print("Invalid choice")
            
    except KeyboardInterrupt:
        print("\nTesting stopped by user")
    except Exception as e:
        print(f"Error: {e}")
