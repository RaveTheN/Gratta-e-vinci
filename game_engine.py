"""Game runtime engine and automation adapter wiring."""

from __future__ import annotations

import asyncio
import math
import random
import time
from typing import Any

import pyautogui
from pynput import keyboard

from game_config import GRINDING_STEP, TEST_MODE_BOARD_SIZE, TEST_MODE_MINE_CONFIG, WIN_MULTIPLIERS


class TkAutomationAdapter:
    """Adapter for physical game automation actions."""

    def __init__(self, app, color_detector):
        self.app = app
        self.color_detector = color_detector

    async def play_or_collect(self):
        await asyncio.sleep(self.app.sleep_play_or_collect_var.get())
        pyautogui.click(self.app.play_x_var.get(), self.app.play_y_var.get())
        self.app.log_message("🎮 Clicked play/collect button")

    async def increase_bet(self):
        await asyncio.sleep(self.app.sleep_increase_bet_var.get())
        pyautogui.click(self.app.raise_x_var.get(), self.app.raise_y_var.get())
        current_index = self.app.bet_values.index(self.app.bet) if self.app.bet in self.app.bet_values else self.app.tries
        self.app.bet = round(self.app.bet_values[min(current_index + 1, len(self.app.bet_values) - 1)], 2)

    async def decrease_bet(self):
        await asyncio.sleep(self.app.sleep_decrease_bet_var.get())
        pyautogui.click(self.app.lower_x_var.get(), self.app.lower_y_var.get())
        current_index = self.app.bet_values.index(self.app.bet) if self.app.bet in self.app.bet_values else 0
        self.app.bet = round(self.app.bet_values[max(current_index - 1, 0)], 2)

    async def decrease_bet_force(self, min_bet):
        for _ in range(len(self.app.bet_values)):
            await asyncio.sleep(self.app.sleep_decrease_bet_force_var.get())
            pyautogui.click(self.app.lower_x_var.get(), self.app.lower_y_var.get())
        self.app.bet = round(min_bet, 2)
        self.app.log_message(f"🔽 Bet forced to minimum: {self.app.format_money(self.app.bet)}")

    async def decrease_difficulty_force(self, silent=False):
        lx = self.app.lower_diff_x_var.get()
        ly = self.app.lower_diff_y_var.get()
        if lx == 0 and ly == 0:
            return
        for _ in range(5):
            await asyncio.sleep(self.app.sleep_decrease_diff_force_var.get())
            pyautogui.click(lx, ly)
        self.app.current_difficulty = "low"
        if not silent:
            self.app.log_message("🔽 Difficoltà forzata al minimo (low)")

    async def set_difficulty(self, target_difficulty):
        if self.app.current_difficulty == target_difficulty:
            return
        await self.decrease_difficulty_force(silent=True)
        rx = self.app.raise_diff_x_var.get()
        ry = self.app.raise_diff_y_var.get()
        if rx == 0 and ry == 0:
            return
        clicks = {"low": 0, "medium": 1, "high": 2}.get(target_difficulty, 0)
        for _ in range(clicks):
            await asyncio.sleep(self.app.sleep_set_difficulty_var.get())
            pyautogui.click(rx, ry)
        self.app.current_difficulty = target_difficulty
        if clicks > 0:
            self.app.log_message(f"🎯 Difficoltà impostata a: {target_difficulty}")

    async def click_tile(self, point, tile_number):
        await asyncio.sleep(self.app.sleep_click_tile_var.get())
        pyautogui.click(point.x, point.y)
        self.app.log_message(f"🎯 Clicked tile {tile_number} at ({point.x}, {point.y})")

    def read_color(self, point):
        try:
            return self.color_detector.read_color_at_point(point)
        except Exception as e:
            self.app.log_message(f"❌ Error reading color: {e}")
            return {"r": 0, "g": 0, "b": 0, "a": 255}

    def is_blue(self, color):
        return self.color_detector.is_color_in_range_blue(color, self.app.target_blue)

    def is_red(self, color):
        return self.color_detector.is_color_in_range_red(color, self.app.target_red)

    async def click_xy(self, x, y, pause):
        pyautogui.click(x, y)
        await asyncio.sleep(pause)


