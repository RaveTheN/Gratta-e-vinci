"""Coordinate grid and recorder management."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from pynput import keyboard, mouse

from game_config import Point


class CoordinateManager:
    def populate_tile_vars(self, tile_vars, base_x, base_y, x_vars_top, y_vars_left):
        x_coords = [base_x] + [var.get() for var in x_vars_top]
        y_coords = [base_y] + [var.get() for var in y_vars_left]
        for tile_num in range(1, 26):
            row = (tile_num - 1) // 5
            col = (tile_num - 1) % 5
            x = x_coords[col]
            y = y_coords[row]
            if tile_num not in tile_vars:
                tile_vars[tile_num] = (tk.IntVar(value=x), tk.IntVar(value=y))
                continue
            current_x_var, current_y_var = tile_vars[tile_num]
            if tile_num in (1, 2, 3, 4, 5, 6, 11, 16, 21):
                continue
            current_x_var.set(x)
            current_y_var.set(y)

    def build_tile_points(self, tile_vars):
        return {tile_num: Point(x_var.get(), y_var.get()) for tile_num, (x_var, y_var) in tile_vars.items()}

    def build_preview_text(self, tile_vars):
        preview_text = "Calculated tile coordinates (5x5 grid):\n"
        preview_text += "-" * 50 + "\n"
        for row in range(5):
            row_text = ""
            for col in range(5):
                tile_num = row * 5 + col + 1
                if tile_num in tile_vars:
                    x = tile_vars[tile_num][0].get()
                    y = tile_vars[tile_num][1].get()
                    row_text += f"T{tile_num:2d}({x:4d},{y:4d}) "
                else:
                    row_text += f"T{tile_num:2d}(----,----) "
            preview_text += row_text + "\n"
        return preview_text


class CoordinateRecorder:
    def __init__(self, app):
        self.app = app
        self.steps = self._build_steps()
        self.current_step = 0
        self.recorded = {}
        self.overlay = None
        self.mouse_listener = None
        self.kb_listener = None
        self.step_counter_label = None
        self.instruction_label = None
        self.status_label = None
        self.step_labels = []
        self._closed = False

    def _build_steps(self):
        return [
            {"label": "Tile 1", "type": "xy", "var_key": 1},
            {"label": "Tile 2", "type": "x_only", "var_key": 2},
            {"label": "Tile 3", "type": "x_only", "var_key": 3},
            {"label": "Tile 4", "type": "x_only", "var_key": 4},
            {"label": "Tile 5", "type": "x_only", "var_key": 5},
            {"label": "Tile 6", "type": "y_only", "var_key": 6},
            {"label": "Tile 11", "type": "y_only", "var_key": 11},
            {"label": "Tile 16", "type": "y_only", "var_key": 16},
            {"label": "Tile 21", "type": "y_only", "var_key": 21},
            {"label": "Play/Collect Button", "type": "xy", "var_key": ("play_x_var", "play_y_var")},
            {"label": "Raise Bet Button", "type": "xy", "var_key": ("raise_x_var", "raise_y_var")},
            {"label": "Lower Bet Button", "type": "xy", "var_key": ("lower_x_var", "lower_y_var")},
            {"label": "Raise Difficulty Button", "type": "xy", "var_key": ("raise_diff_x_var", "raise_diff_y_var")},
            {"label": "Lower Difficulty Button", "type": "xy", "var_key": ("lower_diff_x_var", "lower_diff_y_var")},
        ]

    def start(self):
        existing = getattr(self.app, "coordinate_recorder", None)
        if existing and existing is not self:
            existing._cancel()
        self.app.coordinate_recorder = self
        self._create_overlay()
        try:
            self.mouse_listener = mouse.Listener(on_click=self._on_click, win32_event_filter=self._win32_mouse_event_filter)
            self.kb_listener = keyboard.Listener(on_press=self._on_key)
            self.mouse_listener.start()
            self.kb_listener.start()
        except Exception as e:
            self._cancel()
            messagebox.showerror("Coordinate Recorder", f"Unable to start listeners:\n{e}")

    def _create_overlay(self):
        self.app.root.update_idletasks()
        base_x = max(0, self.app.root.winfo_rootx() + 40)
        base_y = max(0, self.app.root.winfo_rooty() + 40)
        self.overlay = tk.Toplevel(self.app.root)
        self.overlay.title("Recording Coordinates")
        self.overlay.geometry(f"600x500+{base_x}+{base_y}")
        self.overlay.resizable(False, False)
        self.overlay.attributes("-topmost", True)
        self.overlay.protocol("WM_DELETE_WINDOW", self._cancel)

        main_frame = tk.Frame(self.overlay, bg="#F5F7FB", padx=12, pady=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        tk.Label(main_frame, text="Recording Coordinates", font=("Arial", 13, "bold"), bg="#F5F7FB", fg="#1F2937").pack(anchor="w")
        self.step_counter_label = tk.Label(main_frame, font=("Arial", 10), bg="#F5F7FB", fg="#475569")
        self.step_counter_label.pack(anchor="w", pady=(4, 0))
        self.instruction_label = tk.Label(main_frame, font=("Arial", 12, "bold"), bg="#F5F7FB", fg="#0F172A", justify=tk.LEFT, anchor="w", wraplength=345)
        self.instruction_label.pack(fill=tk.X, pady=(8, 2))
        self.status_label = tk.Label(main_frame, font=("Arial", 10), bg="#F5F7FB", fg="#B45309", justify=tk.LEFT, anchor="w")
        self.status_label.pack(fill=tk.X, pady=(0, 8))
        steps_frame = tk.Frame(main_frame, bg="#FFFFFF", bd=1, relief=tk.SOLID)
        steps_frame.pack(fill=tk.BOTH, expand=True)
        for col in range(2):
            steps_frame.grid_columnconfigure(col, weight=1)
        for idx, step in enumerate(self.steps):
            row = idx % 7
            col = idx // 7
            step_label = tk.Label(steps_frame, text=step["label"], anchor="w", justify=tk.LEFT, font=("Arial", 8), padx=6, pady=2, bg="#FFFFFF", fg="#334155")
            step_label.grid(row=row, column=col, sticky="ew", padx=2, pady=1)
            self.step_labels.append(step_label)
        tk.Label(main_frame, text="← → navigate  |  Right-click = redo  |  Enter = save  |  ESC = cancel", font=("Arial", 8), bg="#F5F7FB", fg="#475569", wraplength=345, justify=tk.CENTER).pack(fill=tk.X, pady=(8, 0))
        self.overlay.lift()
        self.overlay.focus_force()
        self._update_overlay()

    def _win32_mouse_event_filter(self, msg, data):
        if self._closed:
            return True
        left_button_down = getattr(mouse.Listener, "WM_LBUTTONDOWN", None)
        left_button_up = getattr(mouse.Listener, "WM_LBUTTONUP", None)
        right_button_down = getattr(mouse.Listener, "WM_RBUTTONDOWN", None)
        right_button_up = getattr(mouse.Listener, "WM_RBUTTONUP", None)
        if msg == left_button_down:
            self.app.root.after(0, lambda: self._record_and_advance(data.pt.x, data.pt.y))
            self.mouse_listener.suppress_event()
        elif msg == left_button_up:
            self.mouse_listener.suppress_event()
        elif msg == right_button_down:
            self.app.root.after(0, self._go_back)
            self.mouse_listener.suppress_event()
        elif msg == right_button_up:
            self.mouse_listener.suppress_event()
        return True

    def _update_overlay(self):
        if not self.overlay or not self.overlay.winfo_exists():
            return
        step = self.steps[self.current_step]
        type_suffix = {"xy": "", "x_only": " (X position)", "y_only": " (Y position)"}
        short_suffix = {"xy": "", "x_only": " (X)", "y_only": " (Y)"}
        self.step_counter_label.config(text=f"Step {self.current_step + 1} / {len(self.steps)}")
        self.instruction_label.config(text=f"Click on: {step['label']}{type_suffix[step['type']]}")
        coords = self.recorded.get(self.current_step)
        if coords:
            self.status_label.config(text=f"Recorded: ({coords[0]}, {coords[1]})", fg="#166534")
        else:
            self.status_label.config(text="Not recorded yet", fg="#B45309")
        for idx, label in enumerate(self.step_labels):
            current_step = self.steps[idx]
            marker = "✓" if idx in self.recorded else "•"
            bg = "#DBEAFE" if idx == self.current_step else "#FFFFFF"
            fg = "#0F172A" if idx == self.current_step else "#334155"
            font = ("Arial", 8, "bold") if idx == self.current_step else ("Arial", 8)
            label.config(text=f"{marker} {idx + 1}. {current_step['label']}{short_suffix[current_step['type']]}", bg=bg, fg=fg, font=font)

    def _on_click(self, x, y, button, pressed):
        if not pressed or self._closed:
            return
        if button == mouse.Button.left:
            self.app.root.after(0, lambda: self._record_and_advance(x, y))
        elif button == mouse.Button.right:
            self.app.root.after(0, self._go_back)

    def _on_key(self, key):
        if self._closed:
            return
        if key == keyboard.Key.esc:
            self.app.root.after(0, self._cancel)
        elif key == keyboard.Key.enter:
            self.app.root.after(0, self._save_and_close)
        elif key == keyboard.Key.left:
            self.app.root.after(0, lambda: self._navigate(-1))
        elif key == keyboard.Key.right:
            self.app.root.after(0, lambda: self._navigate(1))

    def _record_and_advance(self, x, y):
        if self._closed:
            return
        self.recorded[self.current_step] = (int(x), int(y))
        if self.current_step < len(self.steps) - 1:
            self.current_step += 1
        self._update_overlay()

    def _go_back(self):
        if self._closed:
            return
        target_step = self.current_step
        if target_step not in self.recorded and target_step > 0:
            target_step -= 1
        self.current_step = target_step
        self.recorded.pop(target_step, None)
        self._update_overlay()

    def _navigate(self, delta):
        if self._closed:
            return
        self.current_step = max(0, min(len(self.steps) - 1, self.current_step + delta))
        self._update_overlay()

    def _cancel(self):
        if self._closed:
            return
        self._closed = True
        self._stop_listeners()
        if self.overlay and self.overlay.winfo_exists():
            self.overlay.destroy()
        self.overlay = None
        if getattr(self.app, "coordinate_recorder", None) is self:
            self.app.coordinate_recorder = None

    def _save_and_close(self):
        if self._closed:
            return
        for step_index, coords in self.recorded.items():
            step = self.steps[step_index]
            x, y = coords
            if step["type"] == "xy":
                if isinstance(step["var_key"], int):
                    x_var, y_var = self.app.tile_vars[step["var_key"]]
                    x_var.set(x)
                    y_var.set(y)
                else:
                    x_name, y_name = step["var_key"]
                    getattr(self.app, x_name).set(x)
                    getattr(self.app, y_name).set(y)
            elif step["type"] == "x_only":
                self.app.tile_vars[step["var_key"]][0].set(x)
            elif step["type"] == "y_only":
                self.app.tile_vars[step["var_key"]][1].set(y)
        if hasattr(self.app, "update_all_tiles"):
            self.app.root.after(0, self.app.update_all_tiles)
        self._cancel()

    def _stop_listeners(self):
        for listener_name in ("mouse_listener", "kb_listener"):
            listener = getattr(self, listener_name)
            if not listener:
                continue
            try:
                listener.stop()
            except Exception as e:
                if hasattr(self.app, "log_message"):
                    self.app.log_message(f"[WARN] Failed to stop {listener_name}: {e}")
            finally:
                setattr(self, listener_name, None)
