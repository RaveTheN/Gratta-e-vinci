"""Small GUI lifecycle test; physical mouse and listeners are never started."""
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from client_store import ClientStore
from coordinate_manager import CoordinateRecorder
from gratta_e_vinci_gui import BalanceDialog, GrattaEVinciGUI
from tests.test_lan_system import calibration


class SmokeTest(unittest.TestCase):
    def test_pairing_guidance_and_initial_balance_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = tk.Tk()
            root.withdraw()
            with patch("pyautogui.click", side_effect=AssertionError("Real click")), \
                 patch("pyautogui.moveTo", side_effect=AssertionError("Real mouse movement")), \
                 patch("pyautogui.position", return_value=(100, 120)):
                app = GrattaEVinciGUI(root, ClientStore(Path(directory) / "client.sqlite3"), start_services=False)
                try:
                    self.assertTrue(app.ready_button.instate(["disabled"]))
                    self.assertTrue(app.address_button.instate(["disabled"]))
                    app.profile_confirmed.set(True)
                    app.fields["name"].set("Nome modificato")
                    app.save_profile()
                    self.assertTrue(app.profile_confirmed.get())
                    app.pair()
                    self.assertIsNone(app.pair_thread)
                    self.assertIn("Genera codice monouso", app.error_var.get())
                    app.pair_code.insert(0, "copied-code")
                    with patch("gratta_e_vinci_gui.BalanceDialog", return_value=SimpleNamespace(result=None)):
                        app.pair()
                    self.assertIsNone(app.pair_thread)
                    async def fake_associate(store, code):
                        self.assertEqual(code, "copied-code")
                        self.assertEqual(store.snapshot()["balance"], 19750)
                        store.update(connection={"url": "https://master.test:8766"})
                    with patch("gratta_e_vinci_gui.BalanceDialog", return_value=SimpleNamespace(result={"balance": 19750, "reason": "Saldo verificato sul gioco"})), \
                         patch("gratta_e_vinci_gui.associate", side_effect=fake_associate) as pair:
                        app.pair()
                        app.pair_thread.join(timeout=2)
                        self.assertFalse(app.pair_thread.is_alive())
                        pair.assert_awaited_once()
                    app._render_status()
                    self.assertTrue(app.ready_button.instate(["!disabled"]))
                    self.assertTrue(app.address_button.instate(["!disabled"]))
                    self.assertTrue(app.pair_button.instate(["disabled"]))
                    self.assertFalse(app.client.armed.is_set())
                    self.assertTrue(app.store.snapshot()["confirmed"])
                    app.unpair()
                    self.assertTrue(app.store.snapshot()["unpair_requested"])
                    self.assertEqual(app.store.snapshot()["commands"][0]["action"], "unpair")
                    self.assertFalse(app.store.finish_unpair())
                    app._render_status()
                    self.assertTrue(app.ready_button.instate(["disabled"]))
                    self.assertTrue(app.unpair_button.instate(["disabled"]))
                finally:
                    app.on_closing()

    def create_app(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = tk.Tk()
        root.withdraw()
        for method in ("click", "moveTo"):
            guard = patch("pyautogui." + method, side_effect=AssertionError("Real mouse action"))
            guard.start()
            self.addCleanup(guard.stop)
        position = patch("pyautogui.position", return_value=(100, 120))
        position.start()
        self.addCleanup(position.stop)
        app = GrattaEVinciGUI(root, ClientStore(Path(directory.name) / "client.sqlite3"), start_services=False)
        self.addCleanup(app.on_closing)
        return app

    def test_balance_dialog_accepts_actual_amount_and_never_defaults_to_loss(self):
        app = self.create_app()
        state = app.store.snapshot()
        state.update(balance=19680, master_round={"id": "opened", "status": "uncertain"})
        with patch("tkinter.simpledialog.Dialog.__init__", return_value=None):
            dialog = BalanceDialog(app.root, state)
        holder = tk.Frame(app.root)
        dialog.body(holder)
        self.assertEqual(dialog.amount_var.get(), "")
        dialog.amount_var.set("1,999.91")
        self.assertTrue(dialog.validate())
        self.assertEqual(dialog.result, {"balance": 1999910, "reason": "Saldo verificato sul gioco", "outcome": "unknown"})
        dialog.outcome_var.set("Vinta e incassata")
        self.assertTrue(dialog.validate())
        self.assertEqual(dialog.result["outcome"], "win")
        dialog.amount_var.set("non un importo")
        with patch("gratta_e_vinci_gui.messagebox.showerror") as error:
            self.assertFalse(dialog.validate())
        error.assert_called_once()

    def test_euro_fields_and_balance_confirmation_wait_for_master(self):
        app = self.create_app()
        self.assertEqual(app.fields["stake"].get(), "0,10")
        self.assertIn("0,00 €", app.balance_var.get())

    def test_reset_waits_for_master_before_clearing_display(self):
        app = self.create_app()
        app.store.update(balance=1999910, confirmed=True, connection={"url": "https://master.test:8766"})
        app.profile_confirmed.set(True)
        app.last_reply = {"session": {"status": "active", "progress": 3000}, "device": {"last_result": {"outcome": "win"}}}
        app._render_status()
        self.assertIn("3,00 €", app.session_var.get())
        with patch("gratta_e_vinci_gui.messagebox.askyesno", return_value=True), \
             patch.object(app.client, "reset_local", return_value=None, create=True):
            app.reset_local()
        self.assertEqual(app.store.snapshot()["balance"], 1999910)
        self.assertTrue(app.profile_confirmed.get())
        self.assertIn("attendo la dissociazione", app.balance_sync_var.get())
        app.store.update(balance=0, confirmed=False, connection=None, config=app.store.snapshot()["config"])
        app.ui_queue.put(("reset", Path("archivio.sqlite3")))
        app._poll()
        self.assertIsNone(app.last_reply)
        self.assertFalse(app.profile_confirmed.get())
        self.assertIn("0,00 €", app.balance_var.get())
        self.assertEqual(app.session_var.get(), "Nessuna sessione")
        app.store.update(balance=19680, confirmed=True, connection={"url": "https://master.test:8766"})
        with patch("gratta_e_vinci_gui.BalanceDialog", return_value=SimpleNamespace(result={"balance": 1999910, "reason": "Saldo verificato sul gioco"})):
            app.correct_balance()
        self.assertEqual(app.store.snapshot()["balance"], 19680)
        self.assertIn("attendo la conferma", app.balance_sync_var.get())
        state = app.store.snapshot()
        command = state["commands"][-1]
        self.assertEqual(command["action"], "balance")
        self.assertEqual(command["payload"]["balance"], 1999910)
        reply = {"ack": 0, "command_id": command["id"], "session": None,
                 "device": {"balance": 1999910, "config": state["config"], "revision": 1, "error": "", "round": None}}
        app.store.reply(reply)
        app.ui_queue.put(("reply", reply))
        app._poll()
        self.assertIn("confermato dal master: 1.999,91 €", app.balance_sync_var.get())
        self.assertIn("1.999,91 €", app.balance_var.get())
        with patch("gratta_e_vinci_gui.BalanceDialog", return_value=SimpleNamespace(result={"balance": 2000000, "reason": "Nuova verifica"})):
            app.correct_balance()
        reply.update(command_id=app.balance_command_id, command_error="Partita ancora in corso")
        app.store.reply(reply)
        app.ui_queue.put(("reply", reply))
        app._poll()
        self.assertIn("rifiutata dal master: Partita ancora in corso", app.balance_sync_var.get())
        self.assertEqual(app.store.snapshot()["balance"], 1999910)

    def test_balance_with_unknown_round_queues_reconciliation_and_reset_is_explicit(self):
        app = self.create_app()
        app.store.update(confirmed=True, connection={"url": "https://master.test:8766"},
                         master_round={"id": "opened", "status": "uncertain"})
        with patch("gratta_e_vinci_gui.BalanceDialog", return_value=SimpleNamespace(result={"balance": 1999910, "reason": "Saldo verificato sul gioco", "outcome": "unknown"})):
            app.correct_balance()
        command = app.store.snapshot()["commands"][-1]
        self.assertEqual(command["action"], "reconcile")
        self.assertEqual(command["payload"]["outcome"], "unknown")
        with patch("gratta_e_vinci_gui.messagebox.askyesno", return_value=False), \
             patch.object(app.client, "reset_local", create=True) as reset:
            app.reset_local()
            reset.assert_not_called()
        def reset_data():
            app.store.update(balance=0, confirmed=False, connection=None, master_round=None, commands=[])
            return Path("archivio.sqlite3")
        app.profile_confirmed.set(True)
        with patch("gratta_e_vinci_gui.messagebox.askyesno", return_value=True), \
             patch.object(app.client, "reset_local", side_effect=reset_data, create=True) as reset:
            app.reset_local()
            reset.assert_called_once()
        self.assertFalse(app.store.snapshot()["confirmed"])
        self.assertFalse(app.profile_confirmed.get())
        self.assertIsNone(app.balance_command_id)
        self.assertIn("0,00 €", app.balance_var.get())

    def test_light_client_gui_and_close(self):
        with tempfile.TemporaryDirectory() as directory:
            root = tk.Tk()
            root.withdraw()
            errors = []
            root.report_callback_exception = lambda *args: errors.append(args)
            with patch("pyautogui.click", side_effect=AssertionError("Real click")), \
                 patch("pyautogui.moveTo", side_effect=AssertionError("Real mouse movement")), \
                 patch("pyautogui.position", return_value=(100, 120)):
                app = GrattaEVinciGUI(root, ClientStore(Path(directory) / "client.sqlite3"), start_services=False)
                self.assertEqual([app.notebook.tab(t, "text") for t in app.notebook.tabs()],
                                 ["Stato", "Calibrazione", "Cambio/reset puntata", "Tempi"])
                self.assertFalse(hasattr(app, "bulk_laptops"))
                app.store.update(calibration=calibration())
                app.load_calibration()
                app.step_type.set("Attendi")
                app.step_seconds.set("0,5")
                app.add_step()
                with patch("pyautogui.size", return_value=(100, 100)):
                    app.save_advanced()
                self.assertEqual(app.store.snapshot()["calibration"]["steps"][-1], {"action": "wait", "seconds": 0.5})
                app.step_list.append({"action": "wait", "seconds": 2})
                self.assertEqual(len(app.store.snapshot()["calibration"]["steps"]), 3)
                app.arm()
                self.assertFalse(app.client.armed.is_set())
                root.after(150, app.on_closing)
                root.mainloop()
            self.assertFalse(errors)

    def test_difficulty_coordinates_recorder_and_calibration_save(self):
        app = self.create_app()
        app.store.update(calibration=calibration())
        app.load_calibration()
        recorder = CoordinateRecorder(app)
        steps = {step["var_key"]: index for index, step in enumerate(recorder.steps) if isinstance(step["var_key"], tuple)}
        self.assertEqual(len(recorder.steps), 14)
        recorder.recorded[steps[("difficulty_lower_x_var", "difficulty_lower_y_var")]] = (82, 80)
        recorder.recorded[steps[("difficulty_raise_x_var", "difficulty_raise_y_var")]] = (83, 80)
        recorder._save_and_close()
        self.assertEqual((app.difficulty_lower_x_var.get(), app.difficulty_lower_y_var.get()), (82, 80))
        self.assertEqual((app.difficulty_raise_x_var.get(), app.difficulty_raise_y_var.get()), (83, 80))
        with patch("pyautogui.size", return_value=(100, 100)):
            app.save_calibration()
        self.assertEqual(app.error_var.get(), "")
        saved = app.store.snapshot()["calibration"]
        self.assertEqual(saved["difficulty_lower"], [82, 80])
        self.assertEqual(saved["difficulty_raise"], [83, 80])

    def test_timing_fields_are_explicit_independent_and_scrollable(self):
        app = self.create_app()
        app.store.update(calibration=calibration())
        app.load_calibration()
        self.assertEqual(set(app.delay_vars), set(app.store.snapshot()["calibration"]["delays"]))
        before = app.store.snapshot()["calibration"]["delays"]
        app.delay_vars["play"].set("0,7")
        app.delay_vars["collect"].set("0,8")
        app.delay_vars["tile"].set("0,9")
        app.delay_vars["second_tile"].set("1,1")
        app.delay_vars["after_click"].set("0,05")
        with patch("pyautogui.size", return_value=(100, 100)):
            app.save_advanced("timing")
        self.assertEqual(app.error_var.get(), "")
        saved = app.store.snapshot()["calibration"]["delays"]
        self.assertEqual([saved[k] for k in ("play", "collect", "tile", "second_tile", "after_click")], [0.7, 0.8, 0.9, 1.1, 0.05])
        self.assertEqual(saved["after_tile"], before["after_tile"])
        self.assertEqual(saved["after_second_tile"], before["after_second_tile"])
        self.assertIn("somma", app.delay_hints["after_click"])
        self.assertIn("Prima seconda cella", app.delay_hints["second_tile"])
        app.delay_entries["second_tile"].event_generate("<FocusIn>")
        app.root.update_idletasks()
        self.assertEqual(app.timing_help_var.get(), app.delay_hints["second_tile"])
        app.notebook.select(app.tabs[3])
        with patch.object(app.timing_canvas, "yview_scroll") as scroll:
            app._timing_scroll(SimpleNamespace(delta=-120))
        scroll.assert_called_once_with(1, "units")
        self.assertEqual(set(app.scroll_canvases), {str(tab) for tab in app.tabs})
        entry = app.delay_entries["between"]
        with patch.object(app.timing_canvas, "bbox", return_value=(0, 0, 800, 1500)), \
             patch.object(app.timing_canvas, "winfo_height", return_value=300), \
             patch.object(app.timing_canvas, "winfo_rooty", return_value=0), \
             patch.object(app.timing_canvas, "canvasy", side_effect=lambda y: y + 500), \
             patch.object(app.timing_canvas, "yview_moveto") as reveal, \
             patch.object(entry, "winfo_height", return_value=20), \
             patch.object(entry, "winfo_rooty", return_value=-20) as position:
            app._scroll_focus(SimpleNamespace(widget=entry))
            reveal.assert_called_once_with(480 / 1500)
            reveal.reset_mock()
            position.return_value = 400
            app._scroll_focus(SimpleNamespace(widget=entry))
            reveal.assert_called_once_with(620 / 1500)
        self.assertFalse(app.client.armed.is_set())


if __name__ == "__main__":
    unittest.main()
