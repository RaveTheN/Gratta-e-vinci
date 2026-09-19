r"""Run with: .venv\Scripts\python.exe -m unittest discover -s tests"""

import asyncio
from pathlib import Path
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from unittest.mock import AsyncMock, patch

from openpyxl import load_workbook

from game_engine import GameEngine
from gratta_e_vinci_gui import GrattaEVinciGUI
from settings_manager import SettingsManager


class SmokeTest(unittest.TestCase):
    def test_gui_simulation_and_monitor_lifecycle(self):
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(lambda: root.destroy() if root.tk.call('info', 'commands', '.') else None)
        callback_errors = []
        root.report_callback_exception = lambda *error: callback_errors.append(error)
        defaults = SettingsManager().merge_with_defaults({})
        with patch('pyautogui.click', side_effect=AssertionError('Unexpected real click')), \
             patch('pyautogui.moveTo', side_effect=AssertionError('Unexpected mouse move')), \
             patch('pyautogui.position', return_value=(123, 456)) as position, \
             patch.object(SettingsManager, 'load_settings', return_value=defaults):
            app = GrattaEVinciGUI(root)
            notebook = next(widget for widget in root.winfo_children() if isinstance(widget, ttk.Notebook))
            self.assertEqual(len(notebook.tabs()), 8)
            root.after(250, root.quit)
            root.mainloop()
            self.assertGreaterEqual(position.call_count, 2)
            self.assertIn('123, 456', app.coord_label.cget('text'))

            app.max_rounds_var.set(3)
            app.game_running = True
            app.running_event.set()
            app.game_engine.initialize_game_variables()
            app.game_engine.run_test_mode()
            root.update()
            self.assertEqual(app.rounds, 3)
            self.assertFalse(app.game_running)
            self.assertIn('Reached maximum rounds', app.progress_label.cget('text'))

            app.starting_cash_var.set(100)
            app.target_win_var.set(101)
            app.max_loss_var.set(5)
            app.max_rounds_var.set(20)
            app.max_picks_var.set(1)
            app.bulk_betting_modes['normal'] = [1.0]
            for variable in app.bulk_mine_config_vars.values():
                variable.set(0)
            results = app.game_engine.run_bulk_test(3, lambda *_: None, lambda _: None,
                                                    lambda: False, lambda: False)
            counts, profits, losses, snapshot, runs = results
            self.assertEqual(runs, 3)
            self.assertEqual(counts[(5, 1)], 3)
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'results.xlsx'
                app._write_excel(path, counts, profits, losses, snapshot, runs)
                workbook = load_workbook(path)
                self.assertEqual(workbook.sheetnames, ['Griglia Win Rate', 'Impostazioni', 'Sommario'])
                self.assertEqual(workbook.worksheets[0]['B2'].value, 100)
                workbook.close()

            root.after_cancel(app.mouse_monitor_after_id)
            position.side_effect = RuntimeError('Position unavailable')
            app.start_mouse_monitoring()
            root.update()
            self.assertIsNone(app.mouse_monitor_after_id)
            self.assertIn('Position unavailable', app.status_text.get('1.0', 'end'))
            position.side_effect = None
            app.start_mouse_monitoring()
            timer = app.mouse_monitor_after_id
            with patch.object(root, 'after_cancel', wraps=root.after_cancel) as cancel:
                app.on_closing()
                cancel.assert_called_once_with(timer)
            self.assertFalse(app.running_event.is_set())
            self.assertEqual(callback_errors, [])

    def test_async_runner(self):
        engine = GameEngine(None, None)
        with patch.object(engine, 'main_game_loop', new_callable=AsyncMock) as loop:
            engine.run_game_async()
            loop.assert_awaited_once()
        with self.assertRaises(RuntimeError):
            asyncio.get_running_loop()
