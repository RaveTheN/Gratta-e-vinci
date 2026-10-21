"""Two-cell executor: no Tk variables, betting strategies or simulated bankrolls."""
import random
import time
import pyautogui
from color_detector import ColorDetector
from game_config import Point
from client_store import validate_calibration


class EmergencyStop(Exception):
    pass


class PreparationStopped(Exception):
    pass


class ScreenAdapter:
    def __init__(self, calibration):
        self.c = calibration
        self.detector = ColorDetector(calibration["blue"], calibration["red"], calibration["tolerance"])

    def size(self):
        return tuple(pyautogui.size())

    def click(self, point):
        if list(self.size()) != self.c["screen"]:
            raise RuntimeError("Geometria dello schermo cambiata")
        pyautogui.click(*point, _pause=False)

    def color(self, tile):
        color = self.detector.read_color_at_point(Point(*self.c["tiles"][str(tile)]))
        blue, red = self.detector.is_color_in_range_blue(color), self.detector.is_color_in_range_red(color)
        return "blue" if blue and not red else "red" if red and not blue else None

    def board(self):
        return self.detector.read_board({int(k): Point(*v) for k, v in self.c["tiles"].items()})


class GameEngine:
    def __init__(self, store, emergency, ordinary_stop, notify=lambda: None, adapter_factory=ScreenAdapter):
        self.store, self.emergency, self.ordinary_stop = store, emergency, ordinary_stop
        self.notify, self.adapter_factory = notify, adapter_factory
        self.setup_stop = None
        self.difficulty_prepared = False

    def wait(self, seconds):
        if self.emergency.wait(seconds):
            raise EmergencyStop("Arresto di emergenza")

    def preparation_wait(self, seconds, stop):
        if stop is None:
            self.wait(seconds)
            return
        deadline = time.monotonic() + seconds
        while True:
            if stop.is_set():
                raise PreparationStopped("Operazione fermata prima di Play")
            remaining = max(0, deadline - time.monotonic())
            self.wait(min(0.05, remaining))
            if stop.is_set():
                raise PreparationStopped("Operazione fermata prima di Play")
            if remaining <= 0.05:
                return

    def apply_bet(self, profile, revision, calibration):
        adapter = self.adapter_factory(calibration)
        validate_calibration(calibration, adapter.size(), profile)
        self.store.update(bet_in_progress=True, applied_stake=None, applied_revision=0)
        def wait(seconds):
            self.preparation_wait(seconds, self.setup_stop)
        def click(point):
            wait(0)
            adapter.click(point)
            wait(calibration["delays"]["after_click"])
        try:
            current = None
            for step in calibration["steps"]:
                wait(0)
                action = step["action"]
                if action == "reset":
                    for _ in calibration["bet_values"]:
                        wait(calibration["delays"]["reset"])
                        click(calibration["lower"])
                    current = 0
                elif action == "target":
                    target = calibration["bet_values"].index(profile["stake"])
                    for _ in range(target - current):
                        wait(calibration["delays"]["bet"])
                        click(calibration["raise"])
                    current = target
                elif action == "wait":
                    wait(step["seconds"])
                elif action == "click":
                    click(step["point"])
            if not self.difficulty_prepared:
                for _ in range(4):
                    wait(calibration["delays"]["difficulty_lower"])
                    click(calibration["difficulty_lower"])
                wait(calibration["delays"]["difficulty_raise"])
                click(calibration["difficulty_raise"])
                wait(calibration["delays"]["after_difficulty"])
                self.difficulty_prepared = True
            self.store.update(applied_revision=revision, applied_stake=profile["stake"])
        finally:
            self.store.update(bet_in_progress=False)

    def run_round(self, grant, calibration):
        adapter = self.adapter_factory(calibration)
        selected, observed, started = [], [], False
        beginning = time.time()
        try:
            validate_calibration(calibration, adapter.size(), grant["config"])
            if self.ordinary_stop.is_set() or self.emergency.is_set():
                self.store.emit("cancel", {"round": grant["id"], "reason": "Stop prima dell'avvio"})
                return
            pair = (random.sample(range(1, 26), 2) if grant["config"]["selection"] == "random"
                    else list(grant["config"]["pair"]))

            def click(point, action, delay):
                nonlocal started
                preparing = action == "play"
                if preparing:
                    self.preparation_wait(delay, self.ordinary_stop)
                else:
                    self.wait(delay)
                self.store.emit("intent", {"round": grant["id"], "action": action})
                started = True
                self.notify()
                self.wait(0)
                if preparing and self.ordinary_stop.is_set():
                    raise PreparationStopped("Stop prima di Play")
                adapter.click(point)
                self.wait(calibration["delays"]["after_click"])
            click(calibration["play"], "play", calibration["delays"]["play"])
            self.wait(calibration["delays"]["after_play"])
            for index, tile in enumerate(pair):
                click(calibration["tiles"][str(tile)], f"tile:{tile}", calibration["delays"]["tile" if index == 0 else "second_tile"])
                self.wait(calibration["delays"]["after_tile" if index == 0 else "after_second_tile"])
                color = None
                for attempt in range(3):
                    self.wait(0)
                    color = adapter.color(tile)
                    if color in ("blue", "red"):
                        break
                    if attempt < 2:
                        self.wait(calibration["delays"]["retry"])
                if color is None:
                    raise RuntimeError(f"Colore incerto sulla cella {tile}")
                selected.append(tile)
                observed.append(color)
                if color == "red":
                    break
            outcome = "loss" if observed[-1] == "red" else "win"
            if outcome == "win":
                click(calibration["play"], "collect", calibration["delays"]["collect"])
            board, complete, reason = [None] * 25, False, "unreadable"
            for attempt in range(3):
                self.wait(calibration["delays"]["reveal" if attempt == 0 else "board_retry"])
                try:
                    board = adapter.board()
                    matches = all(board[cell - 1] == color for cell, color in zip(selected, observed))
                    complete = all(c is not None for c in board) and board.count("red") == grant["config"]["mines"] and matches
                    reason = "" if complete else "unknown_cells" if None in board else "selected_cell_mismatch" if not matches else "mine_count_mismatch"
                except (OSError, ValueError, RuntimeError) as exc:
                    reason = str(exc)[:300]
                if complete:
                    break
            self.store.emit("result", {"round": grant["id"], "outcome": outcome, "selected": selected,
                                       "observed": observed, "board": board, "board_complete": complete,
                                       "board_reason": reason, "started": beginning, "ended": time.time()})
            self.notify()
        except Exception as exc:
            self.store.emit("uncertain" if started else "cancel",
                            {"round": grant["id"], "error": str(exc), "selected": selected, "observed": observed})
            if started or not self.ordinary_stop.is_set():
                if not started:
                    self.store.emit("error", {"error": str(exc)})
                self.emergency.set()
            self.notify()
