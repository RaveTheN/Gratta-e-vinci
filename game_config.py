"""Shared types, constants, and utilities for Gratta e Vinci."""


# --- Types ---

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Point({self.x}, {self.y})"


# --- Betting ---

BETTING_MODES = {
    "normal": [0.1, 0.2, 0.3, 0.5, 0.8, 1.4, 2.5, 4.5, 8.0, 14.0, 20.0],
    "medium": [0.1, 0.2, 0.3, 0.5, 0.9, 1.5, 3.0, 5.0, 9.0, 16.0, 20.0],
    "high": [0.2, 0.3, 0.6, 1.0, 1.8, 3.0, 5.0, 9.0, 16.0, 20.0],
    "safe": [0.1, 0.1, 0.2, 0.3, 0.5, 1.0, 1.8, 3.0, 5.0, 9.0, 16.0, 20.0],
}

BET_VALUES = [
    0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0,
    1.2, 1.4, 1.5, 1.6, 1.8, 2.0, 2.5, 3.0, 3.5, 4.0,
    4.5, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 12.0, 14.0, 16.0,
    18.0, 20.0, 25.0,
]

GRINDING_STEP = {"b": 20.0, "d": "high"}


# --- Win Conditions ---

WIN_MULTIPLIERS = {
    "low": {1: 1.1, 2: 1.3, 3: 1.5, 4: 1.7},
    "medium": {1: 1.3, 2: 1.8, 3: 2.4, 4: 3.6},
    "high": {1: 1.6, 2: 2.7, 3: 4.8, 4: 8.7},
}


# --- Colors ---

TARGET_BLUE = {"r": 1, "g": 108, "b": 238}
TARGET_RED = {"r": 200, "g": 13, "b": 1}
COLOR_TOLERANCE = 50


# --- Test Mode ---

TEST_MODE_BOARD_SIZE = 25
TEST_MODE_MINE_CONFIG = {"low": 3, "medium": 6, "high": 10}


# --- Utilities ---

def format_money(value):
    """Format a number to always show exactly 2 decimal places."""
    return f"{round(value, 2):.2f}"
