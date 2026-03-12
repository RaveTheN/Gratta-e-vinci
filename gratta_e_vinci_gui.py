"""
Gratta-e-Vinci Automation GUI
Standalone application with configurable settings and mouse coordinate display
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import asyncio
import pyautogui
import random
import time
from pynput import keyboard, mouse
import json
import os
import color_detector
import coordinate_manager
import game_engine
import settings_manager
from color_detector import ColorDetector
from coordinate_manager import CoordinateManager, CoordinateRecorder
from game_config import (
    Point,
    BETTING_MODES,
    WIN_MULTIPLIERS,
    BET_VALUES,
    TARGET_BLUE,
    TARGET_RED,
    COLOR_TOLERANCE,
    GRINDING_STEP,
    TEST_MODE_BOARD_SIZE,
    TEST_MODE_MINE_CONFIG,
    format_money,
)
from game_engine import GameEngine, TkAutomationAdapter
from settings_manager import SettingsManager

class GrattaEVinciGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Gratta-e-Vinci Automation v2.0")
        self.root.geometry("900x1000")
        self.root.resizable(True, True)
        self.settings_path = "gratta_settings.json"
        self.settings_manager = SettingsManager()
        self.coordinate_manager = CoordinateManager()
        
        # Initialize variables
        self.mouse_monitoring = False
        self.game_running = False
        self.escape_pressed = False
        self.stop_event = threading.Event()
        self.running_event = threading.Event()
        self.keyboard_listener = None
        
        # Game variables
        self.current_cash = 0
        self.highest_cash = 0
        self.lowest_cash = 0
        self.bet = 0.1
        self.highest_bet = 0.1
        self.picks = 0
        self.tries = 0
        self.rounds = 0
        self.loss = 0
        self.total_win = 0  # Add this line
        self.randoms = []
        self.grinding_active = False
        self.grinding_saved_balance = None
        self.current_difficulty = None  # Traccia la difficoltà attualmente impostata in gioco
        self.init_steps = [{"action": "set_bet_min"}]
        
        # Target colors (from game_config)
        self.target_blue = dict(TARGET_BLUE)
        self.target_red = dict(TARGET_RED)
        self.color_tolerance_var = tk.IntVar(value=COLOR_TOLERANCE)
        self.color_detector = ColorDetector(self.target_blue, self.target_red, self.color_tolerance_var.get())
        self.color_tolerance_var.trace_add("write", self._on_color_tolerance_changed)
        self.game_engine = GameEngine(self, TkAutomationAdapter(self, self.color_detector))
        
        # Tiles dictionary (will be configurable)
        self.tiles = {}
        
        # Betting modes - deep copy from shared constants
        self.betting_modes = {k: list(v) for k, v in BETTING_MODES.items()}

        # Custom betting mode: each step has bet (b), picks (p), difficulty (d)
        self.custom_mode = [
            {"b": 0.1, "p": 2, "d": "low"},
        ]

        # Valid bet values (from game_config)
        self.bet_values = list(BET_VALUES)

        # Pause configurabili
        self.sleep_play_or_collect_var = tk.DoubleVar(value=1.0)
        self.sleep_increase_bet_var = tk.DoubleVar(value=1.0)
        self.sleep_decrease_bet_var = tk.DoubleVar(value=1.0)
        self.sleep_decrease_bet_force_var = tk.DoubleVar(value=0.05)
        self.sleep_decrease_diff_force_var = tk.DoubleVar(value=0.05)
        self.sleep_set_difficulty_var = tk.DoubleVar(value=0.5)
        self.sleep_click_tile_var = tk.DoubleVar(value=1.0)
        self.sleep_after_play_var = tk.DoubleVar(value=1.0)
        self.sleep_after_tile_click_var = tk.DoubleVar(value=1.0)
        self.sleep_between_rounds_var = tk.DoubleVar(value=1.0)
        self.sleep_after_result_var = tk.DoubleVar(value=2.0)
        self.sleep_color_retry_var = tk.DoubleVar(value=1.0)
        self.sleep_init_raise_diff_var = tk.DoubleVar(value=0.4)
        self.sleep_init_lower_diff_var = tk.DoubleVar(value=0.4)
        self.sleep_init_click_var = tk.DoubleVar(value=0.3)
        
        # Bulk Test variables
        self.bulk_n_runs_var = tk.IntVar(value=100)
        self.bulk_show_logs_var = tk.BooleanVar(value=True)
        self.bulk_test_running = False
        self.bulk_test_stop = False
        self._bulk_results = None

        # Bulk advanced params (local overrides, initialized from game_config defaults)
        self.bulk_betting_modes = {k: list(v) for k, v in BETTING_MODES.items()}
        self.bulk_bet_values = list(BET_VALUES)
        self.bulk_win_multiplier_vars = {
            d: {p: tk.DoubleVar(value=WIN_MULTIPLIERS[d][p]) for p in [1, 2, 3, 4]}
            for d in ["low", "medium", "high"]
        }
        self.bulk_mine_config_vars = {
            d: tk.IntVar(value=TEST_MODE_MINE_CONFIG[d]) for d in ["low", "medium", "high"]
        }

        # Create GUI
        self.create_widgets()
        self.on_load_settings()

        # Start mouse coordinate monitoring
        self.start_mouse_monitoring()

    def get_win_multiplier(self, difficulty, picks):
        """Resolve win multiplier from difficulty and picks."""
        difficulty_key = str(difficulty).lower()
        if difficulty_key not in WIN_MULTIPLIERS:
            raise ValueError(f"Invalid difficulty '{difficulty}'")
        if picks not in WIN_MULTIPLIERS[difficulty_key]:
            raise ValueError(f"Invalid picks '{picks}' for difficulty '{difficulty_key}'")
        return round(WIN_MULTIPLIERS[difficulty_key][picks], 2)
    
    def create_widgets(self):
        # Main notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Settings Tab
        settings_frame = ttk.Frame(notebook)
        notebook.add(settings_frame, text="Settings")
        self.create_settings_tab(settings_frame)
        
        # Coordinates Tab
        coordinates_frame = ttk.Frame(notebook)
        notebook.add(coordinates_frame, text="Coordinates")
        self.create_coordinates_tab(coordinates_frame)
        
        # Betting Modes Tab
        betting_frame = ttk.Frame(notebook)
        notebook.add(betting_frame, text="Betting Modes")
        self.create_betting_modes_tab(betting_frame)

        # Initialization Steps Tab
        init_frame = ttk.Frame(notebook)
        notebook.add(init_frame, text="Inizializzazione")
        self.create_init_steps_tab(init_frame)

        # Game Control Tab
        control_frame = ttk.Frame(notebook)
        notebook.add(control_frame, text="Game Control")
        self.create_control_tab(control_frame)
        
        # Statistics Tab
        stats_frame = ttk.Frame(notebook)
        notebook.add(stats_frame, text="Statistics")
        self.create_stats_tab(stats_frame)

        # Bulk Test Tab
        bulk_frame = ttk.Frame(notebook)
        notebook.add(bulk_frame, text="Bulk Test")
        self.create_bulk_test_tab(bulk_frame)

        # Pauses Tab
        pauses_frame = ttk.Frame(notebook)
        notebook.add(pauses_frame, text="Pause")
        self.create_pauses_tab(pauses_frame)
    
    def create_settings_tab(self, parent):
        # Mouse coordinates display in settings
        coord_frame = ttk.LabelFrame(parent, text="Mouse Coordinates", padding=10)
        coord_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.settings_coord_label = ttk.Label(coord_frame, text="Mouse Position: (0, 0)", font=("Courier", 12))
        self.settings_coord_label.pack(pady=5)
        
        # Game Settings Frame
        game_frame = ttk.LabelFrame(parent, text="Game Settings", padding=10)
        game_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Starting Cash
        ttk.Label(game_frame, text="Starting Cash:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.starting_cash_var = tk.DoubleVar(value=2001.50)
        ttk.Entry(game_frame, textvariable=self.starting_cash_var, width=15).grid(row=0, column=1, padx=5, pady=2)
        
        # Target Win
        ttk.Label(game_frame, text="Target Win:").grid(row=0, column=2, sticky=tk.W, pady=2)
        self.target_win_var = tk.DoubleVar(value=2100.0)
        ttk.Entry(game_frame, textvariable=self.target_win_var, width=15).grid(row=0, column=3, padx=5, pady=2)
        
        # Max Loss
        ttk.Label(game_frame, text="Max Loss:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.max_loss_var = tk.DoubleVar(value=10.0)
        ttk.Entry(game_frame, textvariable=self.max_loss_var, width=15).grid(row=1, column=1, padx=5, pady=2)
        
        # Max Rounds
        ttk.Label(game_frame, text="Max Rounds:").grid(row=1, column=2, sticky=tk.W, pady=2)
        self.max_rounds_var = tk.IntVar(value=100)
        ttk.Entry(game_frame, textvariable=self.max_rounds_var, width=15).grid(row=1, column=3, padx=5, pady=2)
        
        # Max Picks
        ttk.Label(game_frame, text="Max Picks (1-4):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.max_picks_var = tk.IntVar(value=3)
        self.max_picks_spinbox = ttk.Spinbox(game_frame, from_=1, to=4, textvariable=self.max_picks_var, width=13)
        self.max_picks_spinbox.grid(row=2, column=1, padx=5, pady=2)

        # Betting Mode
        ttk.Label(game_frame, text="Betting Mode:").grid(row=2, column=2, sticky=tk.W, pady=2)
        self.mode_var = tk.StringVar(value="normal")
        self.mode_var.trace_add("write", self._on_mode_var_changed)
        mode_combo = ttk.Combobox(game_frame, textvariable=self.mode_var, width=12, state="readonly")
        mode_combo['values'] = ("normal", "medium", "high", "safe", "custom")
        mode_combo.grid(row=2, column=3, padx=5, pady=2)
        mode_combo.bind('<<ComboboxSelected>>', lambda e: self._on_mode_changed_settings())

        # Difficulty (used for standard modes and as default for custom mode steps)
        ttk.Label(game_frame, text="Difficulty:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.difficulty_var = tk.StringVar(value="low")
        self.diff_combo = ttk.Combobox(game_frame, textvariable=self.difficulty_var, width=12, state="readonly")
        self.diff_combo['values'] = ("low", "medium", "high")
        self.diff_combo.grid(row=3, column=1, padx=5, pady=2)

        # Color tolerance
        ttk.Label(game_frame, text="Color Tolerance:").grid(row=3, column=2, sticky=tk.W, pady=2)
        ttk.Entry(game_frame, textvariable=self.color_tolerance_var, width=12).grid(row=3, column=3, padx=5, pady=2)

        # Wait between rounds
        self.wait_selected_var = tk.BooleanVar()
        ttk.Checkbutton(game_frame, text="Random wait between rounds (1-6 min)",
                       variable=self.wait_selected_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=2)
        
        # Grinding Mode
        self.grinding_mode_var = tk.BooleanVar(value=False)
        self.grinding_range_var = tk.DoubleVar(value=0.5)
        self.grinding_p_random_var = tk.BooleanVar(value=False)

        ttk.Checkbutton(game_frame, text="Grinding mode",
                        variable=self.grinding_mode_var,
                        command=self._on_grinding_toggle).grid(row=4, column=2, sticky=tk.W, pady=2)
        ttk.Label(game_frame, text="Range:").grid(row=4, column=3, sticky=tk.E, padx=(10, 2))
        self.grinding_range_entry = ttk.Entry(game_frame, textvariable=self.grinding_range_var, width=6)
        self.grinding_range_entry.grid(row=4, column=4, sticky=tk.W, pady=2)
        self.grinding_p_random_cb = ttk.Checkbutton(game_frame, text="p random (fallback)",
                                                     variable=self.grinding_p_random_var)
        self.grinding_p_random_cb.grid(row=5, column=2, columnspan=2, sticky=tk.W, pady=2)

        # Betting Mode Editor Button
        self.settings_mode_editor_button = ttk.Button(game_frame, text="Edit Modes", command=self.open_selected_mode_editor)
        self.settings_mode_editor_button.grid(row=6, column=0, columnspan=2, padx=5, pady=2, sticky=tk.W)
        
        # Control Points Frame
        control_frame = ttk.LabelFrame(parent, text="Control Points", padding=10)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Play/Collect Button
        ttk.Label(control_frame, text="Play/Collect:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.play_x_var = tk.IntVar(value=2196)
        self.play_y_var = tk.IntVar(value=1616)
        ttk.Entry(control_frame, textvariable=self.play_x_var, width=8).grid(row=0, column=1, padx=2, pady=2)
        ttk.Entry(control_frame, textvariable=self.play_y_var, width=8).grid(row=0, column=2, padx=2, pady=2)
        
        # Raise Bet Button
        ttk.Label(control_frame, text="Raise Bet:").grid(row=0, column=3, sticky=tk.W, pady=2)
        self.raise_x_var = tk.IntVar(value=1900)
        self.raise_y_var = tk.IntVar(value=1740)
        ttk.Entry(control_frame, textvariable=self.raise_x_var, width=8).grid(row=0, column=4, padx=2, pady=2)
        ttk.Entry(control_frame, textvariable=self.raise_y_var, width=8).grid(row=0, column=5, padx=2, pady=2)
        
        # Lower Bet Button
        ttk.Label(control_frame, text="Lower Bet:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.lower_x_var = tk.IntVar(value=1519)
        self.lower_y_var = tk.IntVar(value=1740)
        ttk.Entry(control_frame, textvariable=self.lower_x_var, width=8).grid(row=1, column=1, padx=2, pady=2)
        ttk.Entry(control_frame, textvariable=self.lower_y_var, width=8).grid(row=1, column=2, padx=2, pady=2)

        # Raise Difficulty Button
        ttk.Label(control_frame, text="Raise Difficulty:").grid(row=1, column=3, sticky=tk.W, pady=2)
        self.raise_diff_x_var = tk.IntVar(value=0)
        self.raise_diff_y_var = tk.IntVar(value=0)
        ttk.Entry(control_frame, textvariable=self.raise_diff_x_var, width=8).grid(row=1, column=4, padx=2, pady=2)
        ttk.Entry(control_frame, textvariable=self.raise_diff_y_var, width=8).grid(row=1, column=5, padx=2, pady=2)

        # Lower Difficulty Button
        ttk.Label(control_frame, text="Lower Difficulty:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.lower_diff_x_var = tk.IntVar(value=0)
        self.lower_diff_y_var = tk.IntVar(value=0)
        ttk.Entry(control_frame, textvariable=self.lower_diff_x_var, width=8).grid(row=2, column=1, padx=2, pady=2)
        ttk.Entry(control_frame, textvariable=self.lower_diff_y_var, width=8).grid(row=2, column=2, padx=2, pady=2)

        # Buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=5, pady=10)
        
        ttk.Button(button_frame, text="Save Settings", command=self.on_save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Load Settings", command=self.on_load_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Reset to Defaults", command=self.reset_settings).pack(side=tk.LEFT, padx=5)
    
    def _on_mode_changed_settings(self):
        """Disable max_picks and difficulty widgets when custom mode is selected."""
        is_custom = self.mode_var.get() == "custom"
        self.max_picks_spinbox.config(state="disabled" if is_custom else "normal")
        self.diff_combo.config(state="disabled" if is_custom else "readonly")
        if hasattr(self, "settings_mode_editor_button"):
            btn_label = "Edit Custom Sequence" if is_custom else "Edit Modes"
            self.settings_mode_editor_button.config(text=btn_label)

    def _on_grinding_toggle(self):
        """Enable/disable grinding sub-controls based on checkbox state."""
        state = tk.NORMAL if self.grinding_mode_var.get() else tk.DISABLED
        self.grinding_range_entry.config(state=state)
        self.grinding_p_random_cb.config(state=state)

    def _on_color_tolerance_changed(self, *_):
        try:
            tolerance = max(1, min(255, int(self.color_tolerance_var.get())))
            if tolerance != int(self.color_tolerance_var.get()):
                self.color_tolerance_var.set(tolerance)
                return
            self.color_detector.tolerance = tolerance
        except Exception:
            return

    def get_grinding_picks(self):
        """Return the minimum p (1-3) that would recover grinding_saved_balance, or fallback."""
        b = 20.0
        target = self.grinding_saved_balance if self.grinding_saved_balance is not None else 0
        for p in [1, 2, 3]:
            projected = self.current_cash + (b * WIN_MULTIPLIERS["high"][p])
            if projected >= target:
                return p
        # None of p=1,2,3 sufficient
        if self.grinding_p_random_var.get():
            return random.randint(1, 3)
        return 3

    def _get_min_bet_for_selected_mode(self):
        """Return the first bet for the active strategy."""
        selected_mode_name = self.mode_var.get()
        if selected_mode_name == "custom" and self.custom_mode:
            return round(self.custom_mode[0]["b"], 2)
        if selected_mode_name in self.betting_modes and self.betting_modes[selected_mode_name]:
            return round(self.betting_modes[selected_mode_name][0], 2)
        return 0.1

    def _get_target_bet_for_try(self, tries=None, selected_mode_name=None):
        """Resolve the bet for a given try index."""
        if tries is None:
            tries = self.tries
        if selected_mode_name is None:
            selected_mode_name = self.mode_var.get()

        if selected_mode_name == "custom" and self.custom_mode:
            step_idx = min(tries, len(self.custom_mode) - 1)
            return round(self.custom_mode[step_idx]["b"], 2)
        if selected_mode_name in self.betting_modes and self.betting_modes[selected_mode_name]:
            mode_array = self.betting_modes[selected_mode_name]
            step_idx = min(tries, len(mode_array) - 1)
            return round(mode_array[step_idx], 2)
        return 0.1

    def _get_round_config_for_strategy(self):
        """Resolve picks, difficulty and bet for the current round."""
        selected_mode_name = self.mode_var.get()
        grinding_enabled = bool(self.grinding_mode_var.get())
        step_idx = None
        max_step_idx = None

        if self.grinding_active:
            max_picks = self.get_grinding_picks()
            round_difficulty = GRINDING_STEP["d"]
            target_bet = round(GRINDING_STEP["b"], 2)
            strategy_source = "grinding"
        elif selected_mode_name == "custom" and self.custom_mode:
            step_idx = min(self.tries, len(self.custom_mode) - 1)
            max_step_idx = len(self.custom_mode) - 1
            step_data = self.custom_mode[step_idx]
            max_picks = step_data["p"]
            round_difficulty = step_data["d"]
            target_bet = round(step_data["b"], 2)
            strategy_source = "custom"
        else:
            max_picks = self.max_picks_var.get()
            round_difficulty = self.difficulty_var.get()
            target_bet = self._get_target_bet_for_try(self.tries, selected_mode_name)
            if selected_mode_name in self.betting_modes and self.betting_modes[selected_mode_name]:
                step_idx = min(self.tries, len(self.betting_modes[selected_mode_name]) - 1)
                max_step_idx = len(self.betting_modes[selected_mode_name]) - 1
            strategy_source = "standard"

        return {
            "selected_mode_name": selected_mode_name,
            "strategy_source": strategy_source,
            "grinding_enabled": grinding_enabled,
            "max_picks": max_picks,
            "round_difficulty": round_difficulty,
            "target_bet": target_bet,
            "step_idx": step_idx,
            "max_step_idx": max_step_idx,
            "mine_count": TEST_MODE_MINE_CONFIG[round_difficulty],
            "multiplier": self.get_win_multiplier(round_difficulty, max_picks),
        }

    def _simulate_test_board(self, round_difficulty, max_picks):
        """Simulate a 5x5 board and open tiles without replacement."""
        mine_count = TEST_MODE_MINE_CONFIG[round_difficulty]
        board = ["mine"] * mine_count + ["coin"] * (TEST_MODE_BOARD_SIZE - mine_count)
        random.shuffle(board)

        tile_map = {tile_num: board[tile_num - 1] for tile_num in range(1, TEST_MODE_BOARD_SIZE + 1)}
        available_tiles = list(tile_map.keys())
        random.shuffle(available_tiles)

        opened_tiles = []
        coins_found = 0
        hit_mine = False

        for tile_num in available_tiles[:max_picks]:
            outcome = tile_map[tile_num]
            opened_tiles.append({"tile": tile_num, "outcome": outcome})
            if outcome == "mine":
                hit_mine = True
                break
            coins_found += 1

        return {
            "mine_count": mine_count,
            "opened_tiles": opened_tiles,
            "coins_found": coins_found,
            "hit_mine": hit_mine,
        }

    def _apply_test_win(self, round_config):
        """Apply the result of a winning simulated round."""
        win_amount = round(self.bet * round_config["multiplier"], 2)
        self.current_cash = round(self.current_cash + win_amount, 2)
        self.total_win = round(self.total_win + win_amount, 2)
        self.log_message(
            f"[WIN] 💰 Won {self.format_money(win_amount)}! New balance: {self.format_money(self.current_cash)}"
        )

        if self.current_cash > self.highest_cash:
            self.highest_cash = round(self.current_cash, 2)

        if self.grinding_active:
            if self.grinding_saved_balance is not None and self.current_cash >= self.grinding_saved_balance:
                self.grinding_active = False
                self.tries = 0
                self.picks = 0
                self.bet = self._get_min_bet_for_selected_mode()
                self.log_message(
                    f"[GRIND] Completed: balance recovered ({self.format_money(self.current_cash)} >= "
                    f"{self.format_money(self.grinding_saved_balance)}). Bet reset to minimum."
                )
            else:
                self.bet = round(GRINDING_STEP["b"], 2)
                target_text = self.format_money(self.grinding_saved_balance or 0)
                self.log_message(
                    f"[GRIND] Current balance {self.format_money(self.current_cash)} "
                    f"(target {target_text}), staying on fixed grinding step."
                )
        else:
            self.tries = 0
            self.picks = 0
            self.bet = self._get_min_bet_for_selected_mode()
            self.log_message(f"[WIN] Bet reset to minimum: {self.format_money(self.bet)}")

    def _apply_test_loss(self, round_config):
        """Apply the result of a losing simulated round."""
        step_idx = round_config["step_idx"]
        max_step_idx = round_config["max_step_idx"]
        grinding_enabled = round_config["grinding_enabled"]

        if grinding_enabled and not self.grinding_active and step_idx == 0:
            acceptable_range = self.grinding_range_var.get()
            self.grinding_saved_balance = round(self.highest_cash - acceptable_range, 2)

        self.tries += 1
        self.picks = 0

        reached_top_step = (
            step_idx is not None and
            max_step_idx is not None and
            step_idx >= max_step_idx
        )
        if (
            grinding_enabled and
            not self.grinding_active and
            reached_top_step and
            round(self.bet, 2) == round(GRINDING_STEP["b"], 2) and
            self.grinding_saved_balance is not None
        ):
            self.grinding_active = True
            self.log_message(
                f"[GRIND] Activated after last-step loss: repeating b={GRINDING_STEP['b']:.1f}, "
                f"p={self.max_picks_var.get()}, d={GRINDING_STEP['d']} until balance >= "
                f"{self.format_money(self.grinding_saved_balance)}"
            )

        if self.grinding_active:
            self.bet = round(GRINDING_STEP["b"], 2)
        else:
            self.bet = self._get_target_bet_for_try(self.tries, round_config["selected_mode_name"])

        if self.bet > self.highest_bet:
            self.highest_bet = round(self.bet, 2)

        self.log_message(f"[LOSS] Bet updated to: {self.format_money(self.bet)} (try #{self.tries})")

    def _finish_test_mode(self, stop_reason):
        """Close test mode without marking it as a forced stop."""
        self.game_running = False
        self.root.after(0, lambda: self.start_button.config(state=tk.NORMAL))
        self.root.after(0, lambda: self.stop_button.config(state=tk.DISABLED))
        self.root.after(0, self.update_stats_display)

        max_rounds = self.max_rounds_var.get()
        progress = 100 if max_rounds <= 0 else min(100, (self.rounds / max_rounds) * 100)
        self.root.after(0, lambda value=progress: self.progress_var.set(value))
        self.root.after(0, lambda: self.progress_label.config(text=f"TEST MODE ended: {stop_reason}"))

        self.log_message("\n=== TEST MODE RESULTS ===")
        self.log_message(f"🛑 Stop reason: {stop_reason}")
        self.log_message(f"💰 Final cash: {self.format_money(self.current_cash)}")
        self.log_message(f"📈 Highest cash: {self.format_money(self.highest_cash)}")
        self.log_message(f"📉 Lowest cash: {self.format_money(self.lowest_cash)}")
        self.log_message(f"🔝 Highest bet: {self.format_money(self.highest_bet)}")
        self.log_message(f"📉 Total loss: {self.format_money(self.loss)}")
        self.log_message(f"🏁 Rounds played: {self.rounds}")

        profit_loss = round(self.current_cash - self.starting_cash_var.get(), 2)
        if profit_loss > 0:
            self.log_message(f"✅ Net profit: +{self.format_money(profit_loss)}")
        else:
            self.log_message(f"❌ Net loss: {self.format_money(profit_loss)}")

        self.log_message("🧪 Strategy simulation completed.")

    def _on_mode_var_changed(self, *_):
        """React to mode changes regardless of where they originate."""
        self._on_mode_changed_settings()
        if hasattr(self, "betting_preview_text"):
            self.update_betting_preview()

    def open_selected_mode_editor(self):
        """Open the editor for the currently selected betting mode."""
        if self.mode_var.get() == "custom":
            self.open_custom_mode_editor()
        else:
            self.open_betting_mode_editor()

    def create_coordinates_tab(self, parent):
        # Mouse coordinates display
        coord_frame = ttk.LabelFrame(parent, text="Mouse Coordinates", padding=10)
        coord_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.coord_label = ttk.Label(coord_frame, text="Mouse Position: (0, 0)", font=("Courier", 12))
        self.coord_label.pack(pady=5)
        
        # Tile positions frame
        tile_frame = ttk.LabelFrame(parent, text="Tile Positions (Smart Grid Setup)", padding=15)
        tile_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Instructions
        instructions = ttk.Label(tile_frame, text="Enter key coordinates - other tiles will be auto-calculated:", 
                                font=("TkDefaultFont", 10, "bold"), foreground="blue")
        instructions.pack(pady=(0, 15))
        
        # Create tile position entries for specific tiles only
        self.tile_vars = {}
        
        # Main container for input fields
        input_container = ttk.Frame(tile_frame)
        input_container.pack(fill=tk.X, pady=(0, 15))
        
        # Configure grid weights for responsive layout
        for i in range(3):
            input_container.grid_columnconfigure(i, weight=1)
        
        # Row 1: Tile 1 (X and Y coordinates)
        tile1_frame = ttk.LabelFrame(input_container, text="🎯 Tile 1 (Reference Point)", padding=10)
        tile1_frame.grid(row=0, column=0, columnspan=3, sticky=tk.EW, pady=(0, 10), padx=5)
        
        tile1_coords = ttk.Frame(tile1_frame)
        tile1_coords.pack()
        
        ttk.Label(tile1_coords, text="X:", font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        x1_var = tk.IntVar(value=1640)
        ttk.Entry(tile1_coords, textvariable=x1_var, width=8, font=("TkDefaultFont", 10)).pack(side=tk.LEFT, padx=(0, 15))
        
        ttk.Label(tile1_coords, text="Y:", font=("TkDefaultFont", 10, "bold")).pack(side=tk.LEFT, padx=(0, 5))
        y1_var = tk.IntVar(value=740)
        ttk.Entry(tile1_coords, textvariable=y1_var, width=8, font=("TkDefaultFont", 10)).pack(side=tk.LEFT)
        
        self.tile_vars[1] = (x1_var, y1_var)
        
        # Row 2: Top row X coordinates (tiles 2, 3, 4, 5)
        top_row_frame = ttk.LabelFrame(input_container, text="📐 Top Row X Coordinates", padding=10)
        top_row_frame.grid(row=1, column=0, columnspan=3, sticky=tk.EW, pady=(0, 10), padx=5)
        
        top_row_coords = ttk.Frame(top_row_frame)
        top_row_coords.pack()
        
        # Configure equal spacing for top row entries
        for i in range(4):
            top_row_coords.grid_columnconfigure(i, weight=1)
        
        x_vars_top = []
        for i, tile_num in enumerate([2, 3, 4, 5]):
            tile_container = ttk.Frame(top_row_coords)
            tile_container.grid(row=0, column=i, padx=10, pady=5)
            
            ttk.Label(tile_container, text=f"Tile {tile_num}:", font=("TkDefaultFont", 9, "bold")).pack()
            x_var = tk.IntVar(value=1640 + i * 170 + 170)  # Start from tile 2 position
            ttk.Entry(tile_container, textvariable=x_var, width=8, font=("TkDefaultFont", 9)).pack(pady=(2, 0))
            
            # Store x coordinate for tiles 2-5, y will be same as tile 1
            self.tile_vars[tile_num] = (x_var, y1_var)  # Share Y with tile 1
            x_vars_top.append(x_var)
        
        # Row 3: Left column Y coordinates (tiles 6, 11, 16, 21)
        left_col_frame = ttk.LabelFrame(input_container, text="📏 Left Column Y Coordinates", padding=10)
        left_col_frame.grid(row=2, column=0, columnspan=3, sticky=tk.EW, pady=(0, 10), padx=5)
        
        left_col_coords = ttk.Frame(left_col_frame)
        left_col_coords.pack()
        
        # Configure equal spacing for left column entries
        for i in range(4):
            left_col_coords.grid_columnconfigure(i, weight=1)
        
        y_vars_left = []
        for i, tile_num in enumerate([6, 11, 16, 21]):
            tile_container = ttk.Frame(left_col_coords)
            tile_container.grid(row=0, column=i, padx=10, pady=5)
            
            ttk.Label(tile_container, text=f"Tile {tile_num}:", font=("TkDefaultFont", 9, "bold")).pack()
            y_var = tk.IntVar(value=740 + (i + 1) * 128)  # Start from tile 6 position
            ttk.Entry(tile_container, textvariable=y_var, width=8, font=("TkDefaultFont", 9)).pack(pady=(2, 0))
            
            # Store y coordinate for tiles 6,11,16,21, x will be same as tile 1
            self.tile_vars[tile_num] = (x1_var, y_var)  # Share X with tile 1
            y_vars_left.append(y_var)
        
        # Auto-calculate and store all 25 tiles
        def update_all_tiles():
            """Update all 25 tile positions based on the input coordinates"""
            try:
                self.coordinate_manager.populate_tile_vars(
                    self.tile_vars,
                    x1_var.get(),
                    y1_var.get(),
                    x_vars_top,
                    y_vars_left,
                )
            except Exception as e:
                print(f"Error in update_all_tiles: {e}")

        self.update_all_tiles = update_all_tiles
        
        # Bind update function to coordinate changes
        def on_coordinate_change(*args):
            self.root.after_idle(self.update_all_tiles)
        
        # Bind all coordinate variables to the update function
        x1_var.trace('w', on_coordinate_change)
        y1_var.trace('w', on_coordinate_change)
        for var in x_vars_top:
            var.trace('w', on_coordinate_change)
        for var in y_vars_left:
            var.trace('w', on_coordinate_change)
        
        # Initial calculation
        self.update_all_tiles()
        
        # Preview frame to show calculated coordinates
        preview_frame = ttk.LabelFrame(tile_frame, text="📋 Calculated Grid Preview", padding=10)
        preview_frame.pack(fill=tk.X, pady=(15, 0))
        
        # Create text widget for preview
        self.tile_preview_text = scrolledtext.ScrolledText(preview_frame, height=8, width=80, state=tk.DISABLED)
        self.tile_preview_text.pack(fill=tk.X, pady=(5, 0))
        
        def update_preview():
            """Update the tile preview display"""
            try:
                preview_text = self.coordinate_manager.build_preview_text(self.tile_vars)
                # Update the preview
                self.tile_preview_text.config(state=tk.NORMAL)
                self.tile_preview_text.delete(1.0, tk.END)
                self.tile_preview_text.insert(tk.END, preview_text)
                self.tile_preview_text.config(state=tk.DISABLED)
            except Exception as e:
                self.log_message(f"[WARN] Coordinate preview update failed: {e}")
        
        # Bind preview updates to coordinate changes
        def on_preview_update(*args):
            self.root.after_idle(update_preview)
        
        x1_var.trace('w', on_preview_update)
        y1_var.trace('w', on_preview_update)
        for var in x_vars_top:
            var.trace('w', on_preview_update)
        for var in y_vars_left:
            var.trace('w', on_preview_update)
        
        # Initial preview
        self.root.after(100, update_preview)
        
        # Quick setup buttons
        quick_frame = ttk.Frame(tile_frame)  # Change from coords_main_frame to tile_frame
        quick_frame.pack(fill=tk.X, pady=(10, 0))
        
        tk.Button(
            quick_frame,
            text="Record Coordinates",
            command=lambda: CoordinateRecorder(self).start(),
            bg="#2196F3",
            fg="white",
            font=("Arial", 10, "bold"),
        ).pack(side=tk.LEFT, padx=5)
        ttk.Button(quick_frame, text="🔄 Reset to Default Grid", command=self.reset_tile_grid).pack(side=tk.LEFT, padx=5)
        ttk.Button(quick_frame, text="🎯 Test Click Tile 1", command=lambda: self.test_click_tile(1)).pack(side=tk.LEFT, padx=5)
        ttk.Button(quick_frame, text="📋 Show All Coordinates", command=self.show_all_coordinates).pack(side=tk.LEFT, padx=5)
    
    def reset_tile_grid(self):
        """Reset tile grid to default coordinates"""
        if hasattr(self, 'tile_vars') and self.tile_vars:
            # Reset tile 1
            if 1 in self.tile_vars:
                self.tile_vars[1][0].set(1640)  # X
                self.tile_vars[1][1].set(740)   # Y
            
            # Reset top row X coordinates (tiles 2-5)
            default_x_values = [1810, 1980, 2150, 2320]  # 170px spacing
            for i, tile_num in enumerate([2, 3, 4, 5]):
                if tile_num in self.tile_vars:
                    self.tile_vars[tile_num][0].set(default_x_values[i])
            
            # Reset left column Y coordinates (tiles 6, 11, 16, 21)
            default_y_values = [868, 996, 1124, 1252]  # 128px spacing
            for i, tile_num in enumerate([6, 11, 16, 21]):
                if tile_num in self.tile_vars:
                    self.tile_vars[tile_num][1].set(default_y_values[i])
        
        messagebox.showinfo("Reset", "Tile grid reset to default coordinates!")

    def show_all_coordinates(self):
        """Show all 25 tile coordinates in a popup"""
        coords_window = tk.Toplevel(self.root)
        coords_window.title("All Tile Coordinates")
        coords_window.geometry("600x500")
        coords_window.resizable(True, True)
        
        # Make window modal
        coords_window.transient(self.root)
        coords_window.grab_set()
        
        # Create text widget
        text_frame = ttk.Frame(coords_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        coords_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD)
        coords_text.pack(fill=tk.BOTH, expand=True)
        
        # Generate coordinates display
        coords_display = "ALL TILE COORDINATES (5x5 Grid)\n"
        coords_display += "=" * 40 + "\n\n"
        
        for row in range(5):
            coords_display += f"Row {row + 1}:\n"
            for col in range(5):
                tile_num = row * 5 + col + 1
                if tile_num in self.tile_vars:
                    x = self.tile_vars[tile_num][0].get()
                    y = self.tile_vars[tile_num][1].get()
                    coords_display += f"  Tile {tile_num:2d}: ({x:4d}, {y:4d})\n"
                else:
                    coords_display += f"  Tile {tile_num:2d}: (Not set)\n"
            coords_display += "\n"
        
        coords_display += "Input Method Summary:\n"
        coords_display += "-" * 25 + "\n"
        coords_display += "• Tile 1: Both X and Y coordinates (reference point)\n"
        coords_display += "• Tiles 2-5: Only X coordinates (Y shared with Tile 1)\n"
        coords_display += "• Tiles 6,11,16,21: Only Y coordinates (X shared with Tile 1)\n"
        coords_display += "• All other tiles: Auto-calculated from grid pattern\n"
        
        coords_text.insert(tk.END, coords_display)
        coords_text.config(state=tk.DISABLED)
        
        # Close button
        ttk.Button(coords_window, text="Close", command=coords_window.destroy).pack(pady=10)
    
    def create_betting_modes_tab(self, parent):
        # Create main container directly without scrollable canvas for better responsiveness
        main_container = ttk.Frame(parent)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Header frame
        header_frame = ttk.Frame(main_container)
        header_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(header_frame, text="Betting Mode Configuration", font=("TkDefaultFont", 12, "bold")).pack()
        ttk.Label(header_frame, text="Customize betting strategies for different risk levels", font=("TkDefaultFont", 9)).pack(pady=(0, 10))
        
        # Current mode selection frame
        selection_frame = ttk.LabelFrame(main_container, text="Current Mode Selection", padding=10)
        selection_frame.pack(fill=tk.X, pady=(0, 5))
        
        mode_select_frame = ttk.Frame(selection_frame)
        mode_select_frame.pack(fill=tk.X)
        
        ttk.Label(mode_select_frame, text="Active Betting Mode:").pack(side=tk.LEFT, padx=(0, 10))
        
        mode_combo = ttk.Combobox(mode_select_frame, textvariable=self.mode_var, width=15, state="readonly")
        mode_combo['values'] = ("normal", "medium", "high", "safe", "custom")
        mode_combo.pack(side=tk.LEFT, padx=(0, 10))
        mode_combo.bind('<<ComboboxSelected>>', lambda e: (self.update_betting_preview(), self._on_mode_changed_settings()))
        
        ttk.Button(mode_select_frame, text="🔄 Refresh Preview", command=self.update_betting_preview).pack(side=tk.LEFT, padx=5)
        
        # Preview frame
        preview_frame = ttk.LabelFrame(main_container, text="Current Mode Preview", padding=10)
        preview_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        # Create text widget for preview
        self.betting_preview_text = scrolledtext.ScrolledText(preview_frame, height=12, width=80, state=tk.DISABLED)
        self.betting_preview_text.pack(fill=tk.BOTH, expand=True)
        
        # Action buttons frame with better layout
        action_frame = ttk.Frame(main_container)
        action_frame.pack(fill=tk.X, pady=(5, 0))
        
        # Configure button grid for responsive layout
        action_frame.grid_columnconfigure(0, weight=1)
        action_frame.grid_columnconfigure(1, weight=1)
        action_frame.grid_columnconfigure(2, weight=1)
        action_frame.grid_columnconfigure(3, weight=1)
        action_frame.grid_columnconfigure(4, weight=1)
        
        # Top row buttons
        ttk.Button(action_frame, text="✏️ Edit Selected Mode", command=self.open_selected_mode_editor).grid(row=0, column=0, padx=2, pady=2, sticky=tk.EW)
        ttk.Button(action_frame, text="📊 Analyze Modes", command=self.analyze_betting_modes).grid(row=0, column=1, padx=2, pady=2, sticky=tk.EW)
        ttk.Button(action_frame, text="🔄 Reset to Defaults", command=self.reset_betting_modes).grid(row=0, column=2, padx=2, pady=2, sticky=tk.EW)
        
        # Bottom row buttons
        ttk.Button(action_frame, text="📤 Export Modes", command=self.export_betting_modes).grid(row=1, column=0, padx=2, pady=2, sticky=tk.EW)
        ttk.Button(action_frame, text="📥 Import Modes", command=self.import_betting_modes).grid(row=1, column=1, padx=2, pady=2, sticky=tk.EW)
        ttk.Button(action_frame, text="🛠️ Edit Custom Mode", command=self.open_custom_mode_editor).grid(row=1, column=2, padx=2, pady=2, sticky=tk.EW)

        # Initial preview update
        self.root.after(100, self.update_betting_preview)
    
    def update_betting_preview(self):
        """Update the betting mode preview"""
        selected_mode = self.mode_var.get()

        if selected_mode == "custom":
            preview_text = "Mode: Custom\n"
            preview_text += f"Number of steps: {len(self.custom_mode)}\n\n"
            preview_text += "Step progression:\n"
            preview_text += "-" * 55 + "\n"
            cumulative_risk = 0.0
            for i, step in enumerate(self.custom_mode):
                cumulative_risk = round(cumulative_risk + step["b"], 2)
                preview_text += (
                    f"Step #{i+1:2d}: Bet={self.format_money(step['b']):>8s}  "
                    f"Picks={step['p']}  Difficulty={step['d']:<6s}  "
                    f"(Total risk: {self.format_money(cumulative_risk)})\n"
                )
            total_risk = round(sum(s["b"] for s in self.custom_mode), 2)
            preview_text += f"\nTotal risk if all steps used: {self.format_money(total_risk)}\n"
            self.betting_preview_text.config(state=tk.NORMAL)
            self.betting_preview_text.delete(1.0, tk.END)
            self.betting_preview_text.insert(tk.END, preview_text)
            self.betting_preview_text.config(state=tk.DISABLED)
            return

        if selected_mode in self.betting_modes:
            mode_values = self.betting_modes[selected_mode]
            
            preview_text = f"Mode: {selected_mode.title()}\n"
            preview_text += f"Number of steps: {len(mode_values)}\n"
            preview_text += f"Starting bet: {self.format_money(mode_values[0])}\n"
            preview_text += f"Maximum bet: {self.format_money(max(mode_values))}\n"
            preview_text += f"Total risk if all steps used: {self.format_money(sum(mode_values))}\n\n"
            
            preview_text += "Betting progression:\n"
            preview_text += "-" * 40 + "\n"
            for i, bet in enumerate(mode_values):
                risk_so_far = sum(mode_values[:i+1])
                preview_text += f"Loss #{i+1:2d}: {self.format_money(bet):>8s} (Total risk: {self.format_money(risk_so_far):>8s})\n"
            
            preview_text += "\nStrategy Analysis:\n"
            preview_text += "-" * 40 + "\n"
            
            # Calculate some statistics
            multipliers = []
            for i in range(1, len(mode_values)):
                multiplier = mode_values[i] / mode_values[i-1]
                multipliers.append(multiplier)
            
            if multipliers:
                avg_multiplier = sum(multipliers) / len(multipliers)
                preview_text += f"Average bet increase: {avg_multiplier:.2f}x\n"
                preview_text += f"Max single increase: {max(multipliers):.2f}x\n"
                preview_text += f"Min single increase: {min(multipliers):.2f}x\n"
            
            # Risk assessment
            total_risk = sum(mode_values)
            if total_risk <= 50:
                risk_level = "🟢 Low Risk"
            elif total_risk <= 200:
                risk_level = "🟡 Medium Risk"
            else:
                risk_level = "🔴 High Risk"
            
            preview_text += f"\nRisk Level: {risk_level}\n"
            preview_text += f"Recommended bankroll: {self.format_money(total_risk * 5)}\n"
            
        else:
            preview_text = f"Mode '{selected_mode}' not found in betting modes."
        
        # Update the text widget
        self.betting_preview_text.config(state=tk.NORMAL)
        self.betting_preview_text.delete(1.0, tk.END)
        self.betting_preview_text.insert(tk.END, preview_text)
        self.betting_preview_text.config(state=tk.DISABLED)
    
    def analyze_betting_modes(self):
        """Show detailed analysis of all betting modes"""
        analysis_window = tk.Toplevel(self.root)
        analysis_window.title("Betting Modes Analysis")
        analysis_window.geometry("900x700")
        analysis_window.resizable(True, True)
        
        # Make window modal
        analysis_window.transient(self.root)
        analysis_window.grab_set()
        
        # Create text widget with scrollbar
        text_frame = ttk.Frame(analysis_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        analysis_text = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD)
        analysis_text.pack(fill=tk.BOTH, expand=True)
        
        # Generate analysis
        analysis = "BETTING MODES COMPREHENSIVE ANALYSIS\n"
        analysis += "=" * 50 + "\n\n"
        
        for mode_name, mode_values in self.betting_modes.items():
            analysis += f"🎯 {mode_name.upper()} MODE\n"
            analysis += "-" * 30 + "\n"
            analysis += f"Steps: {len(mode_values)}\n"
            analysis += f"Values: {', '.join(self.format_money(v) for v in mode_values)}\n"
            analysis += f"Total Risk: {self.format_money(sum(mode_values))}\n"
            analysis += f"Max Bet: {self.format_money(max(mode_values))}\n"
            
            # Calculate break-even win rate using configured difficulty/picks
            total_risk = sum(mode_values)
            analysis_multiplier = self.get_win_multiplier(self.difficulty_var.get(), self.max_picks_var.get())
            breakeven_rate = total_risk / (total_risk + analysis_multiplier * mode_values[0])
            analysis += f"Break-even win rate: {breakeven_rate:.1%}\n"
            
            analysis += "\n"
        
        # Comparison table
        analysis += "COMPARISON TABLE\n"
        analysis += "=" * 50 + "\n"
        analysis += f"{'Mode':<10} {'Steps':<6} {'Max Bet':<10} {'Total Risk':<12} {'Break-even':<12}\n"
        analysis += "-" * 50 + "\n"
        
        for mode_name, mode_values in self.betting_modes.items():
            total_risk = sum(mode_values)
            max_bet = max(mode_values)
            analysis_multiplier = self.get_win_multiplier(self.difficulty_var.get(), self.max_picks_var.get())
            breakeven = total_risk / (total_risk + analysis_multiplier * mode_values[0])
            analysis += f"{mode_name:<10} {len(mode_values):<6} {self.format_money(max_bet):<10} {self.format_money(total_risk):<12} {breakeven:.1%}\n"
        
        analysis_text.insert(tk.END, analysis)
        analysis_text.config(state=tk.DISABLED)
        
        # Close button
        ttk.Button(analysis_window, text="Close", command=analysis_window.destroy).pack(pady=10)
    
    def reset_betting_modes(self):
        """Reset betting modes to defaults"""
        if messagebox.askyesno("Reset Betting Modes", "Reset all betting modes to default values?"):
            self.betting_modes = {k: list(v) for k, v in BETTING_MODES.items()}
            self.update_betting_preview()
            messagebox.showinfo("Reset Complete", "Betting modes reset to defaults!")
    
    def export_betting_modes(self):
        """Export betting modes to a JSON file"""
        from tkinter import filedialog
        
        filename = filedialog.asksaveasfilename(
            title="Export Betting Modes",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(self.betting_modes, f, indent=2)
                messagebox.showinfo("Export Successful", f"Betting modes exported to {filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export betting modes: {e}")
    
    def import_betting_modes(self):
        """Import betting modes from a JSON file"""
        from tkinter import filedialog
        
        filename = filedialog.askopenfilename(
            title="Import Betting Modes",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    imported_modes = json.load(f)
                
                # Validate imported data
                if not isinstance(imported_modes, dict):
                    raise ValueError("Invalid format: must be a dictionary")
                
                for mode_name, mode_values in imported_modes.items():
                    if not isinstance(mode_values, list):
                        raise ValueError(f"Invalid format for mode '{mode_name}': must be a list")
                    if not all(isinstance(v, (int, float)) and v >= 0 for v in mode_values):
                        raise ValueError(f"Invalid values in mode '{mode_name}': must be positive numbers")
                
                self.betting_modes = imported_modes
                self.update_betting_preview()
                messagebox.showinfo("Import Successful", f"Betting modes imported from {filename}")
                
            except Exception as e:
                messagebox.showerror("Import Error", f"Failed to import betting modes: {e}")
    
    def create_init_steps_tab(self, parent):
        """Create the initialization steps configuration tab"""
        self._step_type_map = {
            "Forza Bet al Minimo":           "set_bet_min",
            "Alza Difficoltà (N click)":     "raise_difficulty",
            "Abbassa Difficoltà (N click)":  "lower_difficulty",
            "Aspetta N secondi":             "wait",
            "Click a coordinate X,Y":        "click",
        }
        self._step_action_labels = {v: k for k, v in self._step_type_map.items()}

        # ── Sequenza step ────────────────────────────────────────────────────
        list_frame = ttk.LabelFrame(parent, text="Sequenza di Inizializzazione", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        tree_container = ttk.Frame(list_frame)
        tree_container.pack(fill=tk.BOTH, expand=True)

        self.init_tree = ttk.Treeview(
            tree_container,
            columns=("n", "tipo", "dettagli"),
            show="headings",
            height=8,
            selectmode="browse"
        )
        self.init_tree.heading("n",        text="#",            anchor=tk.CENTER)
        self.init_tree.heading("tipo",     text="Tipo azione")
        self.init_tree.heading("dettagli", text="Dettagli")
        self.init_tree.column("n",        width=35,  minwidth=35,  anchor=tk.CENTER)
        self.init_tree.column("tipo",     width=220, minwidth=150)
        self.init_tree.column("dettagli", width=380, minwidth=150)

        tree_sb = ttk.Scrollbar(tree_container, orient=tk.VERTICAL, command=self.init_tree.yview)
        self.init_tree.configure(yscrollcommand=tree_sb.set)
        self.init_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_sb.pack(side=tk.RIGHT, fill=tk.Y)

        btn_row = ttk.Frame(list_frame)
        btn_row.pack(fill=tk.X, pady=(8, 0))

        ttk.Button(btn_row, text="▲ Su",         command=self.init_step_move_up).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="▼ Giù",        command=self.init_step_move_down).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="✕ Rimuovi",    command=self.init_step_remove).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="🗑 Svuota",    command=self.init_step_clear).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_row, text="↺ Default",    command=self.init_step_reset).pack(side=tk.RIGHT, padx=2)

        # ── Aggiungi nuovo step ──────────────────────────────────────────────
        add_frame = ttk.LabelFrame(parent, text="Aggiungi Nuovo Step", padding=10)
        add_frame.pack(fill=tk.X, padx=5, pady=5)

        type_row = ttk.Frame(add_frame)
        type_row.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(type_row, text="Tipo di azione:").pack(side=tk.LEFT, padx=(0, 8))
        self._new_step_display = tk.StringVar(value="Forza Bet al Minimo")
        type_combo = ttk.Combobox(
            type_row,
            textvariable=self._new_step_display,
            state="readonly",
            width=30,
            values=list(self._step_type_map.keys())
        )
        type_combo.pack(side=tk.LEFT)
        type_combo.bind("<<ComboboxSelected>>", self._on_step_type_change)

        self._step_params_frame = ttk.Frame(add_frame)
        self._step_params_frame.pack(fill=tk.X, pady=(0, 6))
        self._step_param_vars = {}
        self._build_step_params_ui()

        ttk.Button(add_frame, text="➕  Aggiungi Step", command=self.init_step_add).pack(anchor=tk.W)

        # ── Coordinate pulsanti difficoltà ───────────────────────────────────
        diff_frame = ttk.LabelFrame(parent, text="Coordinate Pulsanti Difficoltà", padding=10)
        diff_frame.pack(fill=tk.X, padx=5, pady=5)

        diff_grid = ttk.Frame(diff_frame)
        diff_grid.pack(anchor=tk.W)

        ttk.Label(diff_grid, text="Alza difficoltà:").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Label(diff_grid, text="X:").grid(row=0, column=1, padx=2)
        ttk.Entry(diff_grid, textvariable=self.raise_diff_x_var, width=8).grid(row=0, column=2, padx=2)
        ttk.Label(diff_grid, text="Y:").grid(row=0, column=3, padx=2)
        ttk.Entry(diff_grid, textvariable=self.raise_diff_y_var, width=8).grid(row=0, column=4, padx=2)

        ttk.Label(diff_grid, text="Abbassa difficoltà:").grid(row=1, column=0, sticky=tk.W, padx=(0, 8), pady=(6, 0))
        ttk.Label(diff_grid, text="X:").grid(row=1, column=1, padx=2, pady=(6, 0))
        ttk.Entry(diff_grid, textvariable=self.lower_diff_x_var, width=8).grid(row=1, column=2, padx=2, pady=(6, 0))
        ttk.Label(diff_grid, text="Y:").grid(row=1, column=3, padx=2, pady=(6, 0))
        ttk.Entry(diff_grid, textvariable=self.lower_diff_y_var, width=8).grid(row=1, column=4, padx=2, pady=(6, 0))

        ttk.Label(diff_grid,
                  text="Le stesse coordinate della scheda Settings (condivise)",
                  font=("TkDefaultFont", 8), foreground="gray").grid(
            row=2, column=0, columnspan=5, sticky=tk.W, pady=(6, 0))

        self.refresh_init_tree()

    def _on_step_type_change(self, event=None):
        """Rebuild parameter widgets when step type changes"""
        for w in self._step_params_frame.winfo_children():
            w.destroy()
        self._step_param_vars = {}
        self._build_step_params_ui()

    def _build_step_params_ui(self):
        """Build dynamic parameter inputs based on selected step type"""
        action = self._step_type_map.get(self._new_step_display.get(), "set_bet_min")

        if action == "set_bet_min":
            ttk.Label(self._step_params_frame,
                      text="Nessun parametro — forza la scommessa al minimo del modo corrente",
                      foreground="gray").pack(side=tk.LEFT)

        elif action in ("raise_difficulty", "lower_difficulty"):
            ttk.Label(self._step_params_frame, text="Numero di click:").pack(side=tk.LEFT, padx=(0, 6))
            var = tk.IntVar(value=1)
            ttk.Spinbox(self._step_params_frame, from_=1, to=50,
                        textvariable=var, width=5).pack(side=tk.LEFT)
            self._step_param_vars["times"] = var

        elif action == "wait":
            ttk.Label(self._step_params_frame, text="Durata (secondi):").pack(side=tk.LEFT, padx=(0, 6))
            var = tk.DoubleVar(value=2.0)
            ttk.Spinbox(self._step_params_frame, from_=0.5, to=120.0,
                        increment=0.5, textvariable=var, width=7).pack(side=tk.LEFT)
            self._step_param_vars["seconds"] = var

        elif action == "click":
            ttk.Label(self._step_params_frame, text="X:").pack(side=tk.LEFT, padx=(0, 3))
            x_var = tk.IntVar(value=0)
            ttk.Entry(self._step_params_frame, textvariable=x_var, width=7).pack(side=tk.LEFT, padx=(0, 8))
            ttk.Label(self._step_params_frame, text="Y:").pack(side=tk.LEFT, padx=(0, 3))
            y_var = tk.IntVar(value=0)
            ttk.Entry(self._step_params_frame, textvariable=y_var, width=7).pack(side=tk.LEFT, padx=(0, 8))
            ttk.Label(self._step_params_frame, text="Etichetta:").pack(side=tk.LEFT, padx=(0, 3))
            lbl_var = tk.StringVar(value="Click")
            ttk.Entry(self._step_params_frame, textvariable=lbl_var, width=14).pack(side=tk.LEFT)
            self._step_param_vars["x"] = x_var
            self._step_param_vars["y"] = y_var
            self._step_param_vars["label"] = lbl_var

    def init_step_add(self):
        """Add a new initialization step to the list"""
        action = self._step_type_map.get(self._new_step_display.get(), "set_bet_min")
        step = {"action": action}

        if action in ("raise_difficulty", "lower_difficulty"):
            step["times"] = self._step_param_vars["times"].get()
        elif action == "wait":
            step["seconds"] = round(self._step_param_vars["seconds"].get(), 1)
        elif action == "click":
            step["x"]     = self._step_param_vars["x"].get()
            step["y"]     = self._step_param_vars["y"].get()
            step["label"] = self._step_param_vars["label"].get()

        self.init_steps.append(step)
        self.refresh_init_tree()

    def init_step_move_up(self):
        """Move the selected step one position up"""
        sel = self.init_tree.selection()
        if not sel:
            return
        idx = self.init_tree.index(sel[0])
        if idx > 0:
            self.init_steps[idx], self.init_steps[idx - 1] = self.init_steps[idx - 1], self.init_steps[idx]
            self.refresh_init_tree()
            items = self.init_tree.get_children()
            if idx - 1 < len(items):
                self.init_tree.selection_set(items[idx - 1])

    def init_step_move_down(self):
        """Move the selected step one position down"""
        sel = self.init_tree.selection()
        if not sel:
            return
        idx = self.init_tree.index(sel[0])
        if idx < len(self.init_steps) - 1:
            self.init_steps[idx], self.init_steps[idx + 1] = self.init_steps[idx + 1], self.init_steps[idx]
            self.refresh_init_tree()
            items = self.init_tree.get_children()
            if idx + 1 < len(items):
                self.init_tree.selection_set(items[idx + 1])

    def init_step_remove(self):
        """Remove the selected step"""
        sel = self.init_tree.selection()
        if not sel:
            return
        idx = self.init_tree.index(sel[0])
        del self.init_steps[idx]
        self.refresh_init_tree()

    def init_step_clear(self):
        """Remove all initialization steps"""
        if messagebox.askyesno("Conferma", "Svuotare tutti gli step di inizializzazione?"):
            self.init_steps = []
            self.refresh_init_tree()

    def init_step_reset(self):
        """Reset initialization steps to the default (set_bet_min only)"""
        if messagebox.askyesno("Conferma", "Ripristinare gli step predefiniti?"):
            self.init_steps = [{"action": "set_bet_min"}]
            self.refresh_init_tree()

    def refresh_init_tree(self):
        """Refresh the treeview display of initialization steps"""
        if not hasattr(self, 'init_tree'):
            return
        self.init_tree.delete(*self.init_tree.get_children())
        for i, step in enumerate(self.init_steps):
            action = step.get("action", "?")
            tipo = self._step_action_labels.get(action, action)

            if action == "set_bet_min":
                mode = self.mode_var.get() if hasattr(self, 'mode_var') else "?"
                seq  = self.betting_modes.get(mode, [0.1])
                dettagli = f"bet → {seq[0]:.2f} €  (modo: {mode})"
            elif action == "raise_difficulty":
                times = step.get("times", 1)
                dettagli = f"{times} click  →  ({self.raise_diff_x_var.get()}, {self.raise_diff_y_var.get()})"
            elif action == "lower_difficulty":
                times = step.get("times", 1)
                dettagli = f"{times} click  →  ({self.lower_diff_x_var.get()}, {self.lower_diff_y_var.get()})"
            elif action == "wait":
                dettagli = f"{step.get('seconds', 1):.1f} secondi"
            elif action == "click":
                x = step.get("x", 0); y = step.get("y", 0)
                dettagli = f"({x}, {y})   {step.get('label', '')}"
            else:
                dettagli = ""

            self.init_tree.insert("", tk.END, values=(i + 1, tipo, dettagli))

    async def execute_init_steps(self):
        """Execute the user-defined initialization steps before the game loop"""
        if not self.init_steps:
            self.log_message("ℹ️ Nessuno step di inizializzazione configurato.")
            return

        self.log_message(f"🚀 Inizializzazione: {len(self.init_steps)} step in esecuzione...")

        for i, step in enumerate(self.init_steps):
            if self.escape_pressed:
                break
            action = step.get("action")
            self.log_message(f"  ⚙️  [{i + 1}/{len(self.init_steps)}] {self._step_action_labels.get(action, action)}")

            if action == "set_bet_min":
                await self.decrease_bet_force()

            elif action == "raise_difficulty":
                times = step.get("times", 1)
                rx, ry = self.raise_diff_x_var.get(), self.raise_diff_y_var.get()
                if rx == 0 and ry == 0:
                    self.log_message("  ⚠️  Coordinate Alza Difficoltà non configurate!")
                else:
                    for _ in range(times):
                        pyautogui.click(rx, ry)
                        await asyncio.sleep(self.sleep_init_raise_diff_var.get())
                    self.log_message(f"  ⬆️  Difficoltà alzata × {times}")

            elif action == "lower_difficulty":
                times = step.get("times", 1)
                lx, ly = self.lower_diff_x_var.get(), self.lower_diff_y_var.get()
                if lx == 0 and ly == 0:
                    self.log_message("  ⚠️  Coordinate Abbassa Difficoltà non configurate!")
                else:
                    for _ in range(times):
                        pyautogui.click(lx, ly)
                        await asyncio.sleep(self.sleep_init_lower_diff_var.get())
                    self.log_message(f"  ⬇️  Difficoltà abbassata × {times}")

            elif action == "wait":
                seconds = step.get("seconds", 1)
                self.log_message(f"  ⏳  Attesa {seconds} secondi...")
                await asyncio.sleep(seconds)

            elif action == "click":
                x = step.get("x", 0); y = step.get("y", 0)
                label = step.get("label", f"({x},{y})")
                pyautogui.click(x, y)
                self.log_message(f"  🖱️  Click: {label}  ({x}, {y})")
                await asyncio.sleep(self.sleep_init_click_var.get())

        self.log_message("✅ Inizializzazione completata.")

    def create_control_tab(self, parent):
        # Game control buttons
        control_frame = ttk.LabelFrame(parent, text="Game Control", padding=10)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.start_button = ttk.Button(control_frame, text="🎰 START GAME", command=self.start_game, style="Accent.TButton")
        self.start_button.pack(side=tk.LEFT, padx=10, pady=5)
        
        self.stop_button = ttk.Button(control_frame, text="🛑 STOP GAME", command=self.stop_game, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=10, pady=5)
        
        ttk.Button(control_frame, text="🧪 TEST MODE", command=self.start_test_mode).pack(side=tk.LEFT, padx=10, pady=5)
        
        # Log control buttons
        log_control_frame = ttk.LabelFrame(parent, text="Log Control", padding=10)
        log_control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(log_control_frame, text="🗑️ Clear Log", command=self.clear_log).pack(side=tk.LEFT, padx=10, pady=5)
        ttk.Button(log_control_frame, text="💾 Export Log", command=self.export_log).pack(side=tk.LEFT, padx=10, pady=5)
        
        # Status display
        status_frame = ttk.LabelFrame(parent, text="Game Status", padding=10)
        status_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.status_text = scrolledtext.ScrolledText(status_frame, height=20, width=80)
        self.status_text.pack(fill=tk.BOTH, expand=True)
    
    def create_stats_tab(self, parent):
        # Current game stats
        current_frame = ttk.LabelFrame(parent, text="Current Game Statistics", padding=10)
        current_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Stats labels
        stats_grid = ttk.Frame(current_frame)
        stats_grid.pack(fill=tk.X)
        
        ttk.Label(stats_grid, text="💰 Current Cash:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.current_cash_label = ttk.Label(stats_grid, text="0.00", font=("Courier", 10))
        self.current_cash_label.grid(row=0, column=1, sticky=tk.W, padx=10, pady=2)
        
        ttk.Label(stats_grid, text="📈 Highest Cash:").grid(row=0, column=2, sticky=tk.W, pady=2)
        self.highest_cash_label = ttk.Label(stats_grid, text="0.00", font=("Courier", 10))
        self.highest_cash_label.grid(row=0, column=3, sticky=tk.W, padx=10, pady=2)
        
        ttk.Label(stats_grid, text="🎰 Current Bet:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.current_bet_label = ttk.Label(stats_grid, text="0.10", font=("Courier", 10))
        self.current_bet_label.grid(row=1, column=1, sticky=tk.W, padx=10, pady=2)
        
        ttk.Label(stats_grid, text="🔝 Highest Bet:").grid(row=1, column=2, sticky=tk.W, pady=2)
        self.highest_bet_label = ttk.Label(stats_grid, text="0.10", font=("Courier", 10))
        self.highest_bet_label.grid(row=1, column=3, sticky=tk.W, padx=10, pady=2)
        
        ttk.Label(stats_grid, text="🏁 Rounds:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.rounds_label = ttk.Label(stats_grid, text="0", font=("Courier", 10))
        self.rounds_label.grid(row=2, column=1, sticky=tk.W, padx=10, pady=2)
        
        ttk.Label(stats_grid, text="🔄 Tries:").grid(row=2, column=2, sticky=tk.W, pady=2)
        self.tries_label = ttk.Label(stats_grid, text="0", font=("Courier", 10))
        self.tries_label.grid(row=2, column=3, sticky=tk.W, padx=10, pady=2)
        
        ttk.Label(stats_grid, text="📉 Total Loss:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.loss_label = ttk.Label(stats_grid, text="0.00", font=("Courier", 10))
        self.loss_label.grid(row=3, column=1, sticky=tk.W, padx=10, pady=2)
        
        ttk.Label(stats_grid, text="📉 Lowest Cash:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.lowest_cash_label = ttk.Label(stats_grid, text="0.00", font=("Courier", 10))
        self.lowest_cash_label.grid(row=4, column=1, sticky=tk.W, padx=10, pady=2)

        # Progress bar
        progress_frame = ttk.LabelFrame(parent, text="Progress", padding=10)
        progress_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        self.progress_label = ttk.Label(progress_frame, text="Ready to start")
        self.progress_label.pack()

        
        # Add Total Win display
        ttk.Label(stats_grid, text="🎉 Total Win:").grid(row=3, column=2, sticky=tk.W, pady=2)
        self.total_win_label = ttk.Label(stats_grid, text="0.00", font=("Courier", 10))
        self.total_win_label.grid(row=3, column=3, sticky=tk.W, padx=10, pady=2)

    def create_pauses_tab(self, parent):
        """Create tab for configurable pause durations."""
        game_loop_frame = ttk.LabelFrame(parent, text="Loop di gioco", padding=10)
        game_loop_frame.pack(fill=tk.X, padx=5, pady=5)

        setup_frame = ttk.LabelFrame(parent, text="Operazioni di setup", padding=10)
        setup_frame.pack(fill=tk.X, padx=5, pady=5)

        def add_pause_row(container, row, label_text, variable):
            ttk.Label(container, text=label_text).grid(row=row, column=0, sticky=tk.W, padx=(0, 8), pady=2)
            ttk.Spinbox(
                container,
                from_=0.01,
                to=30.0,
                increment=0.05,
                width=8,
                textvariable=variable
            ).grid(row=row, column=1, sticky=tk.W, pady=2)

        add_pause_row(game_loop_frame, 0, "Prima di play/collect (s)", self.sleep_play_or_collect_var)
        add_pause_row(game_loop_frame, 1, "Prima di increase_bet (s)", self.sleep_increase_bet_var)
        add_pause_row(game_loop_frame, 2, "Prima di decrease_bet (s)", self.sleep_decrease_bet_var)
        add_pause_row(game_loop_frame, 3, "Dopo play, prima del tile (s)", self.sleep_after_play_var)
        add_pause_row(game_loop_frame, 4, "Dopo click tile (s)", self.sleep_after_tile_click_var)
        add_pause_row(game_loop_frame, 5, "Tra i round (s)", self.sleep_between_rounds_var)
        add_pause_row(game_loop_frame, 6, "Dopo risultato/prima del prossimo bet (s)", self.sleep_after_result_var)
        add_pause_row(game_loop_frame, 7, "Retry colore sconosciuto (s)", self.sleep_color_retry_var)

        add_pause_row(setup_frame, 0, "Prima di click_tile (s)", self.sleep_click_tile_var)
        add_pause_row(setup_frame, 1, "Tra click in decrease_bet_force (s)", self.sleep_decrease_bet_force_var)
        add_pause_row(setup_frame, 2, "Tra click in decrease_diff_force (s)", self.sleep_decrease_diff_force_var)
        add_pause_row(setup_frame, 3, "Tra click in set_difficulty (s)", self.sleep_set_difficulty_var)
        add_pause_row(setup_frame, 4, "Alza diff. in init steps (s)", self.sleep_init_raise_diff_var)
        add_pause_row(setup_frame, 5, "Abbassa diff. in init steps (s)", self.sleep_init_lower_diff_var)
        add_pause_row(setup_frame, 6, "Click generico in init steps (s)", self.sleep_init_click_var)

        def reset_pauses():
            self.sleep_play_or_collect_var.set(1.0)
            self.sleep_increase_bet_var.set(1.0)
            self.sleep_decrease_bet_var.set(1.0)
            self.sleep_decrease_bet_force_var.set(0.05)
            self.sleep_decrease_diff_force_var.set(0.05)
            self.sleep_set_difficulty_var.set(0.5)
            self.sleep_click_tile_var.set(1.0)
            self.sleep_after_play_var.set(1.0)
            self.sleep_after_tile_click_var.set(1.0)
            self.sleep_between_rounds_var.set(1.0)
            self.sleep_after_result_var.set(2.0)
            self.sleep_color_retry_var.set(1.0)
            self.sleep_init_raise_diff_var.set(0.4)
            self.sleep_init_lower_diff_var.set(0.4)
            self.sleep_init_click_var.set(0.3)

        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, padx=5, pady=10)
        ttk.Button(btn_frame, text="Salva pause", command=self.on_save_settings).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Reset valori default", command=reset_pauses).pack(side=tk.LEFT)

    def start_mouse_monitoring(self):
        """Start monitoring mouse coordinates"""
        self.mouse_monitoring = True
        threading.Thread(target=self.mouse_monitor_thread, daemon=True).start()
    
    def mouse_monitor_thread(self):
        """Thread function for monitoring mouse coordinates"""
        while self.mouse_monitoring:
            try:
                x, y = pyautogui.position()
                coord_text = f"Mouse Position: ({x}, {y})"
                
                # Update both coordinate displays
                self.root.after(0, lambda: self.coord_label.config(text=coord_text))
                if hasattr(self, 'settings_coord_label'):
                    self.root.after(0, lambda: self.settings_coord_label.config(text=coord_text))
                
                time.sleep(0.1)
            except Exception as e:
                self.log_message(f"[WARN] Mouse monitor stopped due to error: {e}")
                break
    
    def open_betting_mode_editor(self):
        """Open the betting mode editor window"""
        editor_window = tk.Toplevel(self.root)
        editor_window.title("Betting Mode Editor")
        editor_window.geometry("900x700")  # Larger default size
        editor_window.resizable(True, True)
        
        # Make window modal
        editor_window.transient(self.root)
        editor_window.grab_set()
        
        # Create main container directly without scrollable canvas for better responsiveness
        main_frame = ttk.Frame(editor_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Instructions
        instructions_frame = ttk.Frame(main_frame)
        instructions_frame.pack(fill=tk.X, pady=(0, 15))
        
        instructions_text = "Edit betting mode arrays. Enter comma-separated values from the allowed bet values only.\nClick 'Show Valid Values' to see all allowed bet amounts:"
        instructions = ttk.Label(instructions_frame, text=instructions_text, font=("TkDefaultFont", 10, "bold"))
        instructions.pack(pady=(0, 8))
        
        # Create scrollable frame for betting modes with scrollbar but no mousewheel
        modes_frame = ttk.Frame(main_frame)
        modes_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Create canvas and scrollbar for modes (without mousewheel events)
        canvas = tk.Canvas(modes_frame, highlightthickness=0)  # No fixed height - let it expand
        scrollbar = ttk.Scrollbar(modes_frame, orient="vertical", command=canvas.yview)
        scrollable_modes_frame = ttk.Frame(canvas)
        
        # Configure scroll region when content changes
        def configure_scroll_region(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Update canvas window width to match canvas width
            canvas_width = canvas.winfo_width()
            if canvas_width > 1:  # Ensure canvas is properly initialized
                canvas.itemconfig(canvas_window, width=canvas_width)
        
        scrollable_modes_frame.bind("<Configure>", configure_scroll_region)
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_modes_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Make canvas responsive to width changes
        def configure_canvas_width(event):
            if canvas.winfo_exists() and canvas.winfo_children():
                canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind('<Configure>', configure_canvas_width)
        
        # Note: Mousewheel scrolling intentionally removed for better responsiveness
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Dictionary to store text widgets for each mode
        mode_text_widgets = {}
        
        # Create editor for each betting mode with better layout
        for i, (mode_name, mode_values) in enumerate(self.betting_modes.items()):
            # Mode frame with better styling
            mode_frame = ttk.LabelFrame(scrollable_modes_frame, text=f"🎯 {mode_name.title()} Mode", padding=15)
            mode_frame.pack(fill=tk.X, pady=8, padx=5)
            
            # Current values display with better formatting
            current_text = ", ".join(str(val) for val in mode_values)
            info_frame = ttk.Frame(mode_frame)
            info_frame.pack(fill=tk.X, pady=(0, 10))
            
            ttk.Label(info_frame, text=f"Current ({len(mode_values)} values):", font=("TkDefaultFont", 9, "bold")).pack(side=tk.LEFT)
            ttk.Label(info_frame, text=f"Total Risk: {sum(mode_values):.1f}", font=("TkDefaultFont", 8), foreground="blue").pack(side=tk.RIGHT)
            
            # Text widget for editing with proper height
            text_widget = tk.Text(mode_frame, height=4, width=70, wrap=tk.WORD, font=("TkDefaultFont", 9))
            text_widget.pack(fill=tk.X, pady=(5, 0))
            text_widget.insert(tk.END, current_text)
            mode_text_widgets[mode_name] = text_widget
        
        # Buttons frame outside scrollable area
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Configure button layout for 5 columns (including new Show Valid Values button)
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        button_frame.grid_columnconfigure(2, weight=1)
        button_frame.grid_columnconfigure(3, weight=1)
        button_frame.grid_columnconfigure(4, weight=1)
        
        def validate_and_save():
            """Validate and save the betting modes"""
            new_modes = {}
            errors = []
            
            for mode_name, text_widget in mode_text_widgets.items():
                try:
                    # Get text and parse values
                    text_content = text_widget.get("1.0", tk.END).strip()
                    if not text_content:
                        errors.append(f"{mode_name}: Cannot be empty")
                        continue
                    
                    # Parse comma-separated values
                    values_str = [v.strip() for v in text_content.split(',')]
                    values = []
                    
                    for val_str in values_str:
                        if val_str:  # Skip empty strings
                            try:
                                val = float(val_str)
                                if val < 0:
                                    errors.append(f"{mode_name}: Negative values not allowed ({val})")
                                elif val not in self.bet_values:
                                    errors.append(f"{mode_name}: Value {val} is not allowed. Must be one of: {', '.join(map(str, self.bet_values))}")
                                else:
                                    values.append(round(val, 2))
                            except ValueError:
                                errors.append(f"{mode_name}: Invalid number '{val_str}'")
                    
                    if not values:
                        errors.append(f"{mode_name}: No valid values found")
                    elif len(values) < 2:
                        errors.append(f"{mode_name}: At least 2 values required")
                    else:
                        # Sort values to ensure ascending order
                        values.sort()
                        new_modes[mode_name] = values
                        
                except Exception as e:
                    errors.append(f"{mode_name}: Error parsing values - {str(e)}")
            
            if errors:
                error_message = "Validation errors:\n" + "\n".join(errors)
                messagebox.showerror("Validation Error", error_message)
                return
            
            # Save the new modes
            self.betting_modes = new_modes
            messagebox.showinfo("Success", "Betting modes updated successfully!")
            editor_window.destroy()
        
        def reset_to_defaults():
            """Reset all modes to default values"""
            if messagebox.askyesno("Reset", "Reset all betting modes to default values?"):
                default_modes = {k: list(v) for k, v in BETTING_MODES.items()}

                # Update text widgets
                for mode_name, values in default_modes.items():
                    if mode_name in mode_text_widgets:
                        text_widget = mode_text_widgets[mode_name]
                        text_widget.delete("1.0", tk.END)
                        text_widget.insert(tk.END, ", ".join(str(val) for val in values))
        
        def show_valid_values():
            """Show a list of all valid bet values"""
            valid_values_text = "Valid bet values that can be used in betting modes:\n\n"
            valid_values_text += ", ".join(str(val) for val in self.bet_values)
            valid_values_text += f"\n\nTotal: {len(self.bet_values)} allowed values"
            valid_values_text += "\n\nNote: Only these exact values are allowed in betting mode arrays."
            messagebox.showinfo("Valid Bet Values", valid_values_text)
        
        def preview_mode():
            """Preview the selected mode values"""
            selected_mode = self.mode_var.get()
            if selected_mode in mode_text_widgets:
                text_widget = mode_text_widgets[selected_mode]
                text_widget.focus_set()
                text_widget.tag_add(tk.SEL, "1.0", tk.END)
                messagebox.showinfo("Preview", f"Selected mode: {selected_mode}\nValues: {text_widget.get('1.0', tk.END).strip()}")
        
        # Buttons with grid layout for better responsiveness
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        button_frame.grid_columnconfigure(2, weight=1)
        button_frame.grid_columnconfigure(3, weight=1)
        button_frame.grid_columnconfigure(4, weight=1)
        
        ttk.Button(button_frame, text="💾 Save Changes", command=validate_and_save).grid(row=0, column=0, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(button_frame, text="🔄 Reset to Defaults", command=reset_to_defaults).grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(button_frame, text="👁️ Preview Selected", command=preview_mode).grid(row=0, column=2, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(button_frame, text="📋 Show Valid Values", command=show_valid_values).grid(row=0, column=3, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(button_frame, text="❌ Cancel", command=editor_window.destroy).grid(row=1, column=2, padx=5, pady=5, sticky=tk.EW)
        
        # Center the window on screen
        editor_window.update_idletasks()
        x = (editor_window.winfo_screenwidth() - editor_window.winfo_width()) // 2
        y = (editor_window.winfo_screenheight() - editor_window.winfo_height()) // 2
        editor_window.geometry(f"+{x}+{y}")
    
    def auto_generate_grid(self):
        """Auto-generate coordinates for key tiles only"""
        start_x = 1640
        start_y = 740
        spacing_x = 170
        spacing_y = 128
        
        key_tiles = [1, 2, 3, 4, 5, 6, 11, 16, 21]
        
        for tile_num in key_tiles:
            # Calculate position based on original 5x5 grid layout
            row = (tile_num - 1) // 5
            col = (tile_num - 1) % 5
            x = start_x + col * spacing_x
            y = start_y + row * spacing_y
            
            if tile_num in self.tile_vars:
                self.tile_vars[tile_num][0].set(x)
                self.tile_vars[tile_num][1].set(y)
        
        messagebox.showinfo("Generated", f"Coordinates auto-generated for tiles: {', '.join(map(str, key_tiles))}!")
    
    def test_click_tile(self, tile_num):
        """Test click on a specific tile"""
        if tile_num in self.tile_vars:
            x = self.tile_vars[tile_num][0].get()
            y = self.tile_vars[tile_num][1].get()
            self.log_message(f"Testing click on tile {tile_num} at ({x}, {y})")
            threading.Thread(target=lambda: self.safe_click(x, y), daemon=True).start()
    
    def safe_click(self, x, y):
        """Safely perform a click with small delay"""
        time.sleep(1)  # Small delay for safety
        pyautogui.click(x, y)
        self.log_message(f"Clicked at ({x}, {y})")
    
    async def play_or_collect(self):
        """Play/collect button click"""
        play_x = self.play_x_var.get()
        play_y = self.play_y_var.get()
        await asyncio.sleep(self.sleep_play_or_collect_var.get())
        pyautogui.click(play_x, play_y)
        self.log_message("🎮 Clicked play/collect button")
    
    async def increase_bet(self):
        """Increase bet by clicking raise bet button"""
        raise_x = self.raise_x_var.get()
        raise_y = self.raise_y_var.get()
        await asyncio.sleep(self.sleep_increase_bet_var.get())  # Small delay to ensure click is registered (same as playM.py)
        pyautogui.click(raise_x, raise_y)
        # Update bet value using the same logic as playM.py
        current_index = self.bet_values.index(self.bet) if self.bet in self.bet_values else self.tries
        self.bet = round(self.bet_values[min(current_index + 1, len(self.bet_values) - 1)], 2)  # Increase bet to next value and round
    
    async def decrease_bet(self):
        await asyncio.sleep(self.sleep_decrease_bet_var.get())
        """Decrease bet by clicking lower bet button"""
        lower_x = self.lower_x_var.get()
        lower_y = self.lower_y_var.get()
        pyautogui.click(lower_x, lower_y)
        # Update bet value using the same logic as playM.py
        current_index = self.bet_values.index(self.bet) if self.bet in self.bet_values else 0
        self.bet = round(self.bet_values[max(current_index - 1, 0)], 2)  # Decrease bet to previous value and round
    
    async def decrease_bet_force(self):
        """Force decrease bet to minimum"""
        lower_x = self.lower_x_var.get()
        lower_y = self.lower_y_var.get()
        
        # Click lower bet button multiple times to ensure minimum (same as playM.py)
        for i in range(len(self.bet_values)):
            await asyncio.sleep(self.sleep_decrease_bet_force_var.get())
            pyautogui.click(lower_x, lower_y)
        
        min_bet = self._get_min_bet_for_selected_mode()
        self.bet = round(min_bet, 2)
        self.log_message(f"🔽 Bet forced to minimum: {self.format_money(self.bet)}")

    async def set_bet_value(self, target_bet):
        """Adjust current bet to an exact value by clicking +/- buttons."""
        target_bet = round(target_bet, 2)
        if target_bet not in self.bet_values:
            self.log_message(f"[WARN] Bet {self.format_money(target_bet)} non valida per set_bet_value")
            return
        old_bet = self.bet
        while self.bet < target_bet:
            await self.increase_bet()
        while self.bet > target_bet:
            await self.decrease_bet()
        if self.bet != old_bet:
            direction = "📈" if self.bet > old_bet else "📉"
            self.log_message(f"{direction} Bet: {self.format_money(old_bet)} → {self.format_money(self.bet)}")

    async def decrease_difficulty_force(self, silent=False):
        """Force difficulty to minimum (low) by clicking lower_difficulty many times"""
        lx = self.lower_diff_x_var.get()
        ly = self.lower_diff_y_var.get()
        if lx == 0 and ly == 0:
            return  # Coordinate non configurate
        for _ in range(5):
            await asyncio.sleep(self.sleep_decrease_diff_force_var.get())
            pyautogui.click(lx, ly)
        self.current_difficulty = "low"
        if not silent:
            self.log_message("🔽 Difficoltà forzata al minimo (low)")

    async def set_difficulty(self, target_difficulty):
        """Forza al minimo poi alza alla difficoltà target: low/medium/high"""
        if self.current_difficulty == target_difficulty:
            return
        await self.decrease_difficulty_force(silent=True)
        rx = self.raise_diff_x_var.get()
        ry = self.raise_diff_y_var.get()
        if rx == 0 and ry == 0:
            return  # Coordinate non configurate
        clicks = {"low": 0, "medium": 1, "high": 2}.get(target_difficulty, 0)
        for _ in range(clicks):
            await asyncio.sleep(self.sleep_set_difficulty_var.get())
            pyautogui.click(rx, ry)
        self.current_difficulty = target_difficulty
        if clicks > 0:
            self.log_message(f"🎯 Difficoltà impostata a: {target_difficulty}")

    async def click_tile(self, tile_number):
        """Click on a specific tile"""
        if tile_number in self.tiles:
            point = self.tiles[tile_number]
            await asyncio.sleep(self.sleep_click_tile_var.get())
            pyautogui.click(point.x, point.y)
            self.log_message(f"🎯 Clicked tile {tile_number} at ({point.x}, {point.y})")
        else:
            self.log_message(f"❌ Tile {tile_number} not found in tiles dictionary")
    
    def generate_random_tile(self):
        """Generate a random tile number from available tiles that hasn't been selected yet"""
        available_tiles = [1, 2, 3, 4, 5, 6, 11, 16, 21]
        unused_tiles = [tile for tile in available_tiles if tile not in self.randoms]
        
        if not unused_tiles:
            # If all tiles have been used, reset and start over
            self.randoms = []
            unused_tiles = available_tiles
        
        tile_number = random.choice(unused_tiles)
        self.randoms.append(tile_number)
        self.log_message(f"🎲 Generated random tile: {tile_number}")
        return tile_number
    
    def _read_color_at_point_legacy(self, point):
        """Read color at a point on screen"""
        try:
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
        except Exception as e:
            self.log_message(f"❌ Error reading color: {e}")
            return {"r": 0, "g": 0, "b": 0, "a": 255}
    
    def is_color_in_range_blue(self, color, target_color, tolerance=50):
        """Check if color is in blue range"""
        return (
            abs(color["r"] - target_color["r"]) <= tolerance and
            abs(color["g"] - target_color["g"]) <= tolerance and
            abs(color["b"] - target_color["b"]) <= tolerance
        )
    
    def is_color_in_range_red(self, color, target_color, tolerance=50):
        """Check if color is in red range"""
        return (
            abs(color["r"] - target_color["r"]) <= tolerance and
            abs(color["g"] - target_color["g"]) <= tolerance and
            abs(color["b"] - target_color["b"]) <= tolerance
        )
    
    def start_game(self):
        """Start the automated game"""
        if self.game_running:
            return
        try:
            self.game_engine.validate_settings()
        except Exception as e:
            messagebox.showerror("Invalid Settings", str(e))
            return

        if not messagebox.askyesno("Start Real Game", 
                                  "⚠️ WARNING: This will start REAL game automation!\n\n"
                                  "• Mouse will be controlled automatically\n"
                                  "• Make sure your game window is positioned correctly\n"
                                  "• Press ESCAPE key to stop at any time\n"
                                  "• Use TEST MODE for safe simulation\n\n"
                                  "Do you want to continue?"):
            return
        
        self.game_running = True
        self.escape_pressed = False
        self.stop_event.clear()
        self.running_event.set()
        
        # Update UI
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.game_engine.initialize_game_variables()
        self.game_engine.update_tiles_from_gui()
        threading.Thread(target=self.game_engine.run_game_async, daemon=True).start()
        self.game_engine.start_keyboard_listener()
        
        self.log_message("🎰 REAL GAME STARTED!")
        self.log_message("⚠️ AUTOMATION ACTIVE - Mouse will be controlled!")
        self.log_message(f"Starting cash: {self.format_money(self.current_cash)}")
        self.log_message("Press ESCAPE key to stop at any time")
    
    def stop_game(self):
        """Stop the automated game or test mode"""
        self.game_running = False
        self.escape_pressed = True
        self.stop_event.set()
        self.running_event.clear()
        
        # Update UI
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        self.game_engine.stop_keyboard_listener()
        
        self.log_message("🛑 GAME/TEST STOPPED by user")
    
    def start_test_mode(self):
        """Start test mode (simulation)"""
        if self.game_running:
            self.log_message("⚠️ Game already running! Stop current game first.")
            return

        try:
            self.game_engine.validate_settings()
        except Exception as e:
            messagebox.showerror("Invalid Settings", str(e))
            return

        self.game_running = True
        self.escape_pressed = False
        self.stop_event.clear()
        self.running_event.set()

        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)

        self.game_engine.initialize_game_variables()
        initial_config = self.game_engine._get_round_config_for_strategy()

        difficulty_text = initial_config["round_difficulty"]
        picks_text = str(initial_config["max_picks"])
        if self.mode_var.get() == "custom" and self.custom_mode:
            difficulty_text = f"{difficulty_text} (step-based)"
            picks_text = f"{picks_text} (step-based)"

        self.log_message("🧪 Starting TEST MODE — simulating real 5x5 grid")
        self.log_message(
            f"📊 Mode: {self.mode_var.get()} | Difficulty: {difficulty_text} | "
            f"Picks: {picks_text} | Starting cash: {self.format_money(self.current_cash)}"
        )
        self.log_message(
            f"🧨 Board: {TEST_MODE_BOARD_SIZE} tiles | "
            f"{initial_config['mine_count']} mines | {TEST_MODE_BOARD_SIZE - initial_config['mine_count']} coins"
        )
        if self.grinding_mode_var.get():
            self.log_message(
                f"⚙️ Grinding mode enabled | range={self.grinding_range_var.get():.2f} | "
                f"random_p={'on' if self.grinding_p_random_var.get() else 'off'}"
            )

        self.progress_var.set(0)
        self.progress_label.config(text="TEST MODE running...")
        self.update_stats_display()
        
        threading.Thread(target=self.game_engine.run_test_mode, daemon=True).start()
    
    def run_test_mode(self):
        """Run game simulation for testing"""
        stop_reason = "Simulation completed"
        try:
            max_rounds = self.max_rounds_var.get()
            target_win = self.target_win_var.get()
            max_loss = self.max_loss_var.get()

            while True:
                if not self.game_running:
                    stop_reason = "Stopped by user"
                    break

                round_config = self._get_round_config_for_strategy()

                if self.rounds >= max_rounds:
                    stop_reason = "Reached maximum rounds"
                    break
                if self.current_cash >= target_win:
                    stop_reason = "Reached target win"
                    break
                if self.loss >= max_loss:
                    stop_reason = "Reached maximum loss"
                    break
                if self.current_cash < round_config["target_bet"]:
                    stop_reason = "Insufficient cash"
                    break

                self.bet = round(round_config["target_bet"], 2)
                self.picks = 0
                self.randoms = []
                if self.bet > self.highest_bet:
                    self.highest_bet = round(self.bet, 2)

                self.log_message(f"\n=== Test Round {self.rounds + 1} ===")
                self.log_message(
                    f"[ROUND] Strategy={round_config['strategy_source']} | "
                    f"Mode={round_config['selected_mode_name']} | Difficulty={round_config['round_difficulty']} | "
                    f"Picks target={round_config['max_picks']} | Mines={round_config['mine_count']} | "
                    f"Bet={self.format_money(self.bet)}"
                )

                self.current_cash = round(self.current_cash - self.bet, 2)
                self.log_message(f"[ROUND] Started round - Cash deducted: {self.format_money(self.bet)}")
                self.log_message(f"💸 New Balance: {self.format_money(self.current_cash)}")

                board_result = self._simulate_test_board(
                    round_config["round_difficulty"],
                    round_config["max_picks"],
                )
                opened_summary = ", ".join(
                    f"T{entry['tile']}={'BLUE' if entry['outcome'] == 'coin' else 'RED'}"
                    for entry in board_result["opened_tiles"]
                )
                self.log_message(f"[BOARD] Opened tiles: {opened_summary}")

                self.picks = board_result["coins_found"]
                if board_result["hit_mine"]:
                    self.log_message(
                        f"[LOSS] Hit a RED tile after {board_result['coins_found']} blue(s). "
                        f"Balance remains {self.format_money(self.current_cash)}"
                    )
                    self._apply_test_loss(round_config)
                else:
                    self.log_message(
                        f"[WIN] {round_config['max_picks']} BLUE tiles found. "
                        f"Multiplier={round_config['multiplier']:.2f}"
                    )
                    self._apply_test_win(round_config)

                self.rounds += 1
                if self.current_cash > self.highest_cash:
                    self.highest_cash = round(self.current_cash, 2)
                self.loss = max(0, round(self.highest_cash - self.current_cash, 2))

                progress = 100 if max_rounds <= 0 else min(100, (self.rounds / max_rounds) * 100)
                self.root.after(0, lambda value=progress: self.progress_var.set(value))
                self.root.after(
                    0,
                    lambda rounds=self.rounds, total=max_rounds: self.progress_label.config(
                        text=f"Test round {rounds}/{total}"
                    )
                )
                self.root.after(0, self.update_stats_display)

            if stop_reason == "Simulation completed":
                stop_reason = "Strategy loop completed"
        except Exception as e:
            stop_reason = f"Error: {e}"
            self.log_message(f"❌ TEST MODE error: {e}")
        finally:
            self._finish_test_mode(stop_reason)
    
    def validate_settings(self):
        """Validate game settings"""
        try:
            starting_cash = self.starting_cash_var.get()
            if starting_cash <= 0:
                raise ValueError("Starting cash must be positive")
            
            if self.mode_var.get() != "custom":
                max_picks = self.max_picks_var.get()
                if max_picks not in [1, 2, 3, 4]:
                    raise ValueError("Max picks must be between 1 and 4")
            
            return True
        except Exception as e:
            messagebox.showerror("Invalid Settings", str(e))
            return False
    
    def initialize_game_variables(self):
        """Initialize game variables from GUI settings"""
        self.current_cash = round(self.starting_cash_var.get(), 2)
        self.highest_cash = self.current_cash
        self.lowest_cash = self.current_cash
        
        initial_bet = self._get_min_bet_for_selected_mode()
        self.bet = round(initial_bet, 2)
        self.highest_bet = round(initial_bet, 2)
        self.picks = 0
        self.tries = 0
        self.rounds = 0
        self.loss = 0.0
        self.total_win = 0.0  # Add this line
        self.randoms = []
        self.grinding_active = False
        self.grinding_saved_balance = None
        self.current_difficulty = None  # Resettato: difficoltà ignota fino alla prima impostazione

        self.log_message(f"💰 Initialized with cash: {self.format_money(self.current_cash)}")
        self.log_message(f"🎯 Target win: {self.format_money(self.target_win_var.get())}")
        self.update_stats_display()
    
    def update_tiles_from_gui(self):
        """Update tiles dictionary from GUI values"""
        self.tiles = self.coordinate_manager.build_tile_points(self.tile_vars)
    
    def start_keyboard_listener(self):
        """Start keyboard listener for escape key"""
        def on_key_press(key):
            if key == keyboard.Key.esc:
                self.escape_pressed = True
                self.log_message("🛑 ESCAPE key pressed!")
                self.root.after(0, self.stop_game)
                return False
        
        self.keyboard_listener = keyboard.Listener(on_press=on_key_press)
        self.keyboard_listener.start()
    
    def run_game_async(self):
        """Run the game asynchronously"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._main_game_loop_legacy())
        finally:
            loop.close()
    
    async def _main_game_loop_legacy(self):
        """Main game loop with actual game automation"""
        max_rounds = self.max_rounds_var.get()
        target_win = self.target_win_var.get()
        max_loss = self.max_loss_var.get()
        max_picks = self.max_picks_var.get()
        wait_selected = self.wait_selected_var.get()
        
        self.log_message("🎮 Starting REAL game automation...")
        self.log_message("⚠️ Make sure your game window is positioned correctly!")
        
        # Execute user-defined initialization steps
        await self.execute_init_steps()

        # Set difficulty (standard modes: once at start; custom: handled per round)
        if self.mode_var.get() != "custom":
            await self.set_difficulty(self.difficulty_var.get())
        else:
            await self.decrease_difficulty_force()

        while self.game_running and not self.escape_pressed:
            # Check end conditions
            if self.rounds >= max_rounds:
                self.log_message("Reached maximum rounds!")
                break
            if self.current_cash >= target_win:
                self.log_message("🎉 Reached target win!")
                break
            if self.loss >= max_loss:
                self.log_message("💸 Reached maximum loss!")
                break
            if self.current_cash < self.bet:
                self.log_message("💀 Insufficient cash!")
                break
            
            # Update progress
            progress = (self.rounds / max_rounds) * 100
            self.root.after(0, lambda: self.progress_var.set(progress))
            self.root.after(0, lambda: self.progress_label.config(text=f"Round {self.rounds + 1}/{max_rounds}"))
            
            # Optional wait between rounds
            if wait_selected and self.rounds > 0:
                wait_time = random.randint(60, 360)  # 1-6 minutes
                self.log_message(f"⏰ Waiting {wait_time//60}m {wait_time%60}s before next round...")
                await asyncio.sleep(wait_time)
            
            # Start new round - actual game automation
            await self._play_real_game_round_legacy()
            
            # Update statistics
            self.root.after(0, self.update_stats_display)
            
            # Small delay between rounds
            await asyncio.sleep(self.sleep_between_rounds_var.get())
        
        # Game ended
        self.root.after(0, self.stop_game)
        self.log_message("=== GAME ENDED ===")
        self.log_message(f"Final cash: {self.format_money(self.current_cash)}")
        self.log_message(f"Highest cash: {self.format_money(self.highest_cash)}")
        self.log_message(f"Highest bet: {self.format_money(self.highest_bet)}")
    
    async def _play_real_game_round_legacy(self):
        """Play an actual game round with mouse automation"""
        round_config = self._get_round_config_for_strategy()
        selected_mode_name = round_config["selected_mode_name"]
        step_idx = round_config["step_idx"]
        max_step_idx = round_config["max_step_idx"]
        grinding_enabled = round_config["grinding_enabled"]
        max_picks = round_config["max_picks"]
        round_difficulty = round_config["round_difficulty"]
        multiplier = round_config["multiplier"]

        # Determine picks and difficulty for this round
        if self.grinding_active:
            await self.set_difficulty(round_difficulty)
            await self.set_bet_value(GRINDING_STEP["b"])
            if self.bet > self.highest_bet:
                self.highest_bet = round(self.bet, 2)
            if self.grinding_saved_balance is not None:
                self.log_message(
                    f"[GRIND] Attivo: b={GRINDING_STEP['b']:.1f}, p={max_picks}, d={GRINDING_STEP['d']} "
                    f"fino a saldo >= {self.format_money(self.grinding_saved_balance)}"
                )
        elif selected_mode_name == "custom" and self.custom_mode:
            await self.set_difficulty(round_difficulty)

        # Start new round - reset picks and prepare for new game
        self.picks = 0
        self.randoms = []
        round_active = True

        self.log_message(f"\n=== Round {self.rounds + 1} ===")
        self.log_message(f"[ROUND] Current bet: {self.format_money(self.bet)}")

        # Press play to start the round and immediately deduct cash
        await self.play_or_collect()
        self.log_message(f"[ROUND] Started round - Cash deducted: {self.format_money(self.bet)}")
        self.current_cash -= self.bet
        self.current_cash = round(self.current_cash, 2)
        self.log_message(f"💸 New Balance: {self.format_money(self.current_cash)}")

        # Keep picking tiles until we get max_picks blues (win) or 1 red (lose)
        while round_active and self.picks < max_picks:
            # Check for escape key press during round
            if self.escape_pressed:
                self.log_message("[STOP] Game stopped by escape key during round")
                round_active = False
                break

            # Generate random tile number
            tile_number = self.generate_random_tile()

            # Wait for game to process
            await asyncio.sleep(self.sleep_after_play_var.get())

            # Click on the corresponding tile
            await self.click_tile(tile_number)
            await asyncio.sleep(self.sleep_after_tile_click_var.get())

            # Check color of the revealed tile with retry mechanism
            color_detected = False
            retry_count = 0

            while not color_detected:
                if self.escape_pressed:
                    self.log_message("[STOP] Game stopped by escape key during color detection")
                    round_active = False
                    break

                # Get the position of the tile we just clicked
                clicked_tile_position = self.tiles[tile_number]
                color = self._read_color_at_point_legacy(clicked_tile_position)

                # Debug: log raw RGB of each tile — utile per calibrare i range di colore
                # self.log_message(
                #     f"[COLOR] Tile {tile_number} ({clicked_tile_position.x}, {clicked_tile_position.y}): "
                #     f"RGB({color['r']}, {color['g']}, {color['b']})"
                # )

                if self.is_color_in_range_blue(color, self.target_blue):
                    # BLUE tile found
                    self.log_message(f"[HIT] Tile {tile_number} is BLUE")
                    self.picks += 1
                    color_detected = True

                    # Check if we got max_picks blues (WIN)
                    if self.picks >= max_picks:
                        self.log_message(f"[WIN] {max_picks} BLUES! ROUND WON!")

                        # Press collect to get winnings
                        await self.play_or_collect()

                        # Increase cash by bet times multiplier (we win!)
                        win_amount = self.bet * multiplier
                        self.current_cash += win_amount
                        self.current_cash = round(self.current_cash, 2)
                        self.total_win += win_amount
                        self.total_win = round(self.total_win, 2)

                        self.log_message(
                            f"[WIN] 💰 Won {self.format_money(win_amount)}! New balance: {self.format_money(self.current_cash)} 💰"
                        )

                        # Update highest cash
                        if self.current_cash > self.highest_cash:
                            self.highest_cash = round(self.current_cash, 2)

                        if self.grinding_active:
                            if self.grinding_saved_balance is not None and self.current_cash >= self.grinding_saved_balance:
                                # Grinding completed: target balance recovered
                                self.grinding_active = False
                                self.tries = 0
                                self.picks = 0

                                min_bet = self._get_min_bet_for_selected_mode()
                                await self.set_bet_value(min_bet)
                                self.log_message(
                                    f"[GRIND] Completato: saldo recuperato ({self.format_money(self.current_cash)} >= "
                                    f"{self.format_money(self.grinding_saved_balance)}). Bet tornata al minimo."
                                )
                            else:
                                await self.set_bet_value(GRINDING_STEP["b"])
                                target_text = self.format_money(self.grinding_saved_balance or 0)
                                self.log_message(
                                    f"[GRIND] Saldo attuale {self.format_money(self.current_cash)} "
                                    f"(target {target_text}), continuo sullo step fisso."
                                )
                        else:
                            # Reset betting strategy after win - back to step 0
                            self.tries = 0
                            self.picks = 0

                            min_bet = self._get_min_bet_for_selected_mode()
                            await self.set_bet_value(min_bet)
                            self.log_message(f"[WIN] Bet reset to minimum: {self.format_money(self.bet)}")

                        # Reset for next round
                        round_active = False

                    else:
                        # Continue picking - we have less than max_picks blues
                        self.log_message(f"Got {self.picks} blue(s), need {max_picks - self.picks} more...")

                elif self.is_color_in_range_red(color, self.target_red):
                    # RED tile found - ROUND LOST
                    self.log_message(f"[LOSS] Tile {tile_number} is RED - ROUND LOST!")
                    color_detected = True
                    self.log_message(f"💸 New Balance: {self.format_money(self.current_cash)} 💸")

                    # In grinding mode, save cash when losing at the lowest step.
                    if grinding_enabled and not self.grinding_active and step_idx == 0:
                        acceptable_range = self.grinding_range_var.get()
                        self.grinding_saved_balance = round(self.highest_cash - acceptable_range, 2)

                    # Cash already deducted when round started, just update strategy
                    self.tries += 1

                    # Reset picks and end round
                    self.picks = 0
                    round_active = False

                    # Activate grinding after a loss on the highest step with bet=20.0
                    reached_top_step = (
                        step_idx is not None and
                        max_step_idx is not None and
                        step_idx >= max_step_idx
                    )
                    if (
                        grinding_enabled and
                        not self.grinding_active and
                        reached_top_step and
                        round(self.bet, 2) == round(GRINDING_STEP["b"], 2) and
                        self.grinding_saved_balance is not None
                    ):
                        self.grinding_active = True
                        self.log_message(
                            f"[GRIND] Attivato dopo perdita all'ultimo step: ripeto b={GRINDING_STEP['b']:.1f}, "
                            f"p={self.max_picks_var.get()}, d={GRINDING_STEP['d']} fino a saldo >= "
                            f"{self.format_money(self.grinding_saved_balance)}"
                        )

                    # Update betting strategy after showing round results
                    await asyncio.sleep(self.sleep_after_result_var.get())

                    if self.grinding_active:
                        await self.set_difficulty(GRINDING_STEP["d"])
                        await self.set_bet_value(GRINDING_STEP["b"])
                    elif selected_mode_name == "custom" and self.custom_mode:
                        target_bet = self._get_target_bet_for_try(self.tries, selected_mode_name)
                        await self.set_bet_value(target_bet)
                    elif selected_mode_name in self.betting_modes:
                        target_bet = self._get_target_bet_for_try(self.tries, selected_mode_name)
                        await self.set_bet_value(target_bet)

                    if self.bet > self.highest_bet:
                        self.highest_bet = round(self.bet, 2)

                    self.log_message(f"[LOSS] Bet aggiornato a: {self.format_money(self.bet)} (try #{self.tries})")

                    # Calculate loss
                    self.loss = max(0, round(self.highest_cash - self.current_cash, 2))
                    if self.loss >= self.max_loss_var.get():
                        self.log_message("[STOP] Reached maximum loss!")
                        self.game_running = False
                        round_active = False
                        break

                else:
                    # Unknown color detected - retry until a known color is found
                    retry_count += 1
                    self.log_message(f"[COLOR] Tile {tile_number} - Unknown color (attempt {retry_count})")
                    self.log_message("   Expected: Blue RGB(1,108,238) or Red RGB(200,13,1)")
                    self.log_message(f"   Actual: RGB({color['r']}, {color['g']}, {color['b']})")
                    self.log_message(f"   Tolerance used: {self.color_detector.tolerance}")
                    self.log_message(f"   Waiting {self.sleep_color_retry_var.get()} second(s) and retrying color detection...")
                    await asyncio.sleep(self.sleep_color_retry_var.get())

        # Round completed, increment round counter
        self.rounds += 1

    async def simulate_game_round(self):
        """Simulate a game round (placeholder)"""
        self.rounds += 1
        self.log_message(f"\n=== Round {self.rounds} ===")
        
        # This is where the actual game automation would go
        # For now, just simulate random outcomes
        await asyncio.sleep(1)  # Simulate game delay
        
        if random.random() < 0.6:  # 60% win chance for testing
            self.log_message("🎉 Round WON!")
            sim_multiplier = self.get_win_multiplier(self.difficulty_var.get(), self.max_picks_var.get())
            self.current_cash += self.bet * sim_multiplier
            self.tries = 0
            
            min_bet = self._get_min_bet_for_selected_mode()
            
            # Reset bet to minimum after win (same as playM.py logic)
            while self.bet > min_bet:
                # Simulate decrease_bet logic without actual clicking
                current_index = self.bet_values.index(self.bet) if self.bet in self.bet_values else 0
                self.bet = round(self.bet_values[max(current_index - 1, 0)], 2)
            self.log_message(f"🎯 WIN! Bet reset to minimum: {self.format_money(self.bet)}")
        else:
            self.log_message("💸 Round LOST!")
            self.current_cash -= self.bet
            self.tries += 1
            
            # Get betting strategy from selected mode (same logic as real game mode)
            selected_mode_name = self.mode_var.get()
            if selected_mode_name in self.betting_modes:
                target_bet = self._get_target_bet_for_try(self.tries, selected_mode_name)
                old_bet = self.bet
                
                # Simulate stepping through bet increases (same as real game mode)
                while self.bet < target_bet:
                    # Simulate increase_bet logic without actual clicking
                    current_index = self.bet_values.index(self.bet) if self.bet in self.bet_values else self.tries
                    self.bet = round(self.bet_values[min(current_index + 1, len(self.bet_values) - 1)], 2)
                
                self.log_message(f"Bet updated from {selected_mode_name} mode: {self.format_money(old_bet)} → {self.format_money(self.bet)} (try #{self.tries})")
                
                # Update highest bet tracking
                if self.bet > self.highest_bet:
                    self.highest_bet = round(self.bet, 2)
            else:
                # Fallback to simple increase if mode not found
                bet_multipliers = list(BETTING_MODES.get("normal", [0.1]))
                if self.tries < len(bet_multipliers):
                    target_bet = bet_multipliers[self.tries]
                    old_bet = self.bet
                    
                    # Simulate stepping through bet increases
                    while self.bet < target_bet:
                        current_index = self.bet_values.index(self.bet) if self.bet in self.bet_values else self.tries
                        self.bet = round(self.bet_values[min(current_index + 1, len(self.bet_values) - 1)], 2)
                    
                    # Update highest bet tracking for fallback case too
                    if self.bet > self.highest_bet:
                        self.highest_bet = round(self.bet, 2)
        
        # Update highest values
        if self.current_cash > self.highest_cash:
            self.highest_cash = self.current_cash
        # Note: highest_bet already updated above in the betting logic
        
        self.loss = max(0, self.highest_cash - self.current_cash)
    
    def update_stats_display(self):
        """Update the statistics display"""
        self.lowest_cash = round(min(self.lowest_cash, self.current_cash), 2)
        self.current_cash_label.config(text=self.format_money(self.current_cash))
        self.highest_cash_label.config(text=self.format_money(self.highest_cash))
        self.lowest_cash_label.config(text=self.format_money(self.lowest_cash))
        self.current_bet_label.config(text=self.format_money(self.bet))
        self.highest_bet_label.config(text=self.format_money(self.highest_bet))
        self.rounds_label.config(text=str(self.rounds))
        self.tries_label.config(text=str(self.tries))
        self.loss_label.config(text=self.format_money(self.loss))
        self.total_win_label.config(text=self.format_money(self.total_win))  # Add this line
    
    def format_money(self, value):
        """Thin wrapper around game_config.format_money for instance method calls."""
        return format_money(value)
    
    def log_message(self, message):
        """Add a message to the status log"""
        timestamp = time.strftime("%H:%M:%S")
        full_message = f"[{timestamp}] {message}\n"
        self.root.after(0, lambda: self.status_text.insert(tk.END, full_message))
        self.root.after(0, lambda: self.status_text.see(tk.END))
    
    def clear_log(self):
        """Clear the status log"""
        if messagebox.askyesno("Clear Log", "Are you sure you want to clear the entire log?"):
            self.status_text.delete(1.0, tk.END)
            self.log_message("📝 Log cleared")
    
    def export_log(self):
        """Export the current log to a text file"""
        from tkinter import filedialog
        import datetime
        
        # Get current log content
        log_content = self.status_text.get(1.0, tk.END)
        
        if not log_content.strip():
            messagebox.showwarning("Empty Log", "No log content to export!")
            return
        
        # Generate default filename with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"gratta_e_vinci_log_{timestamp}.txt"
        
        # Ask user for save location
        filename = filedialog.asksaveasfilename(
            title="Export Log",
            defaultextension=".txt",
            initialfile=default_filename,
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                # Add header with export info
                export_content = f"Gratta-e-Vinci Automation Log Export\n"
                export_content += f"Exported on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                export_content += f"=" * 50 + "\n\n"
                export_content += log_content
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(export_content)
                
                messagebox.showinfo("Export Successful", f"Log exported to:\n{filename}")
                self.log_message(f"📤 Log exported to: {filename}")
                
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export log:\n{str(e)}")
                self.log_message(f"❌ Log export failed: {str(e)}")
    
    def open_custom_mode_editor(self):
        """Open the custom betting mode editor"""
        editor = tk.Toplevel(self.root)
        editor.title("Custom Betting Mode Editor")
        editor.geometry("500x700")
        editor.resizable(True, True)
        editor.transient(self.root)
        editor.grab_set()

        ttk.Label(editor, text="Custom Betting Mode Editor", font=("TkDefaultFont", 12, "bold")).pack(pady=(10, 4))
        instructions = (
            "Una riga = uno step.   Formato:  b=<bet>, p=<picks>, d=<difficulty>\n"
            "  b = importo scommessa (valori validi della lista bet_values)\n"
            "  p = numero di pick (1, 2, 3, 4)\n"
            "  d = difficoltà (low, medium, high)\n"
            "In caso di vittoria → ritorna allo step 1.   In caso di perdita → avanza allo step successivo."
        )
        ttk.Label(editor, text=instructions, justify=tk.LEFT, foreground="gray").pack(padx=15, pady=(0, 8), anchor=tk.W)

        text_frame = ttk.Frame(editor)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 8))
        text_widget = scrolledtext.ScrolledText(text_frame, height=14, font=("Courier", 10))
        text_widget.pack(fill=tk.BOTH, expand=True)

        # Popola con il custom_mode corrente
        for step in self.custom_mode:
            text_widget.insert(tk.END, f"b={step['b']}, p={step['p']}, d={step['d']}\n")

        def validate_and_save():
            content = text_widget.get("1.0", tk.END).strip()
            if not content:
                messagebox.showerror("Errore", "Il custom mode non può essere vuoto.", parent=editor)
                return
            new_mode = []
            all_errors = []
            for i, line in enumerate(content.splitlines(), 1):
                line = line.strip()
                if not line:
                    continue
                line_errors = []
                try:
                    parts = {}
                    for token in line.split(","):
                        k, v = token.strip().split("=")
                        parts[k.strip()] = v.strip()
                    b = round(float(parts["b"]), 2)
                    p = int(parts["p"])
                    d = parts["d"].lower()
                    if b not in self.bet_values:
                        line_errors.append(f"Riga {i}: b={b} non è un valore valido")
                    if p not in (1, 2, 3, 4):
                        line_errors.append(f"Riga {i}: p={p} deve essere tra 1 e 4")
                    if d not in ("low", "medium", "high"):
                        line_errors.append(f"Riga {i}: d={d} deve essere low, medium o high")
                    if not line_errors:
                        new_mode.append({"b": b, "p": p, "d": d})
                    else:
                        all_errors.extend(line_errors)
                except Exception:
                    all_errors.append(f"Riga {i}: formato non valido — usa: b=0.1, p=2, d=low")
            if all_errors:
                messagebox.showerror("Errori di validazione", "\n".join(all_errors), parent=editor)
                return
            if len(new_mode) < 1:
                messagebox.showerror("Errore", "Almeno uno step è richiesto.", parent=editor)
                return
            self.custom_mode = new_mode
            self.update_betting_preview()
            # Auto-salva sul JSON così le modifiche persistono al riavvio
            self._save_custom_mode_silent()
            messagebox.showinfo("Salvato", f"Custom mode salvato con {len(new_mode)} step!", parent=editor)
            editor.destroy()

        btn_frame = ttk.Frame(editor)
        btn_frame.pack(fill=tk.X, padx=15, pady=(0, 10))
        ttk.Button(btn_frame, text="💾 Salva", command=validate_and_save).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="❌ Annulla", command=editor.destroy).pack(side=tk.LEFT, padx=5)

        editor.update_idletasks()
        x = (editor.winfo_screenwidth() - editor.winfo_width()) // 2
        y = (editor.winfo_screenheight() - editor.winfo_height()) // 2
        editor.geometry(f"+{x}+{y}")

    def _save_custom_mode_silent(self):
        """Salva il custom_mode nel JSON senza mostrare messagebox."""
        try:
            self.settings_manager.save_custom_mode(
                self.settings_path,
                self.custom_mode,
                self.mode_var.get(),
                self.difficulty_var.get(),
            )
            self.log_message("💾 Custom mode salvato automaticamente nel JSON")
        except Exception as e:
            self.log_message(f"⚠️ Errore salvataggio automatico custom mode: {e}")

    def _collect_settings_payload(self):
        return {
            "starting_cash": self.starting_cash_var.get(),
            "target_win": self.target_win_var.get(),
            "max_loss": self.max_loss_var.get(),
            "max_rounds": self.max_rounds_var.get(),
            "max_picks": self.max_picks_var.get(),
            "mode": self.mode_var.get(),
            "wait_selected": self.wait_selected_var.get(),
            "grinding_mode": self.grinding_mode_var.get(),
            "grinding_range": self.grinding_range_var.get(),
            "grinding_p_random": self.grinding_p_random_var.get(),
            "play_x": self.play_x_var.get(),
            "play_y": self.play_y_var.get(),
            "raise_x": self.raise_x_var.get(),
            "raise_y": self.raise_y_var.get(),
            "lower_x": self.lower_x_var.get(),
            "lower_y": self.lower_y_var.get(),
            "raise_diff_x": self.raise_diff_x_var.get(),
            "raise_diff_y": self.raise_diff_y_var.get(),
            "lower_diff_x": self.lower_diff_x_var.get(),
            "lower_diff_y": self.lower_diff_y_var.get(),
            "difficulty": self.difficulty_var.get(),
            "custom_mode": self.custom_mode,
            "tiles": {str(num): [x_var.get(), y_var.get()] for num, (x_var, y_var) in self.tile_vars.items()},
            "betting_modes": self.betting_modes,
            "init_steps": self.init_steps,
            "sleep_play_or_collect": self.sleep_play_or_collect_var.get(),
            "sleep_increase_bet": self.sleep_increase_bet_var.get(),
            "sleep_decrease_bet": self.sleep_decrease_bet_var.get(),
            "sleep_decrease_bet_force": self.sleep_decrease_bet_force_var.get(),
            "sleep_decrease_diff_force": self.sleep_decrease_diff_force_var.get(),
            "sleep_set_difficulty": self.sleep_set_difficulty_var.get(),
            "sleep_click_tile": self.sleep_click_tile_var.get(),
            "sleep_after_play": self.sleep_after_play_var.get(),
            "sleep_after_tile_click": self.sleep_after_tile_click_var.get(),
            "sleep_between_rounds": self.sleep_between_rounds_var.get(),
            "sleep_after_result": self.sleep_after_result_var.get(),
            "sleep_color_retry": self.sleep_color_retry_var.get(),
            "color_tolerance": self.color_tolerance_var.get(),
            "sleep_init_raise_diff": self.sleep_init_raise_diff_var.get(),
            "sleep_init_lower_diff": self.sleep_init_lower_diff_var.get(),
            "sleep_init_click": self.sleep_init_click_var.get(),
        }

    def _apply_settings_payload(self, settings):
        self.starting_cash_var.set(settings.get("starting_cash", 2001.50))
        self.target_win_var.set(settings.get("target_win", 2100.0))
        self.max_loss_var.set(settings.get("max_loss", 10.0))
        self.max_rounds_var.set(settings.get("max_rounds", 100))
        self.max_picks_var.set(settings.get("max_picks", 3))
        self.mode_var.set(settings.get("mode", "normal"))
        self.wait_selected_var.set(settings.get("wait_selected", False))
        self.grinding_mode_var.set(settings.get("grinding_mode", False))
        self.grinding_range_var.set(settings.get("grinding_range", 0.5))
        self.grinding_p_random_var.set(settings.get("grinding_p_random", False))
        self._on_grinding_toggle()
        self.play_x_var.set(settings.get("play_x", 2196))
        self.play_y_var.set(settings.get("play_y", 1616))
        self.raise_x_var.set(settings.get("raise_x", 1900))
        self.raise_y_var.set(settings.get("raise_y", 1740))
        self.lower_x_var.set(settings.get("lower_x", 1519))
        self.lower_y_var.set(settings.get("lower_y", 1740))
        self.raise_diff_x_var.set(settings.get("raise_diff_x", 0))
        self.raise_diff_y_var.set(settings.get("raise_diff_y", 0))
        self.lower_diff_x_var.set(settings.get("lower_diff_x", 0))
        self.lower_diff_y_var.set(settings.get("lower_diff_y", 0))
        self.difficulty_var.set(settings.get("difficulty", "low"))
        self.sleep_play_or_collect_var.set(settings.get("sleep_play_or_collect", 1.0))
        self.sleep_increase_bet_var.set(settings.get("sleep_increase_bet", 1.0))
        self.sleep_decrease_bet_var.set(settings.get("sleep_decrease_bet", 1.0))
        self.sleep_decrease_bet_force_var.set(settings.get("sleep_decrease_bet_force", 0.05))
        self.sleep_decrease_diff_force_var.set(settings.get("sleep_decrease_diff_force", 0.05))
        self.sleep_set_difficulty_var.set(settings.get("sleep_set_difficulty", 0.5))
        self.sleep_click_tile_var.set(settings.get("sleep_click_tile", 1.0))
        self.sleep_after_play_var.set(settings.get("sleep_after_play", 1.0))
        self.sleep_after_tile_click_var.set(settings.get("sleep_after_tile_click", 1.0))
        self.sleep_between_rounds_var.set(settings.get("sleep_between_rounds", 1.0))
        self.sleep_after_result_var.set(settings.get("sleep_after_result", 2.0))
        self.sleep_color_retry_var.set(settings.get("sleep_color_retry", 1.0))
        self.color_tolerance_var.set(settings.get("color_tolerance", COLOR_TOLERANCE))
        self.color_detector.tolerance = int(self.color_tolerance_var.get())
        self.sleep_init_raise_diff_var.set(settings.get("sleep_init_raise_diff", 0.4))
        self.sleep_init_lower_diff_var.set(settings.get("sleep_init_lower_diff", 0.4))
        self.sleep_init_click_var.set(settings.get("sleep_init_click", 0.3))
        saved_custom = settings.get("custom_mode", [])
        if saved_custom and isinstance(saved_custom, list):
            self.custom_mode = saved_custom
        tiles = settings.get("tiles", {})
        for tile_str, coords in tiles.items():
            tile_num = int(tile_str)
            if tile_num in self.tile_vars:
                self.tile_vars[tile_num][0].set(coords[0])
                self.tile_vars[tile_num][1].set(coords[1])
        saved_modes = settings.get("betting_modes", {})
        if saved_modes:
            for mode_name, mode_values in saved_modes.items():
                if isinstance(mode_values, list) and all(isinstance(v, (int, float)) for v in mode_values):
                    self.betting_modes[mode_name] = [round(v, 2) for v in mode_values]
        loaded_steps = settings.get("init_steps", None)
        if loaded_steps is not None and isinstance(loaded_steps, list):
            self.init_steps = loaded_steps
            if hasattr(self, 'init_tree'):
                self.refresh_init_tree()
        self._on_mode_changed_settings()
        self._on_grinding_toggle()

    def on_save_settings(self):
        """Save settings using SettingsManager."""
        payload = self._collect_settings_payload()
        errors = self.settings_manager.validate(payload)
        if errors:
            messagebox.showerror("Error", "\n".join(errors))
            return
        try:
            self.settings_manager.save_settings(self.settings_path, payload)
            messagebox.showinfo("Saved", "Settings saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")

    def on_load_settings(self):
        """Load settings using SettingsManager."""
        try:
            settings = self.settings_manager.load_settings(self.settings_path)
            self._apply_settings_payload(settings)
            self.log_message("Settings loaded successfully!")
        except Exception as e:
            self.log_message(f"Failed to load settings: {e}")
            self._on_mode_changed_settings()
            self._on_grinding_toggle()

    def _save_settings_legacy(self):
        """Save settings to file"""
        settings = {
            "starting_cash": self.starting_cash_var.get(),
            "target_win": self.target_win_var.get(),
            "max_loss": self.max_loss_var.get(),
            "max_rounds": self.max_rounds_var.get(),
            "max_picks": self.max_picks_var.get(),
            "mode": self.mode_var.get(),
            "wait_selected": self.wait_selected_var.get(),
            "grinding_mode": self.grinding_mode_var.get(),
            "grinding_range": self.grinding_range_var.get(),
            "grinding_p_random": self.grinding_p_random_var.get(),
            "play_x": self.play_x_var.get(),
            "play_y": self.play_y_var.get(),
            "raise_x": self.raise_x_var.get(),
            "raise_y": self.raise_y_var.get(),
            "lower_x": self.lower_x_var.get(),
            "lower_y": self.lower_y_var.get(),
            "raise_diff_x": self.raise_diff_x_var.get(),
            "raise_diff_y": self.raise_diff_y_var.get(),
            "lower_diff_x": self.lower_diff_x_var.get(),
            "lower_diff_y": self.lower_diff_y_var.get(),
            "difficulty": self.difficulty_var.get(),
            "custom_mode": self.custom_mode,
            "tiles": {str(num): [x_var.get(), y_var.get()] for num, (x_var, y_var) in self.tile_vars.items()},
            "betting_modes": self.betting_modes,
            "init_steps": self.init_steps,
            "sleep_play_or_collect": self.sleep_play_or_collect_var.get(),
            "sleep_increase_bet": self.sleep_increase_bet_var.get(),
            "sleep_decrease_bet": self.sleep_decrease_bet_var.get(),
            "sleep_decrease_bet_force": self.sleep_decrease_bet_force_var.get(),
            "sleep_decrease_diff_force": self.sleep_decrease_diff_force_var.get(),
            "sleep_set_difficulty": self.sleep_set_difficulty_var.get(),
            "sleep_click_tile": self.sleep_click_tile_var.get(),
            "sleep_after_play": self.sleep_after_play_var.get(),
            "sleep_after_tile_click": self.sleep_after_tile_click_var.get(),
            "sleep_between_rounds": self.sleep_between_rounds_var.get(),
            "sleep_after_result": self.sleep_after_result_var.get(),
            "sleep_color_retry": self.sleep_color_retry_var.get(),
            "sleep_init_raise_diff": self.sleep_init_raise_diff_var.get(),
            "sleep_init_lower_diff": self.sleep_init_lower_diff_var.get(),
            "sleep_init_click": self.sleep_init_click_var.get()
        }
        
        try:
            with open("gratta_settings.json", "w") as f:
                json.dump(settings, f, indent=2)
            messagebox.showinfo("Saved", "Settings saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
    
    def _load_settings_legacy(self):
        """Load settings from file"""
        try:
            if os.path.exists("gratta_settings.json"):
                with open("gratta_settings.json", "r") as f:
                    settings = json.load(f)
                
                self.starting_cash_var.set(settings.get("starting_cash", 2001.50))
                self.target_win_var.set(settings.get("target_win", 2100.0))
                self.max_loss_var.set(settings.get("max_loss", 10.0))
                self.max_rounds_var.set(settings.get("max_rounds", 100))
                self.max_picks_var.set(settings.get("max_picks", 3))
                self.mode_var.set(settings.get("mode", "normal"))
                self.wait_selected_var.set(settings.get("wait_selected", False))
                self.grinding_mode_var.set(settings.get("grinding_mode", False))
                self.grinding_range_var.set(settings.get("grinding_range", 0.5))
                self.grinding_p_random_var.set(settings.get("grinding_p_random", False))
                self._on_grinding_toggle()

                self.play_x_var.set(settings.get("play_x", 2196))
                self.play_y_var.set(settings.get("play_y", 1616))
                self.raise_x_var.set(settings.get("raise_x", 1900))
                self.raise_y_var.set(settings.get("raise_y", 1740))
                self.lower_x_var.set(settings.get("lower_x", 1519))
                self.lower_y_var.set(settings.get("lower_y", 1740))
                self.raise_diff_x_var.set(settings.get("raise_diff_x", 0))
                self.raise_diff_y_var.set(settings.get("raise_diff_y", 0))
                self.lower_diff_x_var.set(settings.get("lower_diff_x", 0))
                self.lower_diff_y_var.set(settings.get("lower_diff_y", 0))
                self.difficulty_var.set(settings.get("difficulty", "low"))
                self.sleep_play_or_collect_var.set(settings.get("sleep_play_or_collect", 1.0))
                self.sleep_increase_bet_var.set(settings.get("sleep_increase_bet", 1.0))
                self.sleep_decrease_bet_var.set(settings.get("sleep_decrease_bet", 1.0))
                self.sleep_decrease_bet_force_var.set(settings.get("sleep_decrease_bet_force", 0.05))
                self.sleep_decrease_diff_force_var.set(settings.get("sleep_decrease_diff_force", 0.05))
                self.sleep_set_difficulty_var.set(settings.get("sleep_set_difficulty", 0.5))
                self.sleep_click_tile_var.set(settings.get("sleep_click_tile", 1.0))
                self.sleep_after_play_var.set(settings.get("sleep_after_play", 1.0))
                self.sleep_after_tile_click_var.set(settings.get("sleep_after_tile_click", 1.0))
                self.sleep_between_rounds_var.set(settings.get("sleep_between_rounds", 1.0))
                self.sleep_after_result_var.set(settings.get("sleep_after_result", 2.0))
                self.sleep_color_retry_var.set(settings.get("sleep_color_retry", 1.0))
                self.sleep_init_raise_diff_var.set(settings.get("sleep_init_raise_diff", 0.4))
                self.sleep_init_lower_diff_var.set(settings.get("sleep_init_lower_diff", 0.4))
                self.sleep_init_click_var.set(settings.get("sleep_init_click", 0.3))

                # Load custom mode
                saved_custom = settings.get("custom_mode", [])
                if saved_custom and isinstance(saved_custom, list):
                    self.custom_mode = saved_custom

                # Load tile positions
                tiles = settings.get("tiles", {})
                for tile_str, coords in tiles.items():
                    tile_num = int(tile_str)
                    if tile_num in self.tile_vars:
                        self.tile_vars[tile_num][0].set(coords[0])
                        self.tile_vars[tile_num][1].set(coords[1])
                
                # Load betting modes
                saved_modes = settings.get("betting_modes", {})
                if saved_modes:
                    # Validate and load betting modes
                    for mode_name, mode_values in saved_modes.items():
                        if isinstance(mode_values, list) and all(isinstance(v, (int, float)) for v in mode_values):
                            self.betting_modes[mode_name] = [round(v, 2) for v in mode_values]
                    self.log_message("Betting modes loaded from settings")

                # Load initialization steps
                loaded_steps = settings.get("init_steps", None)
                if loaded_steps is not None and isinstance(loaded_steps, list):
                    self.init_steps = loaded_steps
                    if hasattr(self, 'init_tree'):
                        self.refresh_init_tree()

                self.log_message("Settings loaded successfully!")
        except Exception as e:
            self.log_message(f"Failed to load settings: {e}")
        self._on_mode_changed_settings()
        self._on_grinding_toggle()
    
    def reset_settings(self):
        """Reset settings to defaults"""
        if messagebox.askyesno("Reset", "Reset all settings to defaults?"):
            # Reset to default values
            self.starting_cash_var.set(2001.50)
            self.target_win_var.set(2100.0)
            self.max_loss_var.set(10.0)
            self.max_rounds_var.set(100)
            self.max_picks_var.set(3)
            self.mode_var.set("normal")
            self.difficulty_var.set("low")
            self.wait_selected_var.set(False)
            self.grinding_mode_var.set(False)
            self.grinding_range_var.set(0.5)
            self.grinding_p_random_var.set(False)
            self.color_tolerance_var.set(COLOR_TOLERANCE)
            self.color_detector.tolerance = int(self.color_tolerance_var.get())
            self._on_grinding_toggle()

            self.play_x_var.set(2196)
            self.play_y_var.set(1616)
            self.raise_x_var.set(1900)
            self.raise_y_var.set(1740)
            self.lower_x_var.set(1519)
            self.lower_y_var.set(1740)
            
            self.auto_generate_grid()
            self._on_mode_changed_settings()
            messagebox.showinfo("Reset", "Settings reset to defaults!")
    
    # ---- Bulk Test Tab ----

    def create_bulk_test_tab(self, parent):
        """Create the Bulk Test tab with scrollable content."""
        canvas = tk.Canvas(parent)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # --- Controls ---
        ctrl_frame = ttk.LabelFrame(scroll_frame, text="Bulk Test", padding=10)
        ctrl_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(ctrl_frame, text="Ripetizioni:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.bulk_n_runs_entry = ttk.Entry(ctrl_frame, textvariable=self.bulk_n_runs_var, width=10)
        self.bulk_n_runs_entry.grid(row=0, column=1, padx=5, pady=2)

        self.bulk_show_logs_check = ttk.Checkbutton(ctrl_frame, text="Mostra log", variable=self.bulk_show_logs_var,
                                                     command=self._toggle_bulk_log_frame)
        self.bulk_show_logs_check.grid(row=0, column=2, padx=10, pady=2)

        btn_frame = ttk.Frame(ctrl_frame)
        btn_frame.grid(row=1, column=0, columnspan=4, pady=5)
        self.bulk_start_button = ttk.Button(btn_frame, text="AVVIA BULK TEST", command=self.start_bulk_test)
        self.bulk_start_button.pack(side=tk.LEFT, padx=5)
        self.bulk_stop_button = ttk.Button(btn_frame, text="FERMA", command=self.stop_bulk_test, state="disabled")
        self.bulk_stop_button.pack(side=tk.LEFT, padx=5)

        # Progress
        self.bulk_progress_var = tk.DoubleVar(value=0)
        self.bulk_progress_bar = ttk.Progressbar(ctrl_frame, variable=self.bulk_progress_var, maximum=100, length=400)
        self.bulk_progress_bar.grid(row=2, column=0, columnspan=3, sticky=tk.EW, pady=2, padx=5)
        self.bulk_progress_label = ttk.Label(ctrl_frame, text="0/0 (0%)")
        self.bulk_progress_label.grid(row=2, column=3, padx=5)
        self.bulk_status_label = ttk.Label(ctrl_frame, text="In attesa")
        self.bulk_status_label.grid(row=3, column=0, columnspan=4, sticky=tk.W, pady=2)

        # --- Log (optional) ---
        self.bulk_log_frame = ttk.LabelFrame(scroll_frame, text="Log", padding=5)
        self.bulk_log_frame.pack(fill=tk.X, padx=5, pady=5)
        self.bulk_log_text = scrolledtext.ScrolledText(self.bulk_log_frame, height=8, state="normal",
                                                        font=("Courier", 9))
        self.bulk_log_text.pack(fill=tk.X)

        # --- Advanced Params ---
        adv_frame = ttk.LabelFrame(scroll_frame, text="Parametri Avanzati", padding=10)
        adv_frame.pack(fill=tk.X, padx=5, pady=5)

        # WIN_MULTIPLIERS grid
        ttk.Label(adv_frame, text="WIN_MULTIPLIERS:", font=("", 10, "bold")).grid(row=0, column=0, columnspan=5,
                                                                                    sticky=tk.W, pady=(0, 5))
        for col_i, p in enumerate([1, 2, 3, 4]):
            ttk.Label(adv_frame, text=f"p={p}").grid(row=1, column=col_i + 1, padx=5)
        for row_i, d in enumerate(["low", "medium", "high"]):
            ttk.Label(adv_frame, text=f"{d}:").grid(row=row_i + 2, column=0, sticky=tk.W, padx=5)
            for col_i, p in enumerate([1, 2, 3, 4]):
                ttk.Entry(adv_frame, textvariable=self.bulk_win_multiplier_vars[d][p], width=6).grid(
                    row=row_i + 2, column=col_i + 1, padx=3, pady=1)

        # MINE_CONFIG
        ttk.Label(adv_frame, text="MINE_CONFIG (mines per difficulty):", font=("", 10, "bold")).grid(
            row=6, column=0, columnspan=5, sticky=tk.W, pady=(10, 5))
        for col_i, d in enumerate(["low", "medium", "high"]):
            ttk.Label(adv_frame, text=f"{d}:").grid(row=7, column=col_i * 2, sticky=tk.E, padx=2)
            ttk.Spinbox(adv_frame, from_=0, to=24, textvariable=self.bulk_mine_config_vars[d], width=4).grid(
                row=7, column=col_i * 2 + 1, padx=2)

        # BETTING_MODES / BET_VALUES buttons
        btn_adv_frame = ttk.Frame(adv_frame)
        btn_adv_frame.grid(row=8, column=0, columnspan=5, pady=10)
        ttk.Button(btn_adv_frame, text="Modifica sequenze BETTING_MODES",
                   command=self.open_bulk_betting_modes_editor).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_adv_frame, text="Modifica BET_VALUES",
                   command=self.open_bulk_bet_values_editor).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_adv_frame, text="Ripristina defaults",
                   command=self.reset_bulk_advanced_params).pack(side=tk.LEFT, padx=5)

        # --- Export ---
        export_frame = ttk.Frame(scroll_frame)
        export_frame.pack(fill=tk.X, padx=5, pady=10)
        self.bulk_export_button = ttk.Button(export_frame, text="ESPORTA EXCEL", command=self.export_bulk_excel,
                                              state="disabled")
        self.bulk_export_button.pack()

    def _toggle_bulk_log_frame(self):
        if self.bulk_show_logs_var.get():
            self.bulk_log_frame.pack(fill=tk.X, padx=5, pady=5)
        else:
            self.bulk_log_frame.pack_forget()

    # ---- Bulk Test Control ----

    def start_bulk_test(self):
        n = self.bulk_n_runs_var.get()
        if n <= 0:
            messagebox.showerror("Errore", "Il numero di ripetizioni deve essere > 0")
            return
        self.bulk_test_running = True
        self.bulk_test_stop = False
        self._bulk_results = None
        self.bulk_start_button.config(state="disabled")
        self.bulk_stop_button.config(state="normal")
        self.bulk_export_button.config(state="disabled")
        self.bulk_progress_var.set(0)
        self.bulk_progress_label.config(text=f"0/{n} (0%)")
        self.bulk_status_label.config(text="In esecuzione...")
        self.bulk_log_text.delete("1.0", tk.END)
        threading.Thread(target=self._bulk_test_worker, daemon=True).start()

    def stop_bulk_test(self):
        self.bulk_test_stop = True
        self.bulk_status_label.config(text="Interruzione in corso...")

    def _bulk_test_worker(self):
        n = self.bulk_n_runs_var.get()
        try:
            results = self.game_engine.run_bulk_test(
                n_runs=n,
                progress_cb=self._bulk_update_progress,
                log_cb=self._bulk_log_message,
                stop_check=lambda: self.bulk_test_stop,
                show_logs=lambda: self.bulk_show_logs_var.get(),
            )
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Errore Bulk Test", str(e)))
            self.root.after(0, self._on_bulk_test_failed)
            return
        self.root.after(0, lambda: self._on_bulk_test_complete(results))

    def _on_bulk_test_complete(self, results):
        self.bulk_test_running = False
        self._bulk_results = results
        runs = results[4]
        n = self.bulk_n_runs_var.get()
        self.bulk_start_button.config(state="normal")
        self.bulk_stop_button.config(state="disabled")
        self.bulk_export_button.config(state="normal")
        self.bulk_status_label.config(text=f"Completato {runs}/{n} - Pronto per export")

    def _on_bulk_test_failed(self):
        self.bulk_test_running = False
        self.bulk_start_button.config(state="normal")
        self.bulk_stop_button.config(state="disabled")
        self.bulk_status_label.config(text="Errore durante l'esecuzione")

    def _bulk_log_message(self, msg):
        def _do():
            if msg == "__CLEAR__":
                self.bulk_log_text.delete("1.0", tk.END)
            else:
                self.bulk_log_text.insert(tk.END, msg + "\n")
                self.bulk_log_text.see(tk.END)
        self.root.after(0, _do)

    def _bulk_update_progress(self, i, n):
        pct = int(i / n * 100) if n > 0 else 0
        self.root.after(0, lambda: self.bulk_progress_var.set(pct))
        self.root.after(0, lambda: self.bulk_progress_label.config(text=f"{i}/{n} ({pct}%)"))

    def _clear_bulk_log(self):
        self.root.after(0, lambda: self.bulk_log_text.delete("1.0", tk.END))

    # ---- Bulk Advanced Param Editors ----

    def open_bulk_betting_modes_editor(self):
        win = tk.Toplevel(self.root)
        win.title("Modifica BETTING_MODES (Bulk)")
        win.geometry("500x400")
        win.grab_set()

        texts = {}
        for mode_name in ["normal", "medium", "high", "safe"]:
            frame = ttk.LabelFrame(win, text=mode_name, padding=5)
            frame.pack(fill=tk.X, padx=10, pady=5)
            t = tk.Text(frame, height=2, width=60)
            t.insert("1.0", ", ".join(str(v) for v in self.bulk_betting_modes.get(mode_name, [])))
            t.pack(fill=tk.X)
            texts[mode_name] = t

        def on_save():
            for mode_name, t in texts.items():
                raw = t.get("1.0", tk.END).strip()
                if not raw:
                    self.bulk_betting_modes[mode_name] = []
                    continue
                try:
                    vals = [float(x.strip()) for x in raw.split(",") if x.strip()]
                    if any(v <= 0 for v in vals):
                        raise ValueError("Valori devono essere positivi")
                    self.bulk_betting_modes[mode_name] = vals
                except ValueError as e:
                    messagebox.showerror("Errore", f"Errore in {mode_name}: {e}")
                    return
            win.destroy()

        ttk.Button(win, text="Salva", command=on_save).pack(pady=10)

    def open_bulk_bet_values_editor(self):
        win = tk.Toplevel(self.root)
        win.title("Modifica BET_VALUES (Bulk)")
        win.geometry("500x200")
        win.grab_set()

        ttk.Label(win, text="Valori bet validi (separati da virgola):").pack(padx=10, pady=5, anchor=tk.W)
        t = tk.Text(win, height=4, width=60)
        t.insert("1.0", ", ".join(str(v) for v in self.bulk_bet_values))
        t.pack(fill=tk.X, padx=10)
        ttk.Label(win, text="Nota: usato per validazione nell'editor BETTING_MODES, non influisce sulla simulazione.",
                  wraplength=480).pack(padx=10, pady=5)

        def on_save():
            raw = t.get("1.0", tk.END).strip()
            try:
                vals = [float(x.strip()) for x in raw.split(",") if x.strip()]
                if any(v <= 0 for v in vals):
                    raise ValueError("Valori devono essere positivi")
                if len(vals) != len(set(vals)):
                    raise ValueError("Valori devono essere univoci")
                self.bulk_bet_values = sorted(vals)
            except ValueError as e:
                messagebox.showerror("Errore", str(e))
                return
            win.destroy()

        ttk.Button(win, text="Salva", command=on_save).pack(pady=10)

    def reset_bulk_advanced_params(self):
        self.bulk_betting_modes = {k: list(v) for k, v in BETTING_MODES.items()}
        self.bulk_bet_values = list(BET_VALUES)
        for d in ["low", "medium", "high"]:
            for p in [1, 2, 3, 4]:
                self.bulk_win_multiplier_vars[d][p].set(WIN_MULTIPLIERS[d][p])
            self.bulk_mine_config_vars[d].set(TEST_MODE_MINE_CONFIG[d])
        messagebox.showinfo("Reset", "Parametri avanzati ripristinati ai valori default.")

    # ---- Bulk Excel Export ----

    def export_bulk_excel(self):
        if not self._bulk_results:
            messagebox.showerror("Errore", "Nessun risultato da esportare.")
            return
        from tkinter import filedialog
        import datetime
        default_name = f"bulk_test_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
                                                 initialfile=default_name)
        if not filepath:
            return
        try:
            success_counts, profit_thresholds, loss_thresholds, snapshot, n_runs = self._bulk_results
            self._write_excel(filepath, success_counts, profit_thresholds, loss_thresholds, snapshot, n_runs)
            messagebox.showinfo("Export", f"File salvato: {filepath}")
        except Exception as e:
            messagebox.showerror("Errore Export", str(e))

    def _write_excel(self, filepath, success_counts, profit_thresholds, loss_thresholds, snapshot, n_runs):
        from openpyxl import Workbook
        from openpyxl.styles import PatternFill, Font, Alignment
        from openpyxl.formatting.rule import ColorScaleRule
        from openpyxl.utils import get_column_letter

        wb = Workbook()

        # --- Sheet 1: Griglia Win Rate ---
        ws1 = wb.active
        ws1.title = "Griglia Win Rate"

        # Header row
        ws1.cell(row=1, column=1, value="maxloss \\ profitto")
        ws1.cell(row=1, column=1).font = Font(bold=True)
        for col_i, P in enumerate(profit_thresholds):
            ws1.cell(row=1, column=col_i + 2, value=P).font = Font(bold=True)

        # Data rows
        for row_i, L in enumerate(loss_thresholds):
            ws1.cell(row=row_i + 2, column=1, value=L).font = Font(bold=True)
            for col_i, P in enumerate(profit_thresholds):
                count = success_counts.get((L, P), 0)
                pct = round(count / n_runs * 100, 1) if n_runs > 0 else 0
                cell = ws1.cell(row=row_i + 2, column=col_i + 2, value=pct)
                cell.number_format = '0.0'
                cell.alignment = Alignment(horizontal='center')

        # Conditional formatting: 3-color scale (red 0 -> yellow 50 -> green 100)
        data_start = "B2"
        data_end = f"{get_column_letter(len(profit_thresholds) + 1)}{len(loss_thresholds) + 1}"
        ws1.conditional_formatting.add(
            f"{data_start}:{data_end}",
            ColorScaleRule(
                start_type="num", start_value=0, start_color="F8696B",
                mid_type="num", mid_value=50, mid_color="FFEB84",
                end_type="num", end_value=100, end_color="63BE7B",
            ),
        )

        # Freeze panes
        ws1.freeze_panes = "B2"

        # Auto-width for first column
        ws1.column_dimensions["A"].width = 18

        # --- Sheet 2: Impostazioni ---
        ws2 = wb.create_sheet("Impostazioni")
        settings_data = [
            ("Bankroll iniziale", snapshot["starting_cash"]),
            ("Target profit", snapshot["target_profit"]),
            ("Max loss", snapshot["max_loss"]),
            ("Max rounds", snapshot["max_rounds"]),
            ("Betting mode", snapshot["mode"]),
            ("Difficulty", snapshot["difficulty"]),
            ("Max picks", snapshot["max_picks"]),
            ("Grinding", "ON" if snapshot["grinding_enabled"] else "OFF"),
            ("Grinding range", snapshot["grinding_range"]),
            ("p_random", "ON" if snapshot["p_random"] else "OFF"),
            ("N runs eseguiti", n_runs),
        ]
        for row_i, (label, val) in enumerate(settings_data):
            ws2.cell(row=row_i + 1, column=1, value=label).font = Font(bold=True)
            ws2.cell(row=row_i + 1, column=2, value=val)

        # WIN_MULTIPLIERS table
        start_row = len(settings_data) + 3
        ws2.cell(row=start_row, column=1, value="WIN_MULTIPLIERS").font = Font(bold=True)
        for col_i, p in enumerate([1, 2, 3, 4]):
            ws2.cell(row=start_row, column=col_i + 2, value=f"p={p}").font = Font(bold=True)
        for row_i, d in enumerate(["low", "medium", "high"]):
            ws2.cell(row=start_row + 1 + row_i, column=1, value=d).font = Font(bold=True)
            for col_i, p in enumerate([1, 2, 3, 4]):
                ws2.cell(row=start_row + 1 + row_i, column=col_i + 2, value=snapshot["win_multipliers"][d][p])

        # MINE_CONFIG
        mine_row = start_row + 5
        ws2.cell(row=mine_row, column=1, value="MINE_CONFIG").font = Font(bold=True)
        for col_i, d in enumerate(["low", "medium", "high"]):
            ws2.cell(row=mine_row, column=col_i + 2, value=f"{d}: {snapshot['mine_config'][d]}")

        # Betting sequence
        seq_row = mine_row + 2
        ws2.cell(row=seq_row, column=1, value="Betting sequence").font = Font(bold=True)
        ws2.cell(row=seq_row, column=2, value=str(snapshot["betting_sequence"]))

        ws2.column_dimensions["A"].width = 20
        ws2.column_dimensions["B"].width = 30

        # --- Sheet 3: Sommario ---
        ws3 = wb.create_sheet("Sommario")
        ws3.cell(row=1, column=1, value="Totale run").font = Font(bold=True)
        ws3.cell(row=1, column=2, value=n_runs)

        target_p = int(max(profit_thresholds)) if profit_thresholds else 0
        max_l = int(max(loss_thresholds)) if loss_thresholds else 0

        # % runs that reached full target (using highest loss threshold = most permissive)
        target_count = success_counts.get((max_l, target_p), 0) if target_p and max_l else 0
        ws3.cell(row=2, column=1, value="% raggiunto target (profit >= target)").font = Font(bold=True)
        ws3.cell(row=2, column=2, value=f"{round(target_count / n_runs * 100, 1)}%" if n_runs > 0 else "0%")

        # % stopped by max_loss (complementary at tightest threshold)
        min_l = int(min(loss_thresholds)) if loss_thresholds else 0
        fail_count_tight = n_runs - success_counts.get((min_l, 1), 0) if min_l else n_runs
        ws3.cell(row=3, column=1, value=f"% fallite a L={min_l} (qualsiasi P)").font = Font(bold=True)
        ws3.cell(row=3, column=2, value=f"{round(fail_count_tight / n_runs * 100, 1)}%" if n_runs > 0 else "0%")

        # Extremes
        ws3.cell(row=5, column=1, value="Celle estreme:").font = Font(bold=True)
        if loss_thresholds and profit_thresholds:
            corners = [
                (min(loss_thresholds), min(profit_thresholds)),
                (min(loss_thresholds), max(profit_thresholds)),
                (max(loss_thresholds), min(profit_thresholds)),
                (max(loss_thresholds), max(profit_thresholds)),
            ]
            for i, (l, p) in enumerate(corners):
                cnt = success_counts.get((l, p), 0)
                pct = round(cnt / n_runs * 100, 1) if n_runs > 0 else 0
                ws3.cell(row=6 + i, column=1, value=f"L={l}, P={p}")
                ws3.cell(row=6 + i, column=2, value=f"{pct}%")

        ws3.column_dimensions["A"].width = 35
        ws3.column_dimensions["B"].width = 15

        wb.save(filepath)

    def on_closing(self):
        """Handle application closing"""
        self.mouse_monitoring = False
        self.game_running = False
        self.bulk_test_stop = True
        self.stop_event.set()
        self.running_event.clear()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        self.root.destroy()

def main():
    root = tk.Tk()
    
    # Apply modern styling
    style = ttk.Style()
    style.theme_use('clam')
    
    app = GrattaEVinciGUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()