class GameEngine:
    """Owns runtime loop/strategy/state transitions, delegating I/O to adapter."""

    def __init__(self, app, adapter: TkAutomationAdapter):
        self.app = app
        self.adapter = adapter

    def _is_running(self):
        if hasattr(self.app, "running_event"):
            return self.app.running_event.is_set()
        return bool(self.app.game_running)

    def _is_stop_requested(self):
        if hasattr(self.app, "stop_event"):
            return self.app.stop_event.is_set()
        return bool(self.app.escape_pressed)

    def _get_min_bet_for_selected_mode(self):
        selected_mode_name = self.app.mode_var.get()
        if selected_mode_name == "custom" and self.app.custom_mode:
            return round(self.app.custom_mode[0]["b"], 2)
        if selected_mode_name in self.app.betting_modes and self.app.betting_modes[selected_mode_name]:
            return round(self.app.betting_modes[selected_mode_name][0], 2)
        return 0.1

    def _get_target_bet_for_try(self, tries=None, selected_mode_name=None):
        if tries is None:
            tries = self.app.tries
        if selected_mode_name is None:
            selected_mode_name = self.app.mode_var.get()
        if selected_mode_name == "custom" and self.app.custom_mode:
            step_idx = min(tries, len(self.app.custom_mode) - 1)
            return round(self.app.custom_mode[step_idx]["b"], 2)
        if selected_mode_name in self.app.betting_modes and self.app.betting_modes[selected_mode_name]:
            mode_array = self.app.betting_modes[selected_mode_name]
            step_idx = min(tries, len(mode_array) - 1)
            return round(mode_array[step_idx], 2)
        return 0.1

    def _get_round_config_for_strategy(self):
        selected_mode_name = self.app.mode_var.get()
        grinding_enabled = bool(self.app.grinding_mode_var.get())
        step_idx = None
        max_step_idx = None
        if self.app.grinding_active:
            max_picks = self.app.get_grinding_picks()
            round_difficulty = GRINDING_STEP["d"]
            target_bet = round(GRINDING_STEP["b"], 2)
            strategy_source = "grinding"
        elif selected_mode_name == "custom" and self.app.custom_mode:
            step_idx = min(self.app.tries, len(self.app.custom_mode) - 1)
            max_step_idx = len(self.app.custom_mode) - 1
            step_data = self.app.custom_mode[step_idx]
            max_picks = step_data["p"]
            round_difficulty = step_data["d"]
            target_bet = round(step_data["b"], 2)
            strategy_source = "custom"
        else:
            max_picks = self.app.max_picks_var.get()
            round_difficulty = self.app.difficulty_var.get()
            target_bet = self._get_target_bet_for_try(self.app.tries, selected_mode_name)
            if selected_mode_name in self.app.betting_modes and self.app.betting_modes[selected_mode_name]:
                step_idx = min(self.app.tries, len(self.app.betting_modes[selected_mode_name]) - 1)
                max_step_idx = len(self.app.betting_modes[selected_mode_name]) - 1
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
            "multiplier": self.app.get_win_multiplier(round_difficulty, max_picks),
        }

    def validate_settings(self):
        starting_cash = self.app.starting_cash_var.get()
        if starting_cash <= 0:
            raise ValueError("Starting cash must be positive")
        if self.app.mode_var.get() != "custom":
            max_picks = self.app.max_picks_var.get()
            if max_picks not in [1, 2, 3, 4]:
                raise ValueError("Max picks must be between 1 and 4")
        return True

    def initialize_game_variables(self):
        self.app.current_cash = round(self.app.starting_cash_var.get(), 2)
        self.app.highest_cash = self.app.current_cash
        self.app.lowest_cash = self.app.current_cash
        initial_bet = self._get_min_bet_for_selected_mode()
        self.app.bet = round(initial_bet, 2)
        self.app.highest_bet = round(initial_bet, 2)
        self.app.picks = 0
        self.app.tries = 0
        self.app.rounds = 0
        self.app.loss = 0.0
        self.app.total_win = 0.0
        self.app.randoms = []
        self.app.grinding_active = False
        self.app.grinding_saved_balance = None
        self.app.current_difficulty = None
        self.app.log_message(f"💰 Initialized with cash: {self.app.format_money(self.app.current_cash)}")
        self.app.log_message(f"🎯 Target win: {self.app.format_money(self.app.target_win_var.get())}")
        self.app.update_stats_display()

    def update_tiles_from_gui(self):
        self.app.tiles = self.app.coordinate_manager.build_tile_points(self.app.tile_vars)

    def start_keyboard_listener(self):
        def on_key_press(key):
            if key == keyboard.Key.esc:
                self.app.escape_pressed = True
                if hasattr(self.app, "stop_event"):
                    self.app.stop_event.set()
                if hasattr(self.app, "running_event"):
                    self.app.running_event.clear()
                self.app.log_message("🛑 ESCAPE key pressed!")
                self.app.root.after(0, self.app.stop_game)
                return False

        self.app.keyboard_listener = keyboard.Listener(on_press=on_key_press)
        self.app.keyboard_listener.start()

    def stop_keyboard_listener(self):
        if self.app.keyboard_listener:
            self.app.keyboard_listener.stop()
            self.app.keyboard_listener = None

    async def set_bet_value(self, target_bet):
        target_bet = round(target_bet, 2)
        if target_bet not in self.app.bet_values:
            self.app.log_message(f"[WARN] Bet {self.app.format_money(target_bet)} non valida per set_bet_value")
            return
        old_bet = self.app.bet
        while self.app.bet < target_bet:
            await self.adapter.increase_bet()
        while self.app.bet > target_bet:
            await self.adapter.decrease_bet()
        if self.app.bet != old_bet:
            direction = "📈" if self.app.bet > old_bet else "📉"
            self.app.log_message(f"{direction} Bet: {self.app.format_money(old_bet)} → {self.app.format_money(self.app.bet)}")

    def generate_random_tile(self):
        available_tiles = [1, 2, 3, 4, 5, 6, 11, 16, 21]
        unused_tiles = [tile for tile in available_tiles if tile not in self.app.randoms]
        if not unused_tiles:
            self.app.randoms = []
            unused_tiles = available_tiles
        tile_number = random.choice(unused_tiles)
        self.app.randoms.append(tile_number)
        self.app.log_message(f"🎲 Generated random tile: {tile_number}")
        return tile_number

    async def execute_init_steps(self):
        if not self.app.init_steps:
            self.app.log_message("ℹ️ Nessuno step di inizializzazione configurato.")
            return
        self.app.log_message(f"🚀 Inizializzazione: {len(self.app.init_steps)} step in esecuzione...")
        for i, step in enumerate(self.app.init_steps):
            if self._is_stop_requested():
                break
            action = step.get("action")
            self.app.log_message(f"  ⚙️  [{i + 1}/{len(self.app.init_steps)}] {self.app._step_action_labels.get(action, action)}")
            if action == "set_bet_min":
                await self.adapter.decrease_bet_force(self._get_min_bet_for_selected_mode())
            elif action == "raise_difficulty":
                for _ in range(step.get("times", 1)):
                    await self.adapter.click_xy(self.app.raise_diff_x_var.get(), self.app.raise_diff_y_var.get(), self.app.sleep_init_raise_diff_var.get())
            elif action == "lower_difficulty":
                for _ in range(step.get("times", 1)):
                    await self.adapter.click_xy(self.app.lower_diff_x_var.get(), self.app.lower_diff_y_var.get(), self.app.sleep_init_lower_diff_var.get())
            elif action == "wait":
                await asyncio.sleep(step.get("seconds", 1))
            elif action == "click":
                await self.adapter.click_xy(step.get("x", 0), step.get("y", 0), self.app.sleep_init_click_var.get())
        self.app.log_message("✅ Inizializzazione completata.")

    async def main_game_loop(self):
        max_rounds = self.app.max_rounds_var.get()
        target_win = self.app.target_win_var.get()
        max_loss = self.app.max_loss_var.get()
        wait_selected = self.app.wait_selected_var.get()
        self.app.log_message("🎮 Starting REAL game automation...")
        self.app.log_message("⚠️ Make sure your game window is positioned correctly!")
        await self.execute_init_steps()
        if self.app.mode_var.get() != "custom":
            await self.adapter.set_difficulty(self.app.difficulty_var.get())
        else:
            await self.adapter.decrease_difficulty_force()
        while self._is_running() and not self._is_stop_requested():
            if self.app.rounds >= max_rounds:
                self.app.log_message("Reached maximum rounds!")
                break
            if self.app.current_cash >= target_win:
                self.app.log_message("🎉 Reached target win!")
                break
            if self.app.loss >= max_loss:
                self.app.log_message("💸 Reached maximum loss!")
                break
            if self.app.current_cash < self.app.bet:
                self.app.log_message("💀 Insufficient cash!")
                break
            progress = (self.app.rounds / max_rounds) * 100 if max_rounds > 0 else 100
            self.app.root.after(0, lambda: self.app.progress_var.set(progress))
            self.app.root.after(0, lambda: self.app.progress_label.config(text=f"Round {self.app.rounds + 1}/{max_rounds}"))
            if wait_selected and self.app.rounds > 0:
                wait_time = random.randint(60, 360)
                self.app.log_message(f"⏰ Waiting {wait_time//60}m {wait_time%60}s before next round...")
                await asyncio.sleep(wait_time)
            await self.play_real_game_round()
            self.app.root.after(0, self.app.update_stats_display)
            await asyncio.sleep(self.app.sleep_between_rounds_var.get())
        self.app.root.after(0, self.app.stop_game)
        self.app.log_message("=== GAME ENDED ===")
        self.app.log_message(f"Final cash: {self.app.format_money(self.app.current_cash)}")
        self.app.log_message(f"Highest cash: {self.app.format_money(self.app.highest_cash)}")
        self.app.log_message(f"Highest bet: {self.app.format_money(self.app.highest_bet)}")

    async def play_real_game_round(self):
        round_config = self._get_round_config_for_strategy()
        selected_mode_name = round_config["selected_mode_name"]
        step_idx = round_config["step_idx"]
        max_step_idx = round_config["max_step_idx"]
        grinding_enabled = round_config["grinding_enabled"]
        max_picks = round_config["max_picks"]
        round_difficulty = round_config["round_difficulty"]
        multiplier = round_config["multiplier"]
        if self.app.grinding_active:
            await self.adapter.set_difficulty(round_difficulty)
            await self.set_bet_value(GRINDING_STEP["b"])
            if self.app.bet > self.app.highest_bet:
                self.app.highest_bet = round(self.app.bet, 2)
        elif selected_mode_name == "custom" and self.app.custom_mode:
            await self.adapter.set_difficulty(round_difficulty)
        self.app.picks = 0
        self.app.randoms = []
        round_active = True
        self.app.log_message(f"\n=== Round {self.app.rounds + 1} ===")
        self.app.log_message(f"[ROUND] Current bet: {self.app.format_money(self.app.bet)}")
        await self.adapter.play_or_collect()
        self.app.log_message(f"[ROUND] Started round - Cash deducted: {self.app.format_money(self.app.bet)}")
        self.app.current_cash = round(self.app.current_cash - self.app.bet, 2)
        self.app.log_message(f"💸 New Balance: {self.app.format_money(self.app.current_cash)}")
        while round_active and self.app.picks < max_picks:
            if self._is_stop_requested():
                round_active = False
                break
            tile_number = self.generate_random_tile()
            await asyncio.sleep(self.app.sleep_after_play_var.get())
            await self.adapter.click_tile(self.app.tiles[tile_number], tile_number)
            await asyncio.sleep(self.app.sleep_after_tile_click_var.get())
            color_detected = False
            retry_count = 0
            while not color_detected:
                if self._is_stop_requested():
                    round_active = False
                    break
                clicked_tile_position = self.app.tiles[tile_number]
                color = self.adapter.read_color(clicked_tile_position)
                if self.adapter.is_blue(color):
                    self.app.log_message(f"[HIT] Tile {tile_number} is BLUE")
                    self.app.picks += 1
                    color_detected = True
                    if self.app.picks >= max_picks:
                        self.app.log_message(f"[WIN] {max_picks} BLUES! ROUND WON!")
                        await self.adapter.play_or_collect()
                        win_amount = self.app.bet * multiplier
                        self.app.current_cash = round(self.app.current_cash + win_amount, 2)
                        self.app.total_win = round(self.app.total_win + win_amount, 2)
                        if self.app.current_cash > self.app.highest_cash:
                            self.app.highest_cash = round(self.app.current_cash, 2)
                        if self.app.grinding_active:
                            if self.app.grinding_saved_balance is not None and self.app.current_cash >= self.app.grinding_saved_balance:
                                self.app.grinding_active = False
                                self.app.tries = 0
                                self.app.picks = 0
                                await self.set_bet_value(self._get_min_bet_for_selected_mode())
                            else:
                                await self.set_bet_value(GRINDING_STEP["b"])
                        else:
                            self.app.tries = 0
                            self.app.picks = 0
                            await self.set_bet_value(self._get_min_bet_for_selected_mode())
                        round_active = False
                elif self.adapter.is_red(color):
                    self.app.log_message(f"[LOSS] Tile {tile_number} is RED - ROUND LOST!")
                    color_detected = True
                    if grinding_enabled and not self.app.grinding_active and step_idx == 0:
                        acceptable_range = self.app.grinding_range_var.get()
                        self.app.grinding_saved_balance = round(self.app.highest_cash - acceptable_range, 2)
                    self.app.tries += 1
                    self.app.picks = 0
                    round_active = False
                    reached_top_step = step_idx is not None and max_step_idx is not None and step_idx >= max_step_idx
                    if grinding_enabled and not self.app.grinding_active and reached_top_step and round(self.app.bet, 2) == round(GRINDING_STEP["b"], 2) and self.app.grinding_saved_balance is not None:
                        self.app.grinding_active = True
                    await asyncio.sleep(self.app.sleep_after_result_var.get())
                    if self.app.grinding_active:
                        await self.adapter.set_difficulty(GRINDING_STEP["d"])
                        await self.set_bet_value(GRINDING_STEP["b"])
                    else:
                        target_bet = self._get_target_bet_for_try(self.app.tries, selected_mode_name)
                        await self.set_bet_value(target_bet)
                    if self.app.bet > self.app.highest_bet:
                        self.app.highest_bet = round(self.app.bet, 2)
                    self.app.loss = max(0, round(self.app.highest_cash - self.app.current_cash, 2))
                    if self.app.loss >= self.app.max_loss_var.get():
                        self.app.game_running = False
                        if hasattr(self.app, "running_event"):
                            self.app.running_event.clear()
                        round_active = False
                        break
                else:
                    retry_count += 1
                    if retry_count == 1 or retry_count % 5 == 0:
                        tolerance = getattr(self.adapter.color_detector, "tolerance", "n/a")
                        self.app.log_message(f"[COLOR] Tile {tile_number} - Unknown color (attempt {retry_count})")
                        self.app.log_message(
                            f"   Expected: Blue RGB({self.app.target_blue['r']},{self.app.target_blue['g']},{self.app.target_blue['b']}) "
                            f"or Red RGB({self.app.target_red['r']},{self.app.target_red['g']},{self.app.target_red['b']})"
                        )
                        self.app.log_message(f"   Actual: RGB({color['r']}, {color['g']}, {color['b']})")
                        self.app.log_message(f"   Tolerance used: {tolerance}")
                        self.app.log_message(
                            f"   Waiting {self.app.sleep_color_retry_var.get()} second(s) and retrying color detection..."
                        )
                    await asyncio.sleep(self.app.sleep_color_retry_var.get())
        self.app.rounds += 1

    def _simulate_test_board(self, round_difficulty, max_picks):
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
        return {"mine_count": mine_count, "opened_tiles": opened_tiles, "coins_found": coins_found, "hit_mine": hit_mine}

    def _apply_test_win(self, round_config, verbose=True):
        win_amount = round(self.app.bet * round_config["multiplier"], 2)
        self.app.current_cash = round(self.app.current_cash + win_amount, 2)
        self.app.total_win = round(self.app.total_win + win_amount, 2)
        if verbose:
            self.app.log_message(
                f"[WIN] 💰 Won {self.app.format_money(win_amount)}! New balance: {self.app.format_money(self.app.current_cash)}"
            )
        if self.app.current_cash > self.app.highest_cash:
            self.app.highest_cash = round(self.app.current_cash, 2)
        if self.app.grinding_active:
            if self.app.grinding_saved_balance is not None and self.app.current_cash >= self.app.grinding_saved_balance:
                self.app.grinding_active = False
                self.app.tries = 0
                self.app.picks = 0
                self.app.bet = self._get_min_bet_for_selected_mode()
                self.app.log_message(
                    f"[GRIND] Completed: balance recovered ({self.app.format_money(self.app.current_cash)} >= "
                    f"{self.app.format_money(self.app.grinding_saved_balance)}). Bet reset to minimum."
                )
            else:
                self.app.bet = round(GRINDING_STEP["b"], 2)
                if verbose:
                    target_text = self.app.format_money(self.app.grinding_saved_balance or 0)
                    self.app.log_message(
                        f"[GRIND] Current balance {self.app.format_money(self.app.current_cash)} "
                        f"(target {target_text}), staying on fixed grinding step."
                    )
        else:
            self.app.tries = 0
            self.app.picks = 0
            self.app.bet = self._get_min_bet_for_selected_mode()
            if verbose:
                self.app.log_message(f"[WIN] Bet reset to minimum: {self.app.format_money(self.app.bet)}")

    def _apply_test_loss(self, round_config, verbose=True):
        step_idx = round_config["step_idx"]
        max_step_idx = round_config["max_step_idx"]
        grinding_enabled = round_config["grinding_enabled"]
        if grinding_enabled and not self.app.grinding_active and step_idx == 0:
            acceptable_range = self.app.grinding_range_var.get()
            self.app.grinding_saved_balance = round(self.app.highest_cash - acceptable_range, 2)
        self.app.tries += 1
        self.app.picks = 0
        reached_top_step = step_idx is not None and max_step_idx is not None and step_idx >= max_step_idx
        if grinding_enabled and not self.app.grinding_active and reached_top_step and round(self.app.bet, 2) == round(GRINDING_STEP["b"], 2) and self.app.grinding_saved_balance is not None:
            self.app.grinding_active = True
            self.app.log_message(
                f"[GRIND] Activated after last-step loss: repeating b={GRINDING_STEP['b']:.1f}, "
                f"p={self.app.max_picks_var.get()}, d={GRINDING_STEP['d']} until balance >= "
                f"{self.app.format_money(self.app.grinding_saved_balance)}"
            )
        if self.app.grinding_active:
            self.app.bet = round(GRINDING_STEP["b"], 2)
        else:
            self.app.bet = self._get_target_bet_for_try(self.app.tries, round_config["selected_mode_name"])
        if self.app.bet > self.app.highest_bet:
            self.app.highest_bet = round(self.app.bet, 2)
        if verbose:
            self.app.log_message(f"[LOSS] Bet updated to: {self.app.format_money(self.app.bet)} (try #{self.app.tries})")

    def _finish_test_mode(self, stop_reason):
        self.app.game_running = False
        if hasattr(self.app, "running_event"):
            self.app.running_event.clear()
        self.app.root.after(0, lambda: self.app.start_button.config(state="normal"))
        self.app.root.after(0, lambda: self.app.stop_button.config(state="disabled"))
        self.app.root.after(0, self.app.update_stats_display)
        self.app.root.after(0, lambda: self.app.progress_label.config(text=f"TEST MODE ended: {stop_reason}"))
        self.app.log_message("\n=== TEST MODE RESULTS ===")
        self.app.log_message(f"🛑 Stop reason: {stop_reason}")
        self.app.log_message(f"💰 Final cash: {self.app.format_money(self.app.current_cash)}")
        self.app.log_message(f"📈 Highest cash: {self.app.format_money(self.app.highest_cash)}")
        self.app.log_message(f"📉 Lowest cash: {self.app.format_money(self.app.lowest_cash)}")
        self.app.log_message(f"🔝 Highest bet: {self.app.format_money(self.app.highest_bet)}")
        self.app.log_message(f"📉 Total loss: {self.app.format_money(self.app.loss)}")
        self.app.log_message(f"🏁 Rounds played: {self.app.rounds}")
        profit_loss = round(self.app.current_cash - self.app.starting_cash_var.get(), 2)
        if profit_loss > 0:
            self.app.log_message(f"✅ Net profit: +{self.app.format_money(profit_loss)}")
        else:
            self.app.log_message(f"❌ Net loss: {self.app.format_money(profit_loss)}")
        self.app.log_message(f"🧪 TEST MODE ended: {stop_reason}")

    def _get_test_mode_delay(self):
        configured = max(0.0, float(self.app.sleep_between_rounds_var.get()))
        if self.app.rounds < 5:
            return min(0.08, max(0.02, configured * 0.15))
        if self.app.rounds < 25:
            return min(0.015, configured * 0.03)
        return 0.0

    def _is_test_round_verbose(self, round_number):
        return round_number <= 5 or round_number % 25 == 0

    def run_test_mode(self):
        stop_reason = "Simulation completed"
        try:
            max_rounds = self.app.max_rounds_var.get()
            target_win = self.app.target_win_var.get()
            max_loss = self.app.max_loss_var.get()
            while True:
                if self._is_stop_requested() or not self._is_running():
                    stop_reason = "Stopped by user"
                    break
                round_config = self._get_round_config_for_strategy()
                if self.app.rounds >= max_rounds:
                    stop_reason = "Reached maximum rounds"
                    break
                if self.app.current_cash >= target_win:
                    stop_reason = "Reached target win"
                    break
                if self.app.loss >= max_loss:
                    stop_reason = "Reached maximum loss"
                    break
                if self.app.current_cash < round_config["target_bet"]:
                    stop_reason = "Insufficient cash"
                    break
                self.app.bet = round(round_config["target_bet"], 2)
                self.app.picks = 0
                self.app.randoms = []
                if self.app.bet > self.app.highest_bet:
                    self.app.highest_bet = round(self.app.bet, 2)
                round_number = self.app.rounds + 1
                verbose_round = self._is_test_round_verbose(round_number)
                if verbose_round:
                    self.app.log_message(f"\n=== Test Round {round_number} ===")
                    self.app.log_message(
                        f"[ROUND] Strategy={round_config['strategy_source']} | "
                        f"Mode={round_config['selected_mode_name']} | Difficulty={round_config['round_difficulty']} | "
                        f"Picks target={round_config['max_picks']} | Mines={round_config['mine_count']} | "
                        f"Bet={self.app.format_money(self.app.bet)}"
                    )
                self.app.current_cash = round(self.app.current_cash - self.app.bet, 2)
                if verbose_round:
                    self.app.log_message(f"[ROUND] Started round - Cash deducted: {self.app.format_money(self.app.bet)}")
                    self.app.log_message(f"💸 New Balance: {self.app.format_money(self.app.current_cash)}")
                board_result = self._simulate_test_board(round_config["round_difficulty"], round_config["max_picks"])
                if verbose_round:
                    opened_summary = ", ".join(
                        f"T{entry['tile']}={'BLUE' if entry['outcome'] == 'coin' else 'RED'}"
                        for entry in board_result["opened_tiles"]
                    )
                    self.app.log_message(f"[BOARD] Opened tiles: {opened_summary}")
                self.app.picks = board_result["coins_found"]
                if board_result["hit_mine"]:
                    if verbose_round:
                        self.app.log_message(
                            f"[LOSS] Hit a RED tile after {board_result['coins_found']} blue(s). "
                            f"Balance remains {self.app.format_money(self.app.current_cash)}"
                        )
                    self._apply_test_loss(round_config, verbose=verbose_round)
                else:
                    if verbose_round:
                        self.app.log_message(
                            f"[WIN] {round_config['max_picks']} BLUE tiles found. "
                            f"Multiplier={round_config['multiplier']:.2f}"
                        )
                    self._apply_test_win(round_config, verbose=verbose_round)
                self.app.rounds += 1
                if self.app.current_cash > self.app.highest_cash:
                    self.app.highest_cash = round(self.app.current_cash, 2)
                self.app.lowest_cash = round(min(self.app.lowest_cash, self.app.current_cash), 2)
                self.app.loss = max(0, round(self.app.highest_cash - self.app.current_cash, 2))
                if round_number > 5 and round_number % 25 == 0:
                    self.app.log_message(
                        f"[SUMMARY] Round {round_number}: cash={self.app.format_money(self.app.current_cash)} | "
                        f"loss={self.app.format_money(self.app.loss)} | bet={self.app.format_money(self.app.bet)}"
                    )
                progress = 100 if max_rounds <= 0 else min(100, (self.app.rounds / max_rounds) * 100)
                self.app.root.after(0, lambda value=progress: self.app.progress_var.set(value))
                self.app.root.after(
                    0,
                    lambda rounds=self.app.rounds, total=max_rounds: self.app.progress_label.config(
                        text=f"Test round {rounds}/{total}"
                    ),
                )
                self.app.root.after(0, self.app.update_stats_display)
                time.sleep(self._get_test_mode_delay())
            if stop_reason == "Simulation completed":
                stop_reason = "Strategy loop completed"
        except Exception as e:
            stop_reason = f"Error: {e}"
            self.app.log_message(f"❌ TEST MODE error: {e}")
        finally:
            self._finish_test_mode(stop_reason)

    def run_game_async(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self.main_game_loop())
        finally:
            loop.close()

    # ---- Bulk Test ----

    def _build_bulk_snapshot(self):
        """Capture all settings needed for bulk simulation from the GUI (called once)."""
        mode = self.app.mode_var.get()
        if mode == "custom" and self.app.custom_mode:
            betting_sequence = [step["b"] for step in self.app.custom_mode]
        elif mode in self.app.bulk_betting_modes:
            betting_sequence = list(self.app.bulk_betting_modes[mode])
        else:
            betting_sequence = [0.1]

        win_multipliers = {
            d: {p: self.app.bulk_win_multiplier_vars[d][p].get() for p in [1, 2, 3, 4]}
            for d in ["low", "medium", "high"]
        }
        mine_config = {
            d: self.app.bulk_mine_config_vars[d].get()
            for d in ["low", "medium", "high"]
        }

        return {
            "starting_cash": self.app.starting_cash_var.get(),
            "target_profit": self.app.target_win_var.get() - self.app.starting_cash_var.get(),
            "max_loss": self.app.max_loss_var.get(),
            "max_rounds": self.app.max_rounds_var.get(),
            "mode": mode,
            "betting_sequence": betting_sequence,
            "max_picks": self.app.max_picks_var.get(),
            "difficulty": self.app.difficulty_var.get(),
            "grinding_enabled": bool(self.app.grinding_mode_var.get()),
            "grinding_range": self.app.grinding_range_var.get(),
            "p_random": bool(self.app.grinding_p_random_var.get()),
            "win_multipliers": win_multipliers,
            "mine_config": mine_config,
        }

    def run_bulk_test(self, n_runs, progress_cb, log_cb, stop_check, show_logs):
        """Run n_runs independent simulations and return aggregated results."""
        snapshot = self._build_bulk_snapshot()
        target_profit = snapshot["target_profit"]
        max_loss = snapshot["max_loss"]

        # Build threshold ranges
        if target_profit <= 100:
            profit_step = 1
        else:
            profit_step = math.ceil(target_profit / 100)
        profit_thresholds = list(range(profit_step, int(math.ceil(target_profit / profit_step) * profit_step) + 1, profit_step))
        if not profit_thresholds or profit_thresholds[-1] < target_profit:
            profit_thresholds.append(int(math.ceil(target_profit)))

        loss_step = 5
        max_loss_ceil = max(loss_step, math.ceil(max_loss / loss_step) * loss_step)
        loss_thresholds = list(range(loss_step, max_loss_ceil + 1, loss_step))

        success_counts = {(L, P): 0 for L in loss_thresholds for P in profit_thresholds}

        runs_completed = 0
        for i in range(n_runs):
            if stop_check():
                break
            profit_reached = self._run_single_bulk_game(snapshot)

            for P, max_dd in profit_reached.items():
                for L in loss_thresholds:
                    if max_dd <= L:
                        success_counts[(L, P)] += 1

            runs_completed = i + 1
            progress_cb(runs_completed, n_runs)

            if show_logs():
                reached_target = any(p >= target_profit for p in profit_reached)
                max_dd_final = max(profit_reached.values()) if profit_reached else 0
                status = "TARGET" if reached_target else "STOP"
                log_cb(f"[Run {runs_completed}] {status} | Profits reached: {len(profit_reached)} | Max DD: {max_dd_final:.2f}")

            if show_logs() and runs_completed % 2 == 0:
                log_cb("__CLEAR__")

        return (success_counts, profit_thresholds, loss_thresholds, snapshot, runs_completed)

    def _simulate_bulk_board(self, mine_count, max_picks):
        """Pure board simulation with explicit mine_count (no global access)."""
        board = ["mine"] * mine_count + ["coin"] * (TEST_MODE_BOARD_SIZE - mine_count)
        random.shuffle(board)
        coins_found = 0
        hit_mine = False
        indices = list(range(TEST_MODE_BOARD_SIZE))
        random.shuffle(indices)
        for idx in indices[:max_picks]:
            if board[idx] == "mine":
                hit_mine = True
                break
            coins_found += 1
        return coins_found, hit_mine

    def _run_single_bulk_game(self, snap):
        """Run one full simulation. Returns {profit_threshold: max_dd_when_first_reached}."""
        cash = snap["starting_cash"]
        starting_cash = cash
        target_profit = snap["target_profit"]
        max_loss = snap["max_loss"]
        max_rounds = snap["max_rounds"]
        sequence = snap["betting_sequence"]
        max_picks = snap["max_picks"]
        difficulty = snap["difficulty"]
        grinding_enabled = snap["grinding_enabled"]
        grinding_range = snap["grinding_range"]
        p_random = snap["p_random"]
        win_mults = snap["win_multipliers"]
        mine_cfg = snap["mine_config"]

        highest = cash
        max_dd_so_far = 0.0
        tries = 0
        rounds = 0
        max_step = len(sequence) - 1
        grinding_active = False
        grinding_saved_balance = None
        profit_reached = {}

        while rounds < max_rounds:
            # Determine current round params
            if grinding_active:
                rd = "high"
                mp = self._bulk_grinding_picks(cash, grinding_saved_balance, p_random, win_mults)
                bet = GRINDING_STEP["b"]
            else:
                rd = difficulty
                mp = max_picks
                bet = sequence[min(tries, max_step)]

            if cash < bet:
                break

            cash = round(cash - bet, 2)

            mine_count = mine_cfg[rd]
            multiplier = win_mults[rd][mp]
            coins_found, hit_mine = self._simulate_bulk_board(mine_count, mp)

            if hit_mine:
                # Loss
                step_idx = min(tries, max_step)
                if grinding_enabled and not grinding_active and step_idx == 0:
                    grinding_saved_balance = round(highest - grinding_range, 2)
                tries += 1
                reached_top = step_idx >= max_step
                if grinding_enabled and not grinding_active and reached_top and round(bet, 2) == round(GRINDING_STEP["b"], 2) and grinding_saved_balance is not None:
                    grinding_active = True
                if grinding_active:
                    pass  # bet will be set next iteration
                # no bet update needed here, it's recalculated at loop top
            else:
                # Win
                win_amount = round(bet * multiplier, 2)
                cash = round(cash + win_amount, 2)
                if cash > highest:
                    highest = round(cash, 2)
                if grinding_active:
                    if grinding_saved_balance is not None and cash >= grinding_saved_balance:
                        grinding_active = False
                        tries = 0
                else:
                    tries = 0

            if cash > highest:
                highest = round(cash, 2)
            current_dd = round(highest - cash, 2)
            if current_dd > max_dd_so_far:
                max_dd_so_far = current_dd

            # Check profit thresholds
            profit = round(cash - starting_cash, 2)
            if profit > 0:
                # Check each integer threshold up to target
                step = 1 if target_profit <= 100 else math.ceil(target_profit / 100)
                p_val = step
                while p_val <= profit and p_val <= target_profit:
                    if p_val not in profit_reached:
                        profit_reached[p_val] = max_dd_so_far
                    p_val += step
                # Also check the exact target
                if profit >= target_profit and target_profit not in profit_reached:
                    profit_reached[int(math.ceil(target_profit))] = max_dd_so_far

            rounds += 1

            # Stop conditions
            if profit >= target_profit:
                break
            if max_dd_so_far >= max_loss:
                break

        return profit_reached

    @staticmethod
    def _bulk_grinding_picks(cash, grinding_saved_balance, p_random, win_mults):
        """Determine picks during grinding (pure, no self.app access)."""
        b = GRINDING_STEP["b"]
        target = grinding_saved_balance if grinding_saved_balance is not None else 0
        for p in [1, 2, 3]:
            projected = cash + (b * win_mults["high"][p])
            if projected >= target:
                return p
        if p_random:
            return random.randint(1, 3)
        return 3
