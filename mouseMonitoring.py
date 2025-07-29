import pyautogui
import time

try:
    while True:
        x, y = pyautogui.position()
        print(f"Mouse position: ({x}, {y})", end='\r')
        time.sleep(0.1)  # Update every 100ms
except KeyboardInterrupt:
    print("\nStopped monitoring")