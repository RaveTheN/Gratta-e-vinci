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
from pynput import keyboard
import json
import os

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    
    def __repr__(self):
        return f"Point({self.x}, {self.y})"

class GrattaEVinciGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Gratta-e-Vinci Automation v2.0")
        self.root.geometry("800x900")
        self.root.resizable(True, True)
        
        # Initialize variables
        self.mouse_monitoring = False
        self.game_running = False
        self.escape_pressed = False
        self.keyboard_listener = None
        
        # Game variables
        self.current_cash = 0
        self.highest_cash = 0
        self.bet = 0.1
        self.highest_bet = 0.1
        self.picks = 0
        self.tries = 0
        self.rounds = 0
        self.loss = 0
        self.randoms = []
        
        # Target colors
        self.target_blue = {"r": 1, "g": 108, "b": 238}
        self.target_red = {"r": 200, "g": 13, "b": 1}
        
        # Tiles dictionary (will be configurable)
        self.tiles = {}
        
        # Betting modes - initialize with default values
        self.betting_modes = {
            "normal": [0.1, 0.2, 0.3, 0.5, 0.8, 1.4, 2.5, 4.5, 8.0, 14.0, 20.0],
            "medium": [0.1, 0.2, 0.3, 0.5, 0.9, 1.5, 3.0, 5.0, 9.0, 15.0, 20.0],
            "high": [0.2, 0.3, 0.6, 1.0, 1.8, 3.0, 5.0, 9.0, 16.0, 20.0],
            "safe": [0.1, 0.1, 0.2, 0.3, 0.5, 1.0, 1.8, 3.0, 5.0, 9.0, 15.0, 20.0]
        }
        
        # Valid bet values that can be used in betting modes
        self.bet_values = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.4, 1.5, 1.6, 1.8, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 25.0]
        
        # Create GUI
        self.create_widgets()
        self.load_settings()
        
        # Start mouse coordinate monitoring
        self.start_mouse_monitoring()
    
    def create_widgets(self):
        # Main notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Settings & Coordinates Tab (combined)
        settings_coords_frame = ttk.Frame(notebook)
        notebook.add(settings_coords_frame, text="Settings & Coordinates")
        self.create_settings_coordinates_tab(settings_coords_frame)
        
        # Betting Modes Tab
        betting_frame = ttk.Frame(notebook)
        notebook.add(betting_frame, text="Betting Modes")
        self.create_betting_modes_tab(betting_frame)
        
        # Game Control Tab
        control_frame = ttk.Frame(notebook)
        notebook.add(control_frame, text="Game Control")
        self.create_control_tab(control_frame)
        
        # Statistics Tab
        stats_frame = ttk.Frame(notebook)
        notebook.add(stats_frame, text="Statistics")
        self.create_stats_tab(stats_frame)
    
    def create_settings_tab(self, parent):
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
        ttk.Label(game_frame, text="Max Picks (2 or 3):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.max_picks_var = tk.IntVar(value=3)
        ttk.Spinbox(game_frame, from_=2, to=3, textvariable=self.max_picks_var, width=13).grid(row=2, column=1, padx=5, pady=2)
        
        # Betting Mode
        ttk.Label(game_frame, text="Betting Mode:").grid(row=2, column=2, sticky=tk.W, pady=2)
        self.mode_var = tk.StringVar(value="normal")
        mode_combo = ttk.Combobox(game_frame, textvariable=self.mode_var, width=12)
        mode_combo['values'] = ("normal", "medium", "high", "safe")
        mode_combo.grid(row=2, column=3, padx=5, pady=2)
        
        # Betting Mode Editor Button
        ttk.Button(game_frame, text="Edit Modes", command=self.open_betting_mode_editor).grid(row=3, column=2, columnspan=2, padx=5, pady=2)
        
        # Wait between rounds
        self.wait_selected_var = tk.BooleanVar()
        ttk.Checkbutton(game_frame, text="Random wait between rounds (1-6 min)", 
                       variable=self.wait_selected_var).grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=2)
        
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
        
        # Buttons
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=tk.X, padx=5, pady=10)
        
        ttk.Button(button_frame, text="Save Settings", command=self.save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Load Settings", command=self.load_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Reset to Defaults", command=self.reset_settings).pack(side=tk.LEFT, padx=5)
    
    def create_coordinates_tab(self, parent):
        # Mouse coordinates display
        coord_frame = ttk.LabelFrame(parent, text="Mouse Coordinates", padding=10)
        coord_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.coord_label = ttk.Label(coord_frame, text="Mouse Position: (0, 0)", font=("Courier", 12))
        self.coord_label.pack(pady=5)
        
        # Tile positions frame
        tile_frame = ttk.LabelFrame(parent, text="Tile Positions (5x5 Grid)", padding=10)
        tile_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Create tile position entries
        self.tile_vars = {}
        for i in range(5):
            for j in range(5):
                tile_num = i * 5 + j + 1
                row_frame = ttk.Frame(tile_frame)
                if j == 0:
                    row_frame.pack(fill=tk.X, pady=2)
                
                ttk.Label(row_frame, text=f"Tile {tile_num}:", width=8).pack(side=tk.LEFT, padx=2)
                
                x_var = tk.IntVar(value=1640 + j * 170)
                y_var = tk.IntVar(value=740 + i * 128)
                self.tile_vars[tile_num] = (x_var, y_var)
                
                ttk.Entry(row_frame, textvariable=x_var, width=6).pack(side=tk.LEFT, padx=1)
                ttk.Entry(row_frame, textvariable=y_var, width=6).pack(side=tk.LEFT, padx=1)
        
        # Quick setup buttons
        quick_frame = ttk.Frame(parent)
        quick_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(quick_frame, text="Auto-Generate Grid", command=self.auto_generate_grid).pack(side=tk.LEFT, padx=5)
        ttk.Button(quick_frame, text="Test Click Tile 1", command=lambda: self.test_click_tile(1)).pack(side=tk.LEFT, padx=5)
    
    def create_settings_coordinates_tab(self, parent):
        """Combined Settings and Coordinates tab"""
        # Create scrollable container with optimized settings
        canvas = tk.Canvas(parent, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        # Optimize scroll region updates
        def configure_scroll_region(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))
        
        scrollable_frame.bind("<Configure>", configure_scroll_region)
        
        canvas_window = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Make canvas window responsive to parent width
        def configure_canvas_width(event):
            canvas.itemconfig(canvas_window, width=event.width)
        canvas.bind('<Configure>', configure_canvas_width)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Add optimized mouse wheel scrolling
        def on_mousewheel(event):
            try:
                # Only scroll if scrollbar is visible and canvas exists
                if scrollbar.winfo_viewable() and canvas.winfo_exists():
                    canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            except tk.TclError:
                pass
        
        # Bind to canvas instead of all widgets for better performance
        canvas.bind("<MouseWheel>", on_mousewheel)
        scrollable_frame.bind("<MouseWheel>", on_mousewheel)
        
        # Main container within scrollable frame
        main_container = ttk.Frame(scrollable_frame)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # === SETTINGS SECTION ===
        settings_main_frame = ttk.LabelFrame(main_container, text="⚙️ Game Settings", padding=15)
        settings_main_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Game Settings Frame
        game_frame = ttk.LabelFrame(settings_main_frame, text="Game Configuration", padding=10)
        game_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Configure grid weights for better expansion (batch configure)
        grid_weights = [1, 1, 1, 1]
        for i, weight in enumerate(grid_weights):
            game_frame.grid_columnconfigure(i, weight=weight)
        
        # Starting Cash
        ttk.Label(game_frame, text="Starting Cash:").grid(row=0, column=0, sticky=tk.W, pady=3, padx=5)
        self.starting_cash_var = tk.DoubleVar(value=2001.50)
        ttk.Entry(game_frame, textvariable=self.starting_cash_var, width=18).grid(row=0, column=1, padx=5, pady=3, sticky=tk.EW)
        
        # Target Win
        ttk.Label(game_frame, text="Target Win:").grid(row=0, column=2, sticky=tk.W, pady=3, padx=5)
        self.target_win_var = tk.DoubleVar(value=2100.0)
        ttk.Entry(game_frame, textvariable=self.target_win_var, width=18).grid(row=0, column=3, padx=5, pady=3, sticky=tk.EW)
        
        # Max Loss
        ttk.Label(game_frame, text="Max Loss:").grid(row=1, column=0, sticky=tk.W, pady=3, padx=5)
        self.max_loss_var = tk.DoubleVar(value=10.0)
        ttk.Entry(game_frame, textvariable=self.max_loss_var, width=18).grid(row=1, column=1, padx=5, pady=3, sticky=tk.EW)
        
        # Max Rounds
        ttk.Label(game_frame, text="Max Rounds:").grid(row=1, column=2, sticky=tk.W, pady=3, padx=5)
        self.max_rounds_var = tk.IntVar(value=100)
        ttk.Entry(game_frame, textvariable=self.max_rounds_var, width=18).grid(row=1, column=3, padx=5, pady=3, sticky=tk.EW)
        
        # Max Picks
        ttk.Label(game_frame, text="Max Picks (2 or 3):").grid(row=2, column=0, sticky=tk.W, pady=3, padx=5)
        self.max_picks_var = tk.IntVar(value=3)
        ttk.Spinbox(game_frame, from_=2, to=3, textvariable=self.max_picks_var, width=16).grid(row=2, column=1, padx=5, pady=3, sticky=tk.EW)
        
        # Betting Mode
        ttk.Label(game_frame, text="Betting Mode:").grid(row=2, column=2, sticky=tk.W, pady=3, padx=5)
        self.mode_var = tk.StringVar(value="normal")
        mode_combo = ttk.Combobox(game_frame, textvariable=self.mode_var, width=15)
        mode_combo['values'] = ("normal", "medium", "high", "safe")
        mode_combo.grid(row=2, column=3, padx=5, pady=3, sticky=tk.EW)
        
        # Wait between rounds (span across columns)
        self.wait_selected_var = tk.BooleanVar()
        ttk.Checkbutton(game_frame, text="Random wait between rounds (1-6 min)", 
                       variable=self.wait_selected_var).grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=3, padx=5)
        
        # Betting Mode Editor Button
        ttk.Button(game_frame, text="✏️ Edit Betting Modes", command=self.open_betting_mode_editor).grid(row=3, column=2, columnspan=2, padx=5, pady=3, sticky=tk.EW)
        
        # Control Points Frame
        control_frame = ttk.LabelFrame(settings_main_frame, text="Control Points", padding=10)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Configure grid weights (batch configure)
        grid_weights = [1, 1, 1, 1, 1, 1]
        for i, weight in enumerate(grid_weights):
            control_frame.grid_columnconfigure(i, weight=weight)
        
        # Play/Collect Button
        ttk.Label(control_frame, text="Play/Collect:").grid(row=0, column=0, sticky=tk.W, pady=3, padx=3)
        self.play_x_var = tk.IntVar(value=2196)
        self.play_y_var = tk.IntVar(value=1616)
        ttk.Entry(control_frame, textvariable=self.play_x_var, width=10).grid(row=0, column=1, padx=2, pady=3)
        ttk.Entry(control_frame, textvariable=self.play_y_var, width=10).grid(row=0, column=2, padx=2, pady=3)
        
        # Raise Bet Button
        ttk.Label(control_frame, text="Raise Bet:").grid(row=0, column=3, sticky=tk.W, pady=3, padx=3)
        self.raise_x_var = tk.IntVar(value=1900)
        self.raise_y_var = tk.IntVar(value=1740)
        ttk.Entry(control_frame, textvariable=self.raise_x_var, width=10).grid(row=0, column=4, padx=2, pady=3)
        ttk.Entry(control_frame, textvariable=self.raise_y_var, width=10).grid(row=0, column=5, padx=2, pady=3)
        
        # Lower Bet Button
        ttk.Label(control_frame, text="Lower Bet:").grid(row=1, column=0, sticky=tk.W, pady=3, padx=3)
        self.lower_x_var = tk.IntVar(value=1519)
        self.lower_y_var = tk.IntVar(value=1740)
        ttk.Entry(control_frame, textvariable=self.lower_x_var, width=10).grid(row=1, column=1, padx=2, pady=3)
        ttk.Entry(control_frame, textvariable=self.lower_y_var, width=10).grid(row=1, column=2, padx=2, pady=3)
        
        # Buttons
        button_frame = ttk.Frame(settings_main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(button_frame, text="💾 Save Settings", command=self.save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="📂 Load Settings", command=self.load_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="🔄 Reset to Defaults", command=self.reset_settings).pack(side=tk.LEFT, padx=5)
        
        # === COORDINATES SECTION ===
        coords_main_frame = ttk.LabelFrame(main_container, text="📍 Coordinates Configuration", padding=15)
        coords_main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Mouse coordinates display
        coord_frame = ttk.LabelFrame(coords_main_frame, text="Live Mouse Position", padding=10)
        coord_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.coord_label = ttk.Label(coord_frame, text="Mouse Position: (0, 0)", font=("Courier", 12, "bold"))
        self.coord_label.pack(pady=8)
        
        # Tile positions frame
        tile_frame = ttk.LabelFrame(coords_main_frame, text="Tile Positions (Key Tiles Only)", padding=15)
        tile_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Create tile position entries for specific tiles only
        self.tile_vars = {}
        key_tiles = [1, 2, 3, 4, 5, 6, 11, 16, 21]
        
        # Create rows for better organization
        tiles_per_row = 3
        for i, tile_num in enumerate(key_tiles):
            if i % tiles_per_row == 0:
                row_frame = ttk.Frame(tile_frame)
                row_frame.pack(fill=tk.X, pady=8)
                # Configure equal weights for all columns in the row
                for col in range(tiles_per_row):
                    row_frame.grid_columnconfigure(col, weight=1)
            
            # Calculate column position
            col_pos = i % tiles_per_row
            
            tile_container = ttk.Frame(row_frame)
            tile_container.grid(row=0, column=col_pos, padx=15, pady=5, sticky=tk.EW)
            
            # Tile label
            tile_label = ttk.Label(tile_container, text=f"Tile {tile_num}:", width=10, font=("TkDefaultFont", 10, "bold"))
            tile_label.pack(side=tk.TOP, pady=(0, 5))
            
            # Coordinate entries container
            coord_container = ttk.Frame(tile_container)
            coord_container.pack(fill=tk.X)
            
            # Default coordinates based on tile number
            default_x = 1640 + ((tile_num - 1) % 5) * 170
            default_y = 740 + ((tile_num - 1) // 5) * 128
            
            x_var = tk.IntVar(value=default_x)
            y_var = tk.IntVar(value=default_y)
            self.tile_vars[tile_num] = (x_var, y_var)
            
            # X coordinate
            ttk.Label(coord_container, text="X:", font=("TkDefaultFont", 9)).pack(side=tk.LEFT)
            ttk.Entry(coord_container, textvariable=x_var, width=8, font=("TkDefaultFont", 9)).pack(side=tk.LEFT, padx=(2, 5))
            
            # Y coordinate
            ttk.Label(coord_container, text="Y:", font=("TkDefaultFont", 9)).pack(side=tk.LEFT)
            ttk.Entry(coord_container, textvariable=y_var, width=8, font=("TkDefaultFont", 9)).pack(side=tk.LEFT, padx=2)
        
        # Quick setup buttons
        quick_frame = ttk.Frame(coords_main_frame)
        quick_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(quick_frame, text="🔄 Auto-Generate Key Tiles", command=self.auto_generate_grid).pack(side=tk.LEFT, padx=5)
        ttk.Button(quick_frame, text="🎯 Test Click Tile 1", command=lambda: self.test_click_tile(1)).pack(side=tk.LEFT, padx=5)
    
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
        mode_combo['values'] = ("normal", "medium", "high", "safe")
        mode_combo.pack(side=tk.LEFT, padx=(0, 10))
        mode_combo.bind('<<ComboboxSelected>>', lambda e: self.update_betting_preview())
        
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
        ttk.Button(action_frame, text="✏️ Edit Betting Modes", command=self.open_betting_mode_editor).grid(row=0, column=0, padx=2, pady=2, sticky=tk.EW)
        ttk.Button(action_frame, text="📊 Analyze Modes", command=self.analyze_betting_modes).grid(row=0, column=1, padx=2, pady=2, sticky=tk.EW)
        ttk.Button(action_frame, text="🔄 Reset to Defaults", command=self.reset_betting_modes).grid(row=0, column=2, padx=2, pady=2, sticky=tk.EW)
        
        # Bottom row buttons
        ttk.Button(action_frame, text="📤 Export Modes", command=self.export_betting_modes).grid(row=1, column=0, padx=2, pady=2, sticky=tk.EW)
        ttk.Button(action_frame, text="📥 Import Modes", command=self.import_betting_modes).grid(row=1, column=1, padx=2, pady=2, sticky=tk.EW)
        
        # Initial preview update
        self.root.after(100, self.update_betting_preview)
    
    def update_betting_preview(self):
        """Update the betting mode preview"""
        selected_mode = self.mode_var.get()
        
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
            
            # Calculate break-even win rate
            total_risk = sum(mode_values)
            # Assuming 2.4x multiplier for wins
            breakeven_rate = total_risk / (total_risk + 2.4 * mode_values[0])
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
            breakeven = total_risk / (total_risk + 2.4 * mode_values[0])
            analysis += f"{mode_name:<10} {len(mode_values):<6} {self.format_money(max_bet):<10} {self.format_money(total_risk):<12} {breakeven:.1%}\n"
        
        analysis_text.insert(tk.END, analysis)
        analysis_text.config(state=tk.DISABLED)
        
        # Close button
        ttk.Button(analysis_window, text="Close", command=analysis_window.destroy).pack(pady=10)
    
    def reset_betting_modes(self):
        """Reset betting modes to defaults"""
        if messagebox.askyesno("Reset Betting Modes", "Reset all betting modes to default values?"):
            # Ensure default modes only use values from bet_values
            default_modes = {
                "normal": [0.1, 0.2, 0.3, 0.5, 0.8, 1.4, 2.5, 4.5, 8.0, 14.0, 20.0],
                "medium": [0.1, 0.2, 0.3, 0.5, 0.9, 1.5, 3.0, 5.0, 9.0, 15.0, 20.0],
                "high": [0.2, 0.3, 0.6, 1.0, 1.8, 3.0, 5.0, 9.0, 16.0, 20.0],
                "safe": [0.1, 0.1, 0.2, 0.3, 0.5, 1.0, 1.8, 3.0, 5.0, 9.0, 15.0, 20.0]
            }
            
            # Validate that all default values are in bet_values
            for mode_name, values in default_modes.items():
                invalid_values = [v for v in values if v not in self.bet_values]
                if invalid_values:
                    messagebox.showerror("Default Mode Error", 
                                       f"Default mode '{mode_name}' contains invalid values: {invalid_values}\n"
                                       f"Please update the default modes to use only valid bet values.")
                    return
            
            self.betting_modes = default_modes
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
        
        # Progress bar
        progress_frame = ttk.LabelFrame(parent, text="Progress", padding=10)
        progress_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=5)
        
        self.progress_label = ttk.Label(progress_frame, text="Ready to start")
        self.progress_label.pack()
    
    def start_mouse_monitoring(self):
        """Start monitoring mouse coordinates"""
        self.mouse_monitoring = True
        threading.Thread(target=self.mouse_monitor_thread, daemon=True).start()
    
    def mouse_monitor_thread(self):
        """Thread function for monitoring mouse coordinates"""
        while self.mouse_monitoring:
            try:
                x, y = pyautogui.position()
                self.root.after(0, lambda: self.coord_label.config(text=f"Mouse Position: ({x}, {y})"))
                time.sleep(0.1)
            except:
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
        
        instructions_text = "Edit betting mode arrays. Enter comma-separated positive numeric values:"
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
        
        # Configure button layout
        button_frame.grid_columnconfigure(0, weight=1)
        button_frame.grid_columnconfigure(1, weight=1)
        button_frame.grid_columnconfigure(2, weight=1)
        
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
                default_modes = {
                    "normal": [0.1, 0.2, 0.3, 0.5, 0.8, 1.4, 2.5, 4.5, 8.0, 14.0, 20.0],
                    "medium": [0.1, 0.2, 0.3, 0.5, 0.9, 1.5, 3.0, 5.0, 9.0, 15.0, 20.0],
                    "high": [0.2, 0.3, 0.6, 1.0, 1.8, 3.0, 5.0, 9.0, 16.0, 20.0],
                    "safe": [0.1, 0.1, 0.2, 0.3, 0.5, 1.0, 1.8, 3.0, 5.0, 9.0, 15.0, 20.0]
                }
                
                # Update text widgets
                for mode_name, values in default_modes.items():
                    if mode_name in mode_text_widgets:
                        text_widget = mode_text_widgets[mode_name]
                        text_widget.delete("1.0", tk.END)
                        text_widget.insert(tk.END, ", ".join(str(val) for val in values))
        
        def preview_mode():
            """Preview the selected mode values"""
            selected_mode = self.mode_var.get()
            if selected_mode in mode_text_widgets:
                text_widget = mode_text_widgets[selected_mode]
                text_widget.focus_set()
                text_widget.tag_add(tk.SEL, "1.0", tk.END)
                messagebox.showinfo("Preview", f"Selected mode: {selected_mode}\nValues: {text_widget.get('1.0', tk.END).strip()}")
        
        # Buttons with grid layout for better responsiveness
        ttk.Button(button_frame, text="💾 Save Changes", command=validate_and_save).grid(row=0, column=0, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(button_frame, text="🔄 Reset to Defaults", command=reset_to_defaults).grid(row=0, column=1, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(button_frame, text="👁️ Preview Selected", command=preview_mode).grid(row=0, column=2, padx=5, pady=5, sticky=tk.EW)
        ttk.Button(button_frame, text="❌ Cancel", command=editor_window.destroy).grid(row=1, column=1, padx=5, pady=5, sticky=tk.EW)
        
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
        await asyncio.sleep(1)
        pyautogui.click(play_x, play_y)
        self.log_message("🎮 Clicked play/collect button")
    
    async def increase_bet(self):
        """Increase bet by clicking raise bet button"""
        raise_x = self.raise_x_var.get()
        raise_y = self.raise_y_var.get()
        await asyncio.sleep(0.5)
        pyautogui.click(raise_x, raise_y)
        # Update bet value (simplified - in real game this would be read from screen)
        current_bet_index = next((i for i, v in enumerate([0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 1.4, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0]) if v >= self.bet), 0)
        bet_values = [0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 1.4, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
        if current_bet_index < len(bet_values) - 1:
            self.bet = bet_values[current_bet_index + 1]
        self.log_message(f"📈 Bet increased to: {self.format_money(self.bet)}")
    
    async def decrease_bet(self):
        """Decrease bet by clicking lower bet button"""
        lower_x = self.lower_x_var.get()
        lower_y = self.lower_y_var.get()
        await asyncio.sleep(0.5)
        pyautogui.click(lower_x, lower_y)
        # Update bet value (simplified - in real game this would be read from screen)
        bet_values = [0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 1.4, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
        current_bet_index = next((i for i, v in enumerate(bet_values) if v >= self.bet), 0)
        if current_bet_index > 0:
            self.bet = bet_values[current_bet_index - 1]
        self.log_message(f"📉 Bet decreased to: {self.format_money(self.bet)}")
    
    async def decrease_bet_force(self):
        """Force decrease bet to minimum"""
        lower_x = self.lower_x_var.get()
        lower_y = self.lower_y_var.get()
        
        # Click lower bet button multiple times to ensure minimum
        for i in range(25):  # Should be enough to reach minimum
            await asyncio.sleep(0.05)
            pyautogui.click(lower_x, lower_y)
        
        self.bet = 0.1  # Set to minimum
        self.log_message("🔽 Bet forced to minimum: 0.10")
    
    async def click_tile(self, tile_number):
        """Click on a specific tile"""
        if tile_number in self.tiles:
            point = self.tiles[tile_number]
            await asyncio.sleep(0.5)
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
    
    def read_color_at_point(self, point):
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
        
        # Validate settings
        if not self.validate_settings():
            return
        
        # Confirm real game start
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
        
        # Update UI
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        # Initialize game variables
        self.initialize_game_variables()
        
        # Update tiles from GUI
        self.update_tiles_from_gui()
        
        # Start game in separate thread
        threading.Thread(target=self.run_game_async, daemon=True).start()
        
        # Start keyboard listener
        self.start_keyboard_listener()
        
        self.log_message("🎰 REAL GAME STARTED!")
        self.log_message("⚠️ AUTOMATION ACTIVE - Mouse will be controlled!")
        self.log_message(f"Starting cash: {self.format_money(self.current_cash)}")
        self.log_message("Press ESCAPE key to stop at any time")
    
    def stop_game(self):
        """Stop the automated game or test mode"""
        self.game_running = False
        self.escape_pressed = True
        
        # Update UI
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        # Stop keyboard listener if it exists
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        
        self.log_message("🛑 GAME/TEST STOPPED by user")
    
    def start_test_mode(self):
        """Start test mode (simulation)"""
        if self.game_running:
            self.log_message("⚠️ Game already running! Stop current game first.")
            return
            
        self.log_message("🧪 Starting TEST MODE (simulation only - no mouse control)...")
        self.log_message("📊 This will simulate 5 rounds to test your betting strategy")
        
        # Set game_running to True for test mode
        self.game_running = True
        
        # Initialize variables for test
        self.current_cash = round(self.starting_cash_var.get(), 2)
        self.highest_cash = self.current_cash
        self.bet = 0.1
        self.highest_bet = 0.1
        self.picks = 0
        self.tries = 0
        self.rounds = 0
        self.loss = 0.0
        self.update_stats_display()
        
        threading.Thread(target=self.run_test_mode, daemon=True).start()
    
    def run_test_mode(self):
        """Run game simulation for testing"""
        try:
            # Simulate some game rounds
            for round_num in range(1, 6):
                if not self.game_running:
                    break
                
                self.log_message(f"\n=== Test Round {round_num} ===")
                self.log_message(f"💰 Starting bet: {self.format_money(self.bet)}")
                
                # Simulate random outcome
                if random.random() < 0.6:  # 60% win chance
                    self.log_message("🎉 Test WIN!")
                    win_amount = self.bet * 2.4
                    self.current_cash += win_amount
                    self.current_cash = round(self.current_cash, 2)
                    self.log_message(f"💰 Won {self.format_money(win_amount)}! New balance: {self.format_money(self.current_cash)}")
                    
                    # Reset betting strategy after win
                    self.tries = 0
                    self.bet = 0.1  # Reset bet on win
                    self.log_message(f"🎯 WIN! Bet reset to minimum: {self.format_money(self.bet)}")
                else:
                    self.log_message("💸 Test LOSS!")
                    self.current_cash -= self.bet
                    self.current_cash = round(self.current_cash, 2)
                    self.tries += 1
                    
                    self.log_message(f"💸 Lost {self.format_money(self.bet)}! New balance: {self.format_money(self.current_cash)}")
                    
                    # Get betting strategy from selected mode
                    selected_mode_name = self.mode_var.get()
                    if selected_mode_name in self.betting_modes:
                        mode_array = self.betting_modes[selected_mode_name]
                        # Use tries as index, but cap at array length - 1
                        bet_index = min(self.tries, len(mode_array) - 1)
                        old_bet = self.bet
                        self.bet = mode_array[bet_index]
                        self.log_message(f"📈 Bet updated from {selected_mode_name} mode: {self.format_money(old_bet)} → {self.format_money(self.bet)} (try #{self.tries})")
                    else:
                        # Fallback to simple increase if mode not found
                        old_bet = self.bet
                        self.bet = min(self.bet * 1.5, 5.0)  # Increase bet
                        self.log_message(f"📈 Bet increased: {self.format_money(old_bet)} → {self.format_money(self.bet)}")
                
                # Update highest values
                if self.current_cash > self.highest_cash:
                    self.highest_cash = self.current_cash
                if self.bet > self.highest_bet:
                    self.highest_bet = self.bet
                
                # Calculate loss
                self.loss = max(0, round(self.highest_cash - self.current_cash, 2))
                
                # Update rounds counter
                self.rounds = round_num
                
                # Update UI
                self.root.after(0, self.update_stats_display)
                
                # Log current state
                self.log_message(f"📊 Round {round_num} complete - Cash: {self.format_money(self.current_cash)}, Next bet: {self.format_money(self.bet)}, Loss: {self.format_money(self.loss)}")
                
                time.sleep(2)  # Simulate game delay
            
            # Test completed
            self.log_message("\n=== TEST MODE RESULTS ===")
            self.log_message(f"💰 Final cash: {self.format_money(self.current_cash)}")
            self.log_message(f"📈 Highest cash: {self.format_money(self.highest_cash)}")
            self.log_message(f"🔝 Highest bet: {self.format_money(self.highest_bet)}")
            self.log_message(f"📉 Total loss: {self.format_money(self.loss)}")
            self.log_message(f"🏁 Rounds played: {self.rounds}")
            
            profit_loss = self.current_cash - self.starting_cash_var.get()
            if profit_loss > 0:
                self.log_message(f"✅ Net profit: +{self.format_money(profit_loss)}")
            else:
                self.log_message(f"❌ Net loss: {self.format_money(profit_loss)}")
            
            self.log_message("🧪 Test mode completed!")
            
        finally:
            # Always reset game_running when test is done
            self.game_running = False
    
    def validate_settings(self):
        """Validate game settings"""
        try:
            starting_cash = self.starting_cash_var.get()
            if starting_cash <= 0:
                raise ValueError("Starting cash must be positive")
            
            max_picks = self.max_picks_var.get()
            if max_picks not in [2, 3]:
                raise ValueError("Max picks must be 2 or 3")
            
            return True
        except Exception as e:
            messagebox.showerror("Invalid Settings", str(e))
            return False
    
    def initialize_game_variables(self):
        """Initialize game variables from GUI settings"""
        self.current_cash = round(self.starting_cash_var.get(), 2)
        self.highest_cash = self.current_cash
        self.bet = 0.1
        self.highest_bet = 0.1
        self.picks = 0
        self.tries = 0
        self.rounds = 0
        self.loss = 0.0
        self.randoms = []
        
        self.log_message(f"💰 Initialized with cash: {self.format_money(self.current_cash)}")
        self.update_stats_display()
    
    def update_tiles_from_gui(self):
        """Update tiles dictionary from GUI values"""
        self.tiles = {}
        for tile_num, (x_var, y_var) in self.tile_vars.items():
            self.tiles[tile_num] = Point(x_var.get(), y_var.get())
    
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
            loop.run_until_complete(self.main_game_loop())
        finally:
            loop.close()
    
    async def main_game_loop(self):
        """Main game loop with actual game automation"""
        max_rounds = self.max_rounds_var.get()
        target_win = self.target_win_var.get()
        max_loss = self.max_loss_var.get()
        max_picks = self.max_picks_var.get()
        wait_selected = self.wait_selected_var.get()
        
        self.log_message("🎮 Starting REAL game automation...")
        self.log_message("⚠️ Make sure your game window is positioned correctly!")
        
        # Force set bet to minimum at start
        await self.decrease_bet_force()
        
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
            await self.play_real_game_round()
            
            # Update statistics
            self.root.after(0, self.update_stats_display)
            
            # Small delay between rounds
            await asyncio.sleep(2)
        
        # Game ended
        self.root.after(0, self.stop_game)
        self.log_message("=== GAME ENDED ===")
        self.log_message(f"Final cash: {self.format_money(self.current_cash)}")
        self.log_message(f"Highest cash: {self.format_money(self.highest_cash)}")
        self.log_message(f"Highest bet: {self.format_money(self.highest_bet)}")
    
    async def play_real_game_round(self):
        """Play an actual game round with mouse automation"""
        max_picks = self.max_picks_var.get()
        
        # Start new round - reset picks and prepare for new game
        self.picks = 0
        self.randoms = []
        round_active = True
        
        self.log_message(f"\n=== Round {self.rounds + 1} ===")
        self.log_message(f"💰 Current bet: {self.format_money(self.bet)}")
        
        # Press play to start the round and immediately deduct cash
        await self.play_or_collect()
        self.log_message(f"🎮 Started round - Cash deducted: {self.format_money(self.bet)}")
        self.current_cash -= self.bet
        self.current_cash = round(self.current_cash, 2)
        
        # Keep picking tiles until we get max_picks blues (win) or 1 red (lose)
        while round_active and self.picks < max_picks:
            # Check for escape key press during round
            if self.escape_pressed:
                self.log_message("🛑 Game stopped by escape key during round")
                round_active = False
                break
            
            # Generate random tile number
            tile_number = self.generate_random_tile()
            
            # Wait for game to process
            await asyncio.sleep(1)
            
            # Click on the corresponding tile
            await self.click_tile(tile_number)
            await asyncio.sleep(1.5)
            
            # Check color of the revealed tile with retry mechanism
            color_detected = False
            retry_count = 0
            max_retries = 3
            
            while not color_detected and retry_count < max_retries:
                # Get the position of the tile we just clicked
                clicked_tile_position = self.tiles[tile_number]
                color = self.read_color_at_point(clicked_tile_position)
                
                # Print the actual color values detected
                self.log_message(f"🎨 Color at tile {tile_number} ({clicked_tile_position.x}, {clicked_tile_position.y}): RGB({color['r']}, {color['g']}, {color['b']})")
                
                if self.is_color_in_range_blue(color, self.target_blue):
                    # BLUE tile found
                    self.log_message(f"✅ Tile {tile_number} is BLUE")
                    self.picks += 1
                    color_detected = True
                    
                    # Check if we got max_picks blues (WIN)
                    if self.picks >= max_picks:
                        self.log_message(f"🎉 {max_picks} BLUES! ROUND WON!")
                        
                        # Press collect to get winnings
                        await self.play_or_collect()
                        
                        # Increase cash by bet times multiplier (we win!)
                        multiplier = 1.8 if max_picks == 2 else 2.4
                        win_amount = self.bet * multiplier
                        self.current_cash += win_amount
                        self.current_cash = round(self.current_cash, 2)
                        
                        self.log_message(f"💰 Won {self.format_money(win_amount)}! New balance: {self.format_money(self.current_cash)}")
                        
                        # Update highest cash
                        if self.current_cash > self.highest_cash:
                            self.highest_cash = round(self.current_cash, 2)
                        
                        # Reset betting strategy after win - back to minimum bet
                        self.tries = 0
                        self.picks = 0
                        
                        # Decrease bet down to minimum
                        while self.bet > 0.1:
                            await self.decrease_bet()
                        
                        self.log_message(f"🎯 WIN! Bet reset to minimum: {self.format_money(self.bet)}")
                        
                        # Reset for next round
                        round_active = False
                        
                    else:
                        # Continue picking - we have less than max_picks blues
                        self.log_message(f"Got {self.picks} blue(s), need {max_picks - self.picks} more...")
                        
                elif self.is_color_in_range_red(color, self.target_red):
                    # RED tile found - ROUND LOST
                    self.log_message(f"❌ Tile {tile_number} is RED - ROUND LOST!")
                    color_detected = True
                    
                    # Cash already deducted when round started, just update strategy
                    self.tries += 1
                    
                    # Reset picks and end round
                    self.picks = 0
                    round_active = False
                    
                    # Update betting strategy after showing round results
                    selected_mode_name = self.mode_var.get()
                    if selected_mode_name in self.betting_modes:
                        mode_array = self.betting_modes[selected_mode_name]
                        # Use tries as index, but cap at array length - 1
                        bet_index = min(self.tries, len(mode_array) - 1)
                        target_bet = mode_array[bet_index]
                        
                        # Adjust bet to target
                        while self.bet < target_bet:
                            await self.increase_bet()
                        
                        # Update highest bet tracking
                        if self.bet > self.highest_bet:
                            self.highest_bet = round(self.bet, 2)
                        
                        self.log_message(f"💸 LOSS! Bet increased to: {self.format_money(self.bet)} (try #{self.tries})")
                    
                    # Calculate loss
                    self.loss = max(0, round(self.highest_cash - self.current_cash, 2))
                    if self.loss >= self.max_loss_var.get():
                        self.log_message("⚠️ Reached maximum loss!")
                        self.game_running = False
                        break
                    
                else:
                    # Unknown color detected - retry after waiting
                    retry_count += 1
                    self.log_message(f"❓ Tile {tile_number} - Unknown color (attempt {retry_count}/{max_retries})")
                    self.log_message(f"   Expected: Blue RGB(1,108,238) or Red RGB(200,13,1)")
                    self.log_message(f"   Actual: RGB({color['r']}, {color['g']}, {color['b']})")
                    
                    if retry_count < max_retries:
                        self.log_message("   Waiting 1 second and retrying color detection...")
                        await asyncio.sleep(1)
                    else:
                        self.log_message("   Max retries reached, assuming neutral tile...")
                        color_detected = True
                        continue
        
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
            self.current_cash += self.bet * 2.4
            self.tries = 0
            self.bet = 0.1  # Reset bet on win
        else:
            self.log_message("💸 Round LOST!")
            self.current_cash -= self.bet
            self.tries += 1
            
            # Get betting strategy from selected mode
            selected_mode_name = self.mode_var.get()
            if selected_mode_name in self.betting_modes:
                mode_array = self.betting_modes[selected_mode_name]
                # Use tries as index, but cap at array length - 1
                bet_index = min(self.tries, len(mode_array) - 1)
                self.bet = mode_array[bet_index]
                self.log_message(f"Bet updated from {selected_mode_name} mode: {self.format_money(self.bet)} (try #{self.tries})")
            else:
                # Fallback to simple increase if mode not found
                bet_multipliers = [0.1, 0.2, 0.3, 0.5, 0.8, 1.4, 2.5, 4.5, 8.0]
                if self.tries < len(bet_multipliers):
                    self.bet = bet_multipliers[self.tries]
        
        # Update highest values
        if self.current_cash > self.highest_cash:
            self.highest_cash = self.current_cash
        if self.bet > self.highest_bet:
            self.highest_bet = self.bet
        
        self.loss = max(0, self.highest_cash - self.current_cash)
    
    def update_stats_display(self):
        """Update the statistics display"""
        self.current_cash_label.config(text=self.format_money(self.current_cash))
        self.highest_cash_label.config(text=self.format_money(self.highest_cash))
        self.current_bet_label.config(text=self.format_money(self.bet))
        self.highest_bet_label.config(text=self.format_money(self.highest_bet))
        self.rounds_label.config(text=str(self.rounds))
        self.tries_label.config(text=str(self.tries))
        self.loss_label.config(text=self.format_money(self.loss))
    
    def format_money(self, value):
        """Format monetary values to always show exactly 2 decimal places"""
        return f"{round(value, 2):.2f}"
    
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
            initialname=default_filename,
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
    
    def save_settings(self):
        """Save settings to file"""
        settings = {
            "starting_cash": self.starting_cash_var.get(),
            "target_win": self.target_win_var.get(),
            "max_loss": self.max_loss_var.get(),
            "max_rounds": self.max_rounds_var.get(),
            "max_picks": self.max_picks_var.get(),
            "mode": self.mode_var.get(),
            "wait_selected": self.wait_selected_var.get(),
            "play_x": self.play_x_var.get(),
            "play_y": self.play_y_var.get(),
            "raise_x": self.raise_x_var.get(),
            "raise_y": self.raise_y_var.get(),
            "lower_x": self.lower_x_var.get(),
            "lower_y": self.lower_y_var.get(),
            "tiles": {str(num): [x_var.get(), y_var.get()] for num, (x_var, y_var) in self.tile_vars.items()},
            "betting_modes": self.betting_modes
        }
        
        try:
            with open("gratta_settings.json", "w") as f:
                json.dump(settings, f, indent=2)
            messagebox.showinfo("Saved", "Settings saved successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
    
    def load_settings(self):
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
                
                self.play_x_var.set(settings.get("play_x", 2196))
                self.play_y_var.set(settings.get("play_y", 1616))
                self.raise_x_var.set(settings.get("raise_x", 1900))
                self.raise_y_var.set(settings.get("raise_y", 1740))
                self.lower_x_var.set(settings.get("lower_x", 1519))
                self.lower_y_var.set(settings.get("lower_y", 1740))
                
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
                
                self.log_message("Settings loaded successfully!")
        except Exception as e:
            self.log_message(f"Failed to load settings: {e}")
    
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
            self.wait_selected_var.set(False)
            
            self.play_x_var.set(2196)
            self.play_y_var.set(1616)
            self.raise_x_var.set(1900)
            self.raise_y_var.set(1740)
            self.lower_x_var.set(1519)
            self.lower_y_var.set(1740)
            
            self.auto_generate_grid()
            messagebox.showinfo("Reset", "Settings reset to defaults!")
    
    def on_closing(self):
        """Handle application closing"""
        self.mouse_monitoring = False
        self.game_running = False
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
