"""
Gratta-e-Vinci Automation GUI
Standalone application with configurable settings and mouse coordinate display
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import pyautogui
import random
import time
import json
import queue
from datetime import datetime
from pathlib import Path
from bulk_simulation import run_bulk_batch, wilson_interval
from bulk_export import save_bulk_json, write_bulk_excel, write_bulk_csv, STOP_LABELS
from bulk_export import load_bulk_json
from bulk_ui import LaptopPanel, add_laptop_results
from color_detector import ColorDetector
from coordinate_manager import CoordinateManager, CoordinateRecorder
from game_config import (
    BETTING_MODES,
    WIN_MULTIPLIERS,
    MAX_PICKS,
    BET_VALUES,
    TARGET_BLUE,
    TARGET_RED,
    COLOR_TOLERANCE,
    TEST_MODE_BOARD_SIZE,
    TEST_MODE_MINE_CONFIG,
    format_money,
)
from game_engine import GameEngine, TkAutomationAdapter
from settings_manager import SettingsManager
from tile_history import TileHistory

class GrattaEVinciGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Gratta-e-Vinci Automation v2.0")
        self.root.geometry("900x1000")
        self.root.resizable(True, True)
        self.settings_path = "gratta_settings.json"
        self.tile_history_error = None
        try:
            self.tile_history = TileHistory(Path(self.settings_path).resolve().with_name("tile_history.jsonl"))
        except OSError as error:
            self.tile_history = None
            self.tile_history_error = str(error)
        self.tile_record_enabled_var = tk.BooleanVar(value=self.tile_history is not None)
        self.tile_use_history_var = tk.BooleanVar(value=False)
        self.tile_reveal_delay_var = tk.DoubleVar(value=1.0)
        self.settings_manager = SettingsManager()
        self.coordinate_manager = CoordinateManager()
        
        # Initialize variables
        self.mouse_monitor_after_id = None
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
        self.bulk_show_logs_var = tk.BooleanVar(value=False)
        self.bulk_output_dir_var = tk.StringVar(value=str(Path(__file__).resolve().parent / "bulk_results"))
        self.bulk_test_running = False
        self.bulk_stop_event = threading.Event()
        self.bulk_logs_event = threading.Event()
        self.bulk_events = queue.Queue()
        self.bulk_poll_after_id = None
        self.bulk_worker_thread = None
        self.closing = False
        self._bulk_results = None

        # Bulk advanced params (local overrides, initialized from game_config defaults)
        self.bulk_betting_modes = {k: list(v) for k, v in BETTING_MODES.items()}
        self.bulk_bet_values = list(BET_VALUES)
        self.bulk_win_multiplier_vars = {
            d: {p: tk.DoubleVar(value=value) for p, value in WIN_MULTIPLIERS[d].items()}
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
        
        bulk_frame = ttk.Frame(notebook)
        notebook.add(bulk_frame, text="Bulk Test")
        self.create_bulk_test_section(bulk_frame)

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

        # Pauses Tab
        pauses_frame = ttk.Frame(notebook)
        notebook.add(pauses_frame, text="Pause")
        self.create_pauses_tab(pauses_frame)
    
    def create_settings_tab(self, parent):
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(canvas_window, width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        def _on_mousewheel(event):
            if canvas.winfo_ismapped() and not isinstance(event.widget, tk.Text):
                canvas.yview_scroll(int(-event.delta / 120), "units")
        self.root.bind("<MouseWheel>", _on_mousewheel, add="+")
        parent = scroll_frame

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
        ttk.Label(game_frame, text="Caselle (5-8 solo medium):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.max_picks_var = tk.IntVar(value=3)
        self.max_picks_spinbox = ttk.Spinbox(game_frame, from_=1, to=MAX_PICKS, textvariable=self.max_picks_var, width=13)
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

    def create_control_tab(self, parent):
        # Game control buttons
        control_frame = ttk.LabelFrame(parent, text="Game Control", padding=10)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.start_button = ttk.Button(control_frame, text="🎰 START GAME", command=self.start_game, style="Accent.TButton")
        self.start_button.pack(side=tk.LEFT, padx=10, pady=5)
        
        self.stop_button = ttk.Button(control_frame, text="🛑 STOP GAME", command=self.stop_game, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=10, pady=5)
        
        ttk.Button(control_frame, text="🧪 TEST MODE", command=self.start_test_mode).pack(side=tk.LEFT, padx=10, pady=5)

        tile_frame = ttk.LabelFrame(parent, text="Analisi delle 25 celle", padding=8)
        tile_frame.pack(fill=tk.X, padx=5, pady=5)
        self.tile_record_check = ttk.Checkbutton(tile_frame, text="Registra le 25 celle dopo vittorie e sconfitte",
                                                variable=self.tile_record_enabled_var, command=self._update_tile_controls)
        self.tile_record_check.pack(anchor="w")
        self.tile_history_check = ttk.Checkbutton(tile_frame, text="Scegli le celle usando lo storico (sperimentale)",
                                                 variable=self.tile_use_history_var)
        self.tile_history_check.pack(anchor="w")
        ttk.Label(tile_frame, text="La scelta resta casuale fino a 100 tavole complete per difficoltà. "
                  "Lo storico descrive il passato: non garantisce meno celle rosse nella prossima partita.",
                  wraplength=780).pack(anchor="w", pady=3)
        ttk.Button(tile_frame, text="Mostra analisi celle", command=self.show_tile_analysis).pack(anchor="w", pady=3)
        
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

    def _update_tile_controls(self):
        if self.tile_history is None:
            self.tile_record_enabled_var.set(False)
            self.tile_record_check.config(state="disabled")
        enabled = self.tile_record_enabled_var.get()
        if not enabled:
            self.tile_use_history_var.set(False)
        self.tile_history_check.config(state="normal" if enabled else "disabled")

    def show_tile_analysis(self):
        if self.tile_history is None:
            messagebox.showerror("Analisi celle", f"Archivio non leggibile: {self.tile_history_error}")
            return
        win = tk.Toplevel(self.root)
        win.title("Analisi delle celle — partite reali")
        win.geometry("730x580")
        win.minsize(730, 560)
        canvas = tk.Canvas(win, highlightthickness=0)
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        content = ttk.Frame(canvas)
        window = canvas.create_window(0, 0, window=content, anchor="nw")
        content.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        win.bind("<MouseWheel>", lambda event: canvas.yview_scroll(int(-event.delta/120), "units"))
        difficulty = ttk.Combobox(content, values=["low", "medium", "high"], state="readonly", width=14)
        difficulty.pack(anchor="w", padx=10, pady=8)
        difficulty.set(self.difficulty_var.get())
        description = ttk.Label(content, wraplength=680, justify="left")
        description.pack(anchor="w", padx=10, pady=5)
        grid = ttk.Frame(content)
        grid.pack(fill="x", padx=10, pady=5)
        cells = []
        for tile in range(25):
            cell = tk.Label(grid, relief="ridge", padx=6, pady=8)
            cell.grid(row=tile//5, column=tile%5, sticky="nsew")
            grid.columnconfigure(tile%5, weight=1)
            cells.append(cell)
        comparison = ttk.Label(content, wraplength=680, justify="left")
        comparison.pack(anchor="w", padx=10, pady=8)
        ttk.Label(content, text="Si usano soltanto tavole con tutte le celle riconosciute e un numero di rosse coerente con la difficoltà. "
                  "Le letture parziali restano nel file ma non influenzano la scelta.\n"
                  "Queste percentuali sono frequenze passate. Su tavole casuali indipendenti non prevedono la prossima cella.",
                  wraplength=680).pack(anchor="w", padx=10, pady=5)
        ttk.Label(content, text=f"Dati: {self.tile_history.path}", wraplength=680).pack(anchor="w", padx=10, pady=5)

        def refresh(_=None):
            stats = self.tile_history.stats(difficulty.get())
            status = "Scelta da storico disponibile (sperimentale)" if stats["ready"] else "Raccolta iniziale: scelta ancora casuale"
            description.config(text=f"Tavole utilizzabili: {stats['complete_boards']} | Letture parziali/non valide: {stats['partial_boards']}\n{status}")
            for label, data in zip(cells, stats["tiles"]):
                frequency = "—" if data["red_rate"] is None else f"{data['red_rate']*100:.1f}%"
                label.config(text=f"Cella {data['tile']}\nRosse: {frequency}\n{data['red_count']}/{data['observations']}", bg="#f2f5f7")
            evaluation = stats["evaluation"]
            if evaluation["pairs"]:
                n = evaluation["pairs"]
                comparison.config(text=f"Confronto sulle {n} nuove tavole, con scelte fissate prima di vedere i colori:\n"
                                  f"Storico avrebbe vinto: {evaluation['history_wins']}/{n} | Casuale avrebbe vinto: {evaluation['random_wins']}/{n}\n"
                                  "È un confronto delle scelte di celle, con il numero di caselle previsto per ogni partita. "
                                  "Una differenza osservata può dipendere dal caso.")
            else:
                comparison.config(text="Confronto storico/casuale: ancora nessuna nuova tavola valutata dopo la raccolta iniziale.")
            if stats.get("invalid_records"):
                description.config(text=description.cget("text") + f"\nRighe archivio non valide ignorate: {stats['invalid_records']}")
        difficulty.bind("<<ComboboxSelected>>", refresh)
        ttk.Button(content, text="Aggiorna", command=refresh).pack(anchor="e", padx=10, pady=5)
        refresh()
    
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
        add_pause_row(game_loop_frame, 8, "Attesa scoperta delle 25 celle (s)", self.tile_reveal_delay_var)

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
            self.tile_reveal_delay_var.set(1.0)
            self.sleep_init_raise_diff_var.set(0.4)
            self.sleep_init_lower_diff_var.set(0.4)
            self.sleep_init_click_var.set(0.3)

        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill=tk.X, padx=5, pady=10)
        ttk.Button(btn_frame, text="Salva pause", command=self.on_save_settings).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="Reset valori default", command=reset_pauses).pack(side=tk.LEFT)

    def start_mouse_monitoring(self):
        """Start monitoring mouse coordinates"""
        self.mouse_monitor_after_id = None
        try:
            x, y = pyautogui.position()
            coord_text = f"Mouse Position: ({x}, {y})"
            self.coord_label.config(text=coord_text)
            if hasattr(self, 'settings_coord_label'):
                self.settings_coord_label.config(text=coord_text)
            self.mouse_monitor_after_id = self.root.after(100, self.start_mouse_monitoring)
        except Exception as e:
            self.log_message(f"[WARN] Mouse monitor stopped due to error: {e}")
    
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
            "  p = numero di celle (1-4; 5-8 solo medium)\n"
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
                    if d not in ("low", "medium", "high"):
                        line_errors.append(f"Riga {i}: d={d} deve essere low, medium o high")
                    elif p not in WIN_MULTIPLIERS[d]:
                        line_errors.append(f"Riga {i}: p={p} non disponibile per {d}; 5-8 solo medium")
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
            "tile_record_enabled": self.tile_record_enabled_var.get(),
            "tile_use_history": self.tile_use_history_var.get(),
            "tile_reveal_delay": self.tile_reveal_delay_var.get(),
            "bulk_laptops": [panel.state() for panel in self.bulk_laptops],
            "bulk_game_rules": {
                "bet_values": list(self.bulk_bet_values),
                "mine_config": {d: var.get() for d, var in self.bulk_mine_config_vars.items()},
                "win_multipliers": {d: {p: var.get() for p, var in values.items()}
                                    for d, values in self.bulk_win_multiplier_vars.items()},
            },
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
        self.tile_record_enabled_var.set(settings.get("tile_record_enabled", True))
        self.tile_use_history_var.set(settings.get("tile_use_history", False))
        self.tile_reveal_delay_var.set(settings.get("tile_reveal_delay", 1.0))
        self._update_tile_controls()
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

        rules = settings.get("bulk_game_rules", {})
        if rules:
            self.bulk_bet_values = list(rules["bet_values"])
            for difficulty, var in self.bulk_mine_config_vars.items():
                var.set(rules["mine_config"][difficulty])
                values = rules["win_multipliers"][difficulty]
                for picks, multiplier_var in self.bulk_win_multiplier_vars[difficulty].items():
                    multiplier_var.set(values.get(picks, values.get(str(picks), WIN_MULTIPLIERS[difficulty][picks])))
        for index, panel in enumerate(self.bulk_laptops):
            saved = settings.get("bulk_laptops", [])
            if index < len(saved):
                panel.restore(saved[index])
            else:
                panel.copy_current()

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
    
    # ---- Bulk Test Section ----

    def create_bulk_test_section(self, parent):
        canvas = tk.Canvas(parent, highlightthickness=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(fill="both", expand=True)
        content = ttk.Frame(canvas)
        window = canvas.create_window(0, 0, window=content, anchor="nw")
        content.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        self.root.bind("<MouseWheel>", lambda event: canvas.yview_scroll(int(-event.delta / 120), "units")
                       if canvas.winfo_ismapped() and not isinstance(event.widget, tk.Text) else None, add="+")
        parent = content
        ttk.Label(parent, text="Configura i tre laptop e avvia lo stesso numero di simulazioni per ciascuno.",
                  padding=8).pack(anchor="w")
        cards = ttk.Frame(parent)
        cards.pack(fill="x", padx=4, pady=5)
        self.bulk_laptops = [LaptopPanel(self, cards, number) for number in range(1, 4)]
        ttk.Label(parent, text="Ogni simulazione riparte dal capitale indicato. Il limite di perdita misura il calo dal saldo più alto; "
                  "lo stop avviene dopo la giocata e può superare la soglia.", wraplength=810, padding=8).pack(anchor="w")
        ctrl_frame = ttk.LabelFrame(parent, text="Avvia il confronto", padding=8)
        ctrl_frame.pack(fill="x", padx=8, pady=5)
        ttk.Label(ctrl_frame, text="Simulazioni per laptop:").grid(row=0, column=0, sticky="w")
        self.bulk_n_runs_entry = ttk.Entry(ctrl_frame, textvariable=self.bulk_n_runs_var, width=10)
        self.bulk_n_runs_entry.grid(row=0, column=1, padx=5)
        self.bulk_start_button = ttk.Button(ctrl_frame, text="AVVIA BULK TEST", command=self.start_bulk_test)
        self.bulk_start_button.grid(row=0, column=2, padx=5)
        self.bulk_stop_button = ttk.Button(ctrl_frame, text="FERMA", command=self.stop_bulk_test, state="disabled")
        self.bulk_stop_button.grid(row=0, column=3, padx=5)
        self.bulk_progress_var = tk.DoubleVar(value=0)
        self.bulk_progress_bar = ttk.Progressbar(ctrl_frame, variable=self.bulk_progress_var, maximum=100, length=450)
        self.bulk_progress_bar.grid(row=1, column=0, columnspan=3, sticky="ew", pady=8)
        self.bulk_progress_label = ttk.Label(ctrl_frame, text="0/0")
        self.bulk_progress_label.grid(row=1, column=3)
        self.bulk_status_label = ttk.Label(ctrl_frame, text="In attesa")
        self.bulk_status_label.grid(row=2, column=0, columnspan=4, sticky="w")
        self.bulk_time_label = ttk.Label(ctrl_frame, text="")
        self.bulk_time_label.grid(row=3, column=0, columnspan=4, sticky="w")
        ttk.Label(ctrl_frame, text="Cartella risultati:").grid(row=4, column=0, sticky="w", pady=5)
        ttk.Entry(ctrl_frame, textvariable=self.bulk_output_dir_var, width=42).grid(row=4, column=1, columnspan=2, sticky="ew")
        ttk.Button(ctrl_frame, text="Sfoglia...", command=self._choose_bulk_output_dir).grid(row=4, column=3)
        ttk.Label(ctrl_frame, text="Risultati salvati in JSON e Excel.").grid(row=5, column=0, columnspan=4, sticky="w")
        ttk.Button(ctrl_frame, text="Regole del gioco...", command=self._show_bulk_rules).grid(row=6, column=0, sticky="w", pady=5)
        ttk.Button(ctrl_frame, text="Salva configurazioni", command=self.on_save_settings).grid(row=6, column=1, columnspan=2, sticky="w")
        self.bulk_show_logs_check = ttk.Checkbutton(ctrl_frame, text="Mostra log", variable=self.bulk_show_logs_var,
                                                    command=self._toggle_bulk_log_frame)
        self.bulk_show_logs_check.grid(row=6, column=3)
        self.bulk_log_frame = ttk.LabelFrame(parent, text="Log", padding=5)
        self.bulk_log_text = scrolledtext.ScrolledText(self.bulk_log_frame, height=5, font=("Courier", 9))
        self.bulk_log_text.pack(fill="x")
        # --- Export ---
        export_frame = ttk.Frame(parent)
        export_frame.pack(fill=tk.X, padx=5, pady=10)
        self.bulk_export_button = ttk.Button(export_frame, text="ESPORTA EXCEL", command=self.export_bulk_excel,
                                              state="disabled")
        self.bulk_export_button.pack(side=tk.LEFT, padx=5)
        self.bulk_results_button = ttk.Button(export_frame, text="MOSTRA RISULTATI",
                                             command=lambda: self._show_bulk_grid_popup(self._bulk_results),
                                             state="disabled")
        self.bulk_results_button.pack(side=tk.LEFT, padx=5)
        self.bulk_load_button = ttk.Button(export_frame, text="Apri risultati salvati", command=self.load_bulk_results)
        self.bulk_load_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(export_frame, text="ESPORTA DETTAGLI CSV", command=self.export_bulk_csv).pack(side=tk.LEFT, padx=5)

    def _show_bulk_rules(self):
        parent = tk.Toplevel(self.root)
        parent.title("Regole del gioco - comuni ai tre laptop")
        # --- Advanced Params ---
        adv_frame = ttk.LabelFrame(parent, text="Parametri Avanzati", padding=10)
        adv_frame.pack(fill=tk.X, padx=5, pady=5)

        # WIN_MULTIPLIERS grid
        ttk.Label(adv_frame, text="Moltiplicatori di vincita:", font=("", 10, "bold")).grid(row=0, column=0, columnspan=5,
                                                                                    sticky=tk.W, pady=(0, 5))
        for col_i, p in enumerate(range(1, MAX_PICKS + 1)):
            ttk.Label(adv_frame, text=f"p={p}").grid(row=1, column=col_i + 1, padx=5)
        for row_i, d in enumerate(["low", "medium", "high"]):
            ttk.Label(adv_frame, text=f"{d}:").grid(row=row_i + 2, column=0, sticky=tk.W, padx=5)
            for col_i, p in enumerate(range(1, MAX_PICKS + 1)):
                if p in self.bulk_win_multiplier_vars[d]:
                    widget = ttk.Entry(adv_frame, textvariable=self.bulk_win_multiplier_vars[d][p], width=6)
                else:
                    widget = ttk.Label(adv_frame, text="—")
                widget.grid(row=row_i + 2, column=col_i + 1, padx=3, pady=1)

        # MINE_CONFIG
        ttk.Label(adv_frame, text="Numero mine per difficolta:", font=("", 10, "bold")).grid(
            row=6, column=0, columnspan=5, sticky=tk.W, pady=(10, 5))
        for col_i, d in enumerate(["low", "medium", "high"]):
            ttk.Label(adv_frame, text=f"{d}:").grid(row=7, column=col_i * 2, sticky=tk.E, padx=2)
            ttk.Spinbox(adv_frame, from_=0, to=25, textvariable=self.bulk_mine_config_vars[d], width=4).grid(
                row=7, column=col_i * 2 + 1, padx=2)

        # BETTING_MODES / BET_VALUES buttons
        btn_adv_frame = ttk.Frame(adv_frame)
        btn_adv_frame.grid(row=8, column=0, columnspan=5, pady=10)
        ttk.Button(btn_adv_frame, text="Puntate consentite",
                   command=self.open_bulk_bet_values_editor).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_adv_frame, text="Ripristina defaults",
                   command=self.reset_bulk_advanced_params).pack(side=tk.LEFT, padx=5)

    def _choose_bulk_output_dir(self):
        from tkinter import filedialog
        path = filedialog.askdirectory(initialdir=self.bulk_output_dir_var.get())
        if path:
            self.bulk_output_dir_var.set(path)

    def _toggle_bulk_log_frame(self):
        if self.bulk_show_logs_var.get():
            self.bulk_logs_event.set()
            self.bulk_log_frame.pack(fill=tk.X, padx=5, pady=5)
        else:
            self.bulk_logs_event.clear()
            self.bulk_log_frame.pack_forget()

    # ---- Bulk Test Control ----

    def start_bulk_test(self):
        if self.bulk_test_running:
            return
        try:
            n = int(self.bulk_n_runs_entry.get())
            if n <= 0:
                raise ValueError("Le ripetizioni devono essere un intero maggiore di zero.")
            settings = [panel.snapshot() for panel in self.bulk_laptops]
            self._launch_bulk(settings, n)
        except (ValueError, TypeError, KeyError, tk.TclError, OSError) as error:
            messagebox.showerror("Parametri Bulk Test", str(error))
            return

    def _launch_bulk(self, settings, n):
        if self.bulk_test_running:
            return
        output_text = self.bulk_output_dir_var.get().strip()
        if not output_text:
            raise ValueError("Scegli una cartella per il salvataggio automatico.")
        output_dir = Path(output_text).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        self.bulk_test_running = True
        self.bulk_stop_event.clear()
        self._bulk_results = None
        self.bulk_start_button.config(state="disabled")
        self.bulk_stop_button.config(state="normal")
        self.bulk_export_button.config(state="disabled")
        self.bulk_results_button.config(state="disabled")
        self.bulk_load_button.config(state="disabled")
        self.bulk_n_runs_entry.config(state="disabled")
        self.bulk_progress_var.set(0)
        self.bulk_total_runs = n * len(settings)
        self.bulk_done_runs = 0
        self.bulk_started_at = time.monotonic()
        self.bulk_status_label.config(text="Confronto dei tre laptop in esecuzione")
        self.bulk_log_text.delete("1.0", tk.END)
        self.bulk_events = queue.Queue()
        filename = f"bulk_test_{datetime.now():%Y%m%d_%H%M%S_%f}"
        json_path = output_dir / (filename + ".json")
        self.bulk_worker_thread = threading.Thread(
            target=self._bulk_test_worker, args=(settings, n, json_path), daemon=True)
        self.bulk_worker_thread.start()
        self._bulk_poll_events()

    def export_bulk_csv(self):
        if self._bulk_results is None:
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("Dettagli CSV", "*.csv")])
        if path:
            try:
                write_bulk_csv(path, self._bulk_results)
            except OSError as error:
                messagebox.showerror("Esportazione CSV", str(error))

    def stop_bulk_test(self):
        self.bulk_stop_event.set()
        self.bulk_status_label.config(text="Interruzione e salvataggio in corso...")
        self.bulk_stop_button.config(state="disabled")

    def _bulk_test_worker(self, settings, n, json_path):
        latest = None
        warnings = []
        last_progress = 0.0
        last_log = 0.0

        def checkpoint(batch):
            nonlocal latest
            latest = batch
            try:
                save_bulk_json(json_path, batch)
            except OSError as error:
                warning = f"Salvataggio archivio non riuscito: {error}"
                if warning not in warnings:
                    warnings.append(warning)
                    self.bulk_events.put(("log", warning))

        def progress(done, total):
            nonlocal last_progress
            now = time.monotonic()
            if done == total or now - last_progress >= 0.1:
                last_progress = now
                self.bulk_events.put(("progress", (done, total)))

        def log(message):
            nonlocal last_log
            now = time.monotonic()
            if now - last_log >= 0.1:
                self.bulk_events.put(("log", message))
                last_log = now

        try:
            batch = run_bulk_batch(
                settings, n, None, progress, log,
                self.bulk_stop_event.is_set, self.bulk_logs_event.is_set, checkpoint)
            save_bulk_json(json_path, batch)
            try:
                write_bulk_excel(json_path.with_suffix(".xlsx"), batch)
            except Exception as error:
                warnings.append(f"Esportazione Excel automatica non riuscita: {error}")
            self.bulk_events.put(("complete", (batch, json_path, warnings)))
        except Exception as error:
            if latest is not None:
                latest["status"] = "error"
                latest["error"] = str(error)
                checkpoint(latest)
            self.bulk_events.put(("error", (str(error), latest)))

    @staticmethod
    def _bulk_duration(seconds):
        seconds = max(0, int(seconds))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:d}h {minutes:02d}m {seconds:02d}s" if hours else f"{minutes:d}m {seconds:02d}s"

    def _bulk_poll_events(self):
        self.bulk_poll_after_id = None
        for _ in range(200):
            try:
                kind, data = self.bulk_events.get_nowait()
            except queue.Empty:
                break
            if kind == "progress":
                self.bulk_done_runs, self.bulk_total_runs = data
                self._bulk_update_progress(*data)
            elif kind == "log":
                self._bulk_log_message(data)
            elif kind == "complete":
                batch, path, warnings = data
                self._on_bulk_test_complete(batch, path, warnings)
            elif kind == "error":
                error, batch = data
                self._bulk_results = batch
                self._on_bulk_test_failed()
                if not self.closing:
                    messagebox.showerror("Errore Bulk Test", error)

        if self.bulk_test_running:
            elapsed = time.monotonic() - self.bulk_started_at
            done = self.bulk_done_runs
            remaining = elapsed * (self.bulk_total_runs - done) / done if done else None
            eta = self._bulk_duration(remaining) if remaining is not None else "in stima"
            self.bulk_time_label.config(text=f"Trascorso: {self._bulk_duration(elapsed)} | Rimanente: {eta}")
            self.bulk_poll_after_id = self.root.after(100, self._bulk_poll_events)

    def _restore_bulk_controls(self):
        self.bulk_test_running = False
        self.bulk_start_button.config(state="normal")
        self.bulk_stop_button.config(state="disabled")
        self.bulk_load_button.config(state="normal")
        self.bulk_n_runs_entry.config(state="normal")
        state = "normal" if self._bulk_results is not None else "disabled"
        self.bulk_export_button.config(state=state)
        self.bulk_results_button.config(state=state)

    def _on_bulk_test_complete(self, batch, path=None, warnings=()):
        self._bulk_results = batch
        self._restore_bulk_controls()
        completed = sum(config["summary"]["completed_runs"] for config in batch["configurations"])
        total = batch["requested_runs"] * len(batch["configurations"])
        self._bulk_update_progress(completed, total)
        status = "Interrotto" if batch["status"] == "interrupted" else "Completato"
        self.bulk_status_label.config(text=f"{status}: {completed}/{total} sessioni completate")
        self.bulk_time_label.config(text=f"Durata: {self._bulk_duration(batch['elapsed_seconds'])}")
        if path:
            self._bulk_log_message(f"Risultati: {path}")
        for warning in warnings:
            self._bulk_log_message(warning)
        if not self.closing:
            if warnings:
                messagebox.showwarning("Salvataggio Bulk Test", "\n".join(warnings))
            self._show_bulk_grid_popup(batch)

    def _show_bulk_grid_popup(self, batch):
        if batch is None:
            return
        win = tk.Toplevel(self.root)
        win.title("Risultati Bulk Test - confronto laptop")
        win.geometry("1150x750")
        win.minsize(1000, 700)
        notebook = ttk.Notebook(win)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        add_laptop_results(notebook, batch)
        def number(value):
            return "-" if value is None else f"{value:.2f}"

        grid_tab = ttk.Frame(notebook)
        notebook.add(grid_tab, text="Dettaglio avanzato")
        labels = [f"{config['id']}. {config['label']}" for config in batch["configurations"]]
        selected = ttk.Combobox(grid_tab, values=labels, state="readonly", width=90)
        selected.pack(fill=tk.X, pady=5)
        description = ttk.Label(grid_tab, wraplength=1080, justify=tk.LEFT)
        description.pack(anchor=tk.W, pady=5)
        ttk.Label(grid_tab, text="Righe: calo massimo osservato dal picco. Colonne: profitto raggiunto. "
                  "Non sono simulazioni con stop loss diversi. Seleziona una cella per conteggio e IC 95%.",
                  wraplength=1080).pack(anchor=tk.W, pady=5)
        cell_info = ttk.Label(grid_tab, text="")
        cell_info.pack(anchor=tk.W, pady=5)
        outer = ttk.Frame(grid_tab)
        outer.pack(fill=tk.BOTH, expand=True)
        canvas = tk.Canvas(outer, highlightthickness=0)
        horizontal = ttk.Scrollbar(outer, orient="horizontal", command=canvas.xview)
        vertical = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)
        horizontal.pack(side=tk.BOTTOM, fill=tk.X)
        vertical.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(fill=tk.BOTH, expand=True)
        content = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))

        def show_cell(count, total, loss, profit):
            low, high = wilson_interval(count, total)
            cell_info.config(text=f"Calo ≤ {loss:g}, profitto ≥ {profit:g}: {count}/{total} sessioni | "
                             f"IC 95%: {number(low)}% … {number(high)}%")

        def render(_event=None):
            for widget in content.winfo_children():
                widget.destroy()
            config = batch["configurations"][selected.current()]
            summary = config["summary"]
            counts = summary["stop_counts"]
            reasons = STOP_LABELS.items()
            description.config(text=" | ".join(f"{title}: {counts.get(key, 0)}" for key, title in reasons)
                               + f"\nProfitto medio {number(summary['avg_profit'])}; mediana {number(summary['median_profit'])}; "
                               f"P5/P95 {number(summary['p05_profit'])}/{number(summary['p95_profit'])}; "
                               f"min/max {number(summary['min_profit'])}/{number(summary['max_profit'])}. "
                               f"Positive: {number(summary['positive_rate'])}% "
                               f"(IC 95% {number(summary['positive_ci_low'])} … {number(summary['positive_ci_high'])}%).")
            cell_info.config(text="")
            if config["settings"].get("activity", {}).get("enabled"):
                ttk.Label(content, text="Questo vecchio report descrive un periodo di attivita: la griglia delle sessioni non e disponibile.").pack()
                return
            total = summary["completed_runs"]
            tk.Label(content, text="Calo / Profitto", relief="ridge", width=16).grid(row=0, column=0, sticky="nsew")
            for col, profit in enumerate(config["profit_thresholds"], 1):
                tk.Label(content, text=f"{profit:g}", width=8, relief="ridge").grid(row=0, column=col, sticky="nsew")
            for row, loss in enumerate(config["loss_thresholds"], 1):
                tk.Label(content, text=f"{loss:g}", relief="ridge").grid(row=row, column=0, sticky="nsew")
                for col, profit in enumerate(config["profit_thresholds"], 1):
                    count = config["success_counts"][row - 1][col - 1]
                    pct = count / total * 100 if total else None
                    if pct is None:
                        color = "#eeeeee"
                    else:
                        start, end = ((248, 105, 107), (255, 235, 132)) if pct <= 50 else ((255, 235, 132), (99, 190, 123))
                        fraction = pct / 50 if pct <= 50 else (pct - 50) / 50
                        color = "#" + "".join(f"{int(a + (b - a) * fraction):02x}" for a, b in zip(start, end))
                    cell = tk.Label(content, text=f"{pct:.1f}%" if pct is not None else "?",
                                    bg=color, fg="#202020", relief="ridge", cursor="hand2")
                    cell.grid(row=row, column=col, sticky="nsew")
                    cell.bind("<Button-1>", lambda event, c=count, n=total, l=loss, p=profit: show_cell(c, n, l, p))
            canvas.xview_moveto(0)
            canvas.yview_moveto(0)

        selected.bind("<<ComboboxSelected>>", render)
        if labels:
            selected.current(0)
            render()
    def _on_bulk_test_failed(self):
        self._restore_bulk_controls()
        self.bulk_status_label.config(text="Errore durante l'esecuzione; i risultati disponibili restano esportabili.")

    def _bulk_log_message(self, message):
        self.bulk_log_text.insert(tk.END, message + "\n")
        lines = int(self.bulk_log_text.index("end-1c").split(".")[0])
        if lines > 200:
            self.bulk_log_text.delete("1.0", f"{lines - 200}.0")
        self.bulk_log_text.see(tk.END)

    def _bulk_update_progress(self, done, total):
        pct = done / total * 100 if total else 0
        self.bulk_progress_var.set(pct)
        self.bulk_progress_label.config(text=f"{done}/{total} ({pct:.1f}%)")

    def load_bulk_results(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(initialdir=self.bulk_output_dir_var.get(),
                                          filetypes=[("Risultati Bulk Test", "*.json")])
        if not path:
            return
        try:
            batch = load_bulk_json(path)
            # Check fields used by the viewer before replacing the current result.
            for config in batch["configurations"]:
                if len(config["success_counts"]) != len(config["loss_thresholds"]):
                    raise ValueError("Griglia risultati incompleta.")
                if any(len(row) != len(config["profit_thresholds"]) for row in config["success_counts"]):
                    raise ValueError("Griglia risultati incompleta.")
                if not isinstance(config["summary"]["stop_counts"], dict):
                    raise ValueError("Riepilogo risultati non valido.")
            self._on_bulk_test_complete(batch, Path(path))
        except (ValueError, TypeError, KeyError, AttributeError, OSError) as error:
            messagebox.showerror("Caricamento risultati", str(error))

    # ---- Bulk Advanced Param Editors ----

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
            for p in self.bulk_win_multiplier_vars[d]:
                self.bulk_win_multiplier_vars[d][p].set(WIN_MULTIPLIERS[d][p])
            self.bulk_mine_config_vars[d].set(TEST_MODE_MINE_CONFIG[d])
        messagebox.showinfo("Reset", "Parametri avanzati ripristinati ai valori default.")

    # ---- Bulk Excel Export ----

    def export_bulk_excel(self):
        if self._bulk_results is None:
            messagebox.showerror("Errore", "Nessun risultato da esportare.")
            return
        from tkinter import filedialog
        filepath = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")],
            initialfile=f"bulk_test_{datetime.now():%Y%m%d_%H%M%S}.xlsx")
        if not filepath:
            return
        try:
            self._write_excel(filepath, self._bulk_results)
            messagebox.showinfo("Export", f"File salvato: {filepath}")
        except Exception as error:
            messagebox.showerror("Errore Export", str(error))

    def _write_excel(self, filepath, batch):
        write_bulk_excel(filepath, batch)

    def on_closing(self):
        """Handle application closing"""
        self.closing = True
        if self.mouse_monitor_after_id is not None:
            self.root.after_cancel(self.mouse_monitor_after_id)
            self.mouse_monitor_after_id = None
        self.game_running = False
        self.bulk_stop_event.set()
        self.stop_event.set()
        self.running_event.clear()
        if self.bulk_worker_thread is not None and self.bulk_worker_thread.is_alive():
            self.bulk_status_label.config(text="Chiusura: salvataggio dei risultati in corso...")
            self.root.after(100, self.on_closing)
            return
        if self.bulk_poll_after_id is not None:
            self.root.after_cancel(self.bulk_poll_after_id)
            self.bulk_poll_after_id = None
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

