"""Deterministic money/recovery tests: no real mouse clicks, screens or accounts."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import queue
import sqlite3
import sys
import tempfile
import threading
import unittest
import uuid
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Gratta e vinci Master"))
from coordinator import Coordinator
from client_store import ClientStore, default_calibration, validate_calibration
from game_engine import GameEngine
from mine_protocol import DEFAULT_CONFIG, config, money


class Clock:
    def __init__(self):
        self.now = 1802854800.0
    def __call__(self):
        return self.now
    def advance(self, value):
        self.now += value


def event(seq, kind, body):
    return {"id": str(uuid.uuid4()), "seq": seq, "kind": kind, "body": body, "time": 1.0}


def result(grant, outcome="win"):
    board = ["blue"] * 19 + ["red"] * 6
    if outcome == "loss":
        board[0], board[19] = "red", "blue"
    return {"round": grant["id"], "outcome": outcome, "selected": [1, 2] if outcome == "win" else [1],
            "observed": ["blue", "blue"] if outcome == "win" else ["red"],
            "board": board, "board_complete": True, "board_reason": ""}


def calibration():
    c = default_calibration()
    c.update({"tiles": {str(i): [10 + (i-1) % 5 * 10, 10 + (i-1) // 5 * 10] for i in range(1, 26)},
              "play": [70, 70], "lower": [80, 70], "raise": [90, 70],
              "difficulty_lower": [70, 80], "difficulty_raise": [80, 80], "screen": [100, 100]})
    c["delays"] = {k: 0 for k in c["delays"]}
    return c


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.clock = Clock()
        self.path = Path(self.temp.name) / "master.sqlite3"
        self.master = Coordinator(self.path, self.clock)

    def tearDown(self):
        self.master.close()
        self.temp.cleanup()

    def add(self, did="a", balance=20000, profile=None):
        token = self.master.register(did, profile or dict(DEFAULT_CONFIG), balance)
        self.sync(did)
        return token

    def sync(self, did="a", request=None, events=None, **values):
        return self.master.sync(did, {"ready": True, "busy": False, "events": events or [],
                                      "applied_revision": self.master.state["devices"][did]["revision"],
                                      "request": request, **values})

    def command(self, action, payload=None, command_id=None):
        return self.master.command(action, payload or {}, command_id or str(uuid.uuid4()))

    def test_default_and_mill_precision_validation(self):
        self.assertEqual(money("0,184"), 184)
        for bad in ("NaN", "Infinity", "0.0001", "-1", "1e999999999"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                money(bad)
        with self.assertRaises(ValueError):
            config({**DEFAULT_CONFIG, "multiplier": "1e999999999"})
        profile = {**DEFAULT_CONFIG, "multiplier": "1.84"}
        self.add(profile=profile)
        self.command("start")
        grant = self.sync(request="one")["grant"]
        self.assertEqual(self.master.state["devices"]["a"]["balance"], 19900)
        self.sync(events=[event(1, "result", result(grant))])
        self.assertEqual(self.master.state["devices"]["a"]["balance"], 20084)
        self.assertEqual(self.master.device_view("a")["session_net"], 84)
        self.assertEqual(self.master.device_view("a")["net"], 84)
        self.assertEqual(self.master.device_view("a")["wins"], 1)

    def test_grant_and_result_retries_are_idempotent_and_durable(self):
        self.add()
        self.command("start")
        grant = self.sync(request="one")["grant"]
        self.assertEqual(self.sync(request="one")["grant"]["id"], grant["id"])
        self.assertIsNone(self.sync(request="two")["grant"])
        e = event(1, "result", result(grant))
        self.sync(events=[e])
        self.sync(events=[e])
        self.assertEqual(self.master.state["devices"]["a"]["balance"], 20080)
        altered = deepcopy(e)
        altered["body"]["outcome"] = "loss"
        with self.assertRaises(ValueError):
            self.sync(events=[altered])
        self.master.close()
        self.master = Coordinator(self.path, self.clock)
        self.assertEqual(self.master.state["devices"]["a"]["balance"], 20080)
        self.assertEqual(self.master.session()["status"], "paused_manual")

    def test_difficulty_intent_keeps_round_reserved_and_cancel_safe(self):
        self.add()
        self.command("start")
        grant = self.sync(request="setup")['grant']
        self.sync(events=[event(1, "intent", {"round": grant["id"], "action": "difficulty_lower"}),
                          event(2, "intent", {"round": grant["id"], "action": "difficulty_raise"})])
        self.assertEqual(self.master.open_round("a")["status"], "reserved")
        self.sync(events=[event(3, "cancel", {"round": grant["id"], "reason": "Stop prima di Play"})], ready=False)
        self.assertIsNone(self.master.open_round("a"))
        self.assertEqual((self.master.device_view("a")["balance"], self.master.session()["net"]), (20000, 0))

    def test_trigger_includes_all_open_reservations(self):
        self.add("a")
        self.add("b")
        self.command("settings", {**self.master.state["settings"], "target": 80})
        self.command("start")
        a, b = self.sync("a", "a1")["grant"], self.sync("b", "b1")["grant"]
        self.sync("a", events=[event(1, "result", result(a))])
        self.assertEqual(self.master.session_view()["progress"], -20)
        self.assertEqual(self.master.session()["status"], "active")
        self.sync("b", events=[event(1, "result", result(b))])
        self.assertEqual(self.master.session()["status"], "closed")
        self.assertIsNone(self.sync("a", "late")["grant"])

    def test_command_retry_and_failed_storage_never_reserve_twice(self):
        self.add()
        command_id = str(uuid.uuid4())
        self.command("start", command_id=command_id)
        self.command("start", command_id=command_id)
        self.assertEqual(self.master.state["counts"][self.master.day()], 1)
        with self.assertRaises(ValueError):
            self.command("pause", command_id=command_id)
        with patch.object(self.master, "save_round", side_effect=OSError("Disco pieno")):
            with self.assertRaises(OSError):
                self.sync(request="failed")
        self.assertEqual(self.master.device_view("a")["balance"], 20000)
        self.assertIsNone(self.master.open_round("a"))
        self.assertEqual(self.master.session_view()["progress"], 0)

    def test_minimum_recovery_and_manual_pause_priority(self):
        self.add("a")
        self.add("b")
        self.command("settings", {**self.master.state["settings"], "minimum": 2})
        self.command("start")
        self.clock.advance(6)
        self.sync("a")
        self.assertEqual(self.master.session()["status"], "paused_minimum")
        self.sync("b")
        self.assertEqual(self.master.session()["status"], "active")
        self.command("pause")
        self.sync("a")
        self.sync("b")
        self.assertEqual(self.master.session()["status"], "paused_manual")

    def test_resume_explains_blockers_and_never_reopens_a_closed_session(self):
        with self.assertRaisesRegex(ValueError, "Avvia nuova sessione"):
            self.command("resume")
        self.add()
        self.command("start")
        self.command("pause")
        self.sync(ready=False)
        self.assertIn("Abilita questo laptop", self.master.device_view("a")["blocked_reason"])
        self.assertFalse(self.master.snapshot()["controls"]["resume"]["allowed"])
        with self.assertRaisesRegex(ValueError, "partecipanti pronti"):
            self.command("resume")
        self.assertEqual(self.master.session()["status"], "paused_manual")
        self.sync()
        self.assertTrue(self.master.snapshot()["controls"]["resume"]["allowed"])
        self.command("resume")
        self.assertEqual(self.master.session()["status"], "active")
        self.command("stop")
        with self.assertRaisesRegex(ValueError, "Avvia nuova sessione"):
            self.command("resume")

    def test_pause_and_restart_cannot_undo_definitive_stop(self):
        self.add()
        self.command("start")
        self.sync(request="open")
        self.command("stop")
        self.assertEqual(self.master.session()["status"], "draining")
        with self.assertRaises(ValueError):
            self.command("pause")
        self.master.close()
        self.master = Coordinator(self.path, self.clock)
        self.assertEqual(self.master.session()["status"], "draining")
        self.master.tick()
        self.assertEqual(self.master.session()["status"], "provisional")

    def test_master_shutdown_preserves_paused_session_for_explicit_resume(self):
        self.add()
        self.command("start")
        sid = self.master.session()["id"]
        self.command("shutdown")
        self.assertEqual(self.master.session()["status"], "paused_manual")
        self.master.close()
        self.master = Coordinator(self.path, self.clock)
        self.assertEqual(self.master.session()["id"], sid)
        self.assertFalse(self.master.snapshot()["controls"]["resume"]["allowed"])
        self.sync()
        self.command("resume")
        self.assertEqual(self.master.session()["status"], "active")
        self.assertEqual(self.master.session()["id"], sid)
        self.command("stop")
        self.command("shutdown")
        self.assertEqual(self.master.session()["status"], "closed")

    def test_unpair_drains_then_preserves_ledger_and_can_reassociate(self):
        token = self.add()
        self.command("start")
        grant = self.sync(request="open")["grant"]
        session = self.master.session()["id"]
        self.command("unpair", {"id": "a"})
        self.assertTrue(self.master.state["devices"]["a"]["unpair_requested"])
        self.assertIsNone(self.sync(request="blocked")["grant"])
        ack = self.master.state["devices"]["a"]["disarm"]
        e = event(1, "result", result(grant))
        reply = self.sync(events=[e], ready=False, disarm_ack=ack)
        self.assertFalse(reply["device"]["associated"])
        self.assertEqual(reply["device"]["balance"], 20080)
        self.assertFalse(self.master.authenticate("a", token))
        self.assertTrue(self.master.authenticate("a", token, allow_unpaired=True))
        self.assertIsNone(self.sync(events=[e], request="cannot-run")["grant"])
        with self.assertRaisesRegex(ValueError, "dissociato"):
            self.command("balance", {"id": "a", "balance": 1, "reason": "Rejected"})
        new_token = self.master.register("a", dict(DEFAULT_CONFIG), 1, sequence=1)
        self.assertTrue(self.master.authenticate("a", new_token))
        self.assertFalse(self.master.authenticate("a", token, allow_unpaired=True))
        self.assertEqual(self.master.device_view("a")["balance"], 20080)
        self.assertEqual(self.master.session(session)["net"], 80)
        self.assertEqual(len(list(self.master.archive_rows("rounds"))), 1)

    def test_offline_unresolved_round_blocks_unpair_and_new_master_accepts_sequence(self):
        self.add()
        self.command("start")
        self.sync(request="open")
        self.clock.advance(6)
        with self.assertRaisesRegex(ValueError, "Riconcilia partita"):
            self.command("unpair", {"id": "a"})
        self.master.register("other", dict(DEFAULT_CONFIG), 12345, sequence=42)
        self.assertEqual(self.master.state["devices"]["other"]["last_seq"], 42)

    def test_survivors_keep_baseline_and_late_result_stays_in_original_session(self):
        self.add("a")
        self.add("b")
        self.command("start")
        old_id = self.master.session()["id"]
        b = self.sync("b", "b1")["grant"]
        self.clock.advance(6)
        self.sync("a")
        self.assertEqual(self.master.session_view()["progress"], -100)
        self.assertEqual(self.master.session()["status"], "active")
        self.command("stop")
        self.assertEqual(self.master.session()["status"], "provisional")
        self.command("start")
        self.assertNotIn("b", self.master.session()["baseline"])
        a = self.sync("a", "a1")["grant"]
        self.sync("a", events=[event(1, "result", result(a))])
        self.sync("b", events=[event(1, "result", result(b))])
        self.assertEqual(self.master.session_view()["progress"], 80)
        self.assertEqual(self.master.session(old_id)["net"], 80)
        self.assertEqual(self.master.session(old_id)["status"], "closed")

    def test_capital_adjustment_and_configuration_conflict(self):
        self.add()
        self.command("start")
        self.sync(ready=False)
        self.command("balance", {"id": "a", "balance": 30000, "reason": "Saldo verificato"})
        self.assertEqual(self.master.session_view()["progress"], 0)
        self.command("device", {"id": "a", "revision": 1, "config": {**DEFAULT_CONFIG, "stake": 200}})
        with self.assertRaisesRegex(ValueError, "Conflitto"):
            self.command("device", {"id": "a", "revision": 1, "config": dict(DEFAULT_CONFIG)})
        self.assertIsNone(self.sync(request="pending", applied_revision=1)["grant"])
        self.assertIsNotNone(self.sync(request="pending", applied_revision=2)["grant"])

    def test_time_is_per_group_persisted_and_excludes_idle_pauses(self):
        for did in ("a", "b", "c", "d"):
            self.add(did)
        self.command("start")
        self.clock.advance(2)
        self.command("pause")
        self.assertAlmostEqual(self.master.state["usage"][self.master.day()], 2)
        self.clock.advance(100)
        self.master.tick()
        self.assertAlmostEqual(self.master.state["usage"][self.master.day()], 2)
        for did in ("a", "b", "c", "d"):
            self.sync(did)
        self.command("resume")
        self.command("settings", {**self.master.state["settings"], "budget": 3})
        self.clock.advance(1)
        self.master.tick()
        self.assertEqual(self.master.session()["reason"], "time")
        self.assertIsNone(self.sync(request="too_late")["grant"])

    def test_emergency_uncertain_round_manual_reconciliation(self):
        self.add()
        self.command("start")
        grant = self.sync(request="one")["grant"]
        self.sync(events=[event(1, "intent", {"round": grant["id"], "action": "play"}),
                          event(2, "uncertain", {"round": grant["id"], "error": "Crash"})], ready=False)
        self.assertIsNone(self.sync(request="other", ready=False)["grant"])
        self.command("reconcile", {"id": "a", "outcome": "loss", "balance": 19900, "reason": "Verificato"})
        self.assertEqual(self.master.session_view()["progress"], -100)
        self.assertIsNone(self.master.open_round("a"))

    def test_unknown_reconciliation_uses_verified_balance_without_inventing_loss(self):
        self.add(balance=2000000)
        self.assertFalse(self.master.device_view("a")["balance_is_estimate"])
        self.command("start")
        grant = self.sync(request="uncertain")['grant']
        self.assertTrue(self.master.device_view("a")["balance_is_estimate"])
        self.sync(events=[event(1, "uncertain", {"round": grant["id"], "error": "Esito non leggibile"})], ready=False)
        payload = {"id": "a", "outcome": "unknown", "balance": 1999910, "reason": "Saldo verificato sul gioco"}
        cid = str(uuid.uuid4())
        self.command("reconcile", payload, cid)
        self.command("reconcile", payload, cid)
        view = self.master.device_view("a")
        self.assertEqual(view["balance"], 1999910)
        self.assertEqual((view["net"], view["wins"], view["losses"]), (0, 0, 0))
        self.assertEqual(view["last_result"]["outcome"], "unknown")
        self.assertEqual(self.master.round(grant["id"])["outcome"], "unknown")
        self.assertEqual((self.master.session()["net"], self.master.session()["capital_flow"]), (0, -90))
        self.assertFalse(view["balance_is_estimate"])
        self.assertEqual(view["balance_verified_source"], "manual_adjustment")
        self.sync(events=[event(2, "result", result(grant, "loss"))], ready=False)
        self.assertEqual(self.master.device_view("a")["balance"], 1999910)
        self.assertEqual(self.master.device_view("a")["losses"], 0)

    def test_verified_reconciliation_preserves_each_outcomes_signed_profit(self):
        for outcome, expected in (("win", 80), ("loss", -100), ("cancel", 0)):
            with self.subTest(outcome=outcome):
                did = outcome
                self.add(did)
                self.command("start")
                grant = self.sync(did, request="one")["grant"]
                self.sync(did, ready=False)
                self.command("reconcile", {"id": did, "outcome": outcome, "balance": 1999910,
                                            "reason": "Credito effettivo verificato"})
                view = self.master.device_view(did)
                self.assertEqual(view["net"], expected)
                self.assertEqual(self.master.session()["net"], expected)
                self.assertEqual(view["last_result"]["outcome"], outcome)
                self.assertEqual(view["balance"], 1999910)
                self.assertEqual(view["wins"], int(outcome == "win"))
                self.assertEqual(view["losses"], int(outcome == "loss"))
                self.command("stop")

    def test_reset_backs_up_before_archiving_without_deleting_ledger_and_is_idempotent(self):
        token = self.add()
        self.command("settings", {**self.master.state["settings"], "target": 9999, "budget": 30000})
        self.command("start")
        old_session = self.master.session()["id"]
        grant = self.sync(request="one")["grant"]
        e = event(1, "result", result(grant))
        self.sync(events=[e], ready=False)
        self.clock.advance(3)
        cid = str(uuid.uuid4())
        snapshot = self.command("reset", {"confirmation": "RIPARTI"}, cid)
        path = Path(snapshot["reset_backup"])
        self.assertTrue(path.exists())
        backup = sqlite3.connect(path)
        try:
            self.assertEqual(backup.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            before = json.loads(backup.execute("SELECT payload FROM state WHERE id=1").fetchone()[0])
            self.assertEqual(before["current"], old_session)
            self.assertTrue(before["devices"]["a"]["associated"])
        finally:
            backup.close()
        self.assertIsNone(snapshot["session"])
        self.assertEqual((snapshot["usage"], snapshot["sessions_today"]), (0, 0))
        self.assertEqual(snapshot["settings"], {"target": 3000, "budget": 18000, "minimum": 1,
                                                 "automatic": False, "max_sessions": 0})
        old = self.master.device_view("a")
        self.assertTrue(old["reset_required"])
        self.assertFalse(old["associated"])
        self.assertEqual((old["balance"], old["net"]), (20080, 80))
        self.assertEqual(self.master.session(old_session)["reason"], "reset")
        self.assertEqual(self.master.session(old_session)["status"], "closed")
        self.assertEqual(len(list(self.master.archive_rows("rounds"))), 1)
        self.command("reset", {"confirmation": "RIPARTI"}, cid)
        self.assertEqual(list(path.parent.glob("*.sqlite3")), [path])
        self.assertFalse(self.master.authenticate("a", token))
        self.assertTrue(self.master.authenticate("a", token, allow_unpaired=True))
        with self.assertRaisesRegex(ValueError, "archiviata"):
            self.master.register("a", dict(DEFAULT_CONFIG), 1, sequence=1)
        receipt = self.sync(events=[e, event(2, "error", {"error": "Messaggio residuo"})], request="old-request")
        self.assertEqual(receipt["ack"], 2)
        self.assertIsNone(receipt["grant"])
        self.assertEqual(self.master.device_view("a")["error"], "")
        self.assertEqual(self.master.device_view("a")["balance"], 20080)
        self.add("fresh", balance=2000000)
        self.command("start")
        self.assertEqual(self.master.session()["net"], 0)
        self.assertEqual(self.master.session()["baseline"], {"fresh": 2000000})

    def test_reset_rejects_unresolved_rounds_busy_clients_and_missing_backup(self):
        self.add()
        payload = {"confirmation": "RIPARTI"}
        with self.assertRaisesRegex(ValueError, "RIPARTI"):
            self.command("reset")
        with self.assertRaisesRegex(ValueError, "disarmare"):
            self.command("reset", payload)
        self.command("start")
        grant = self.sync(request="unresolved")["grant"]
        self.sync(ready=False)
        with self.assertRaisesRegex(ValueError, "partite aperte"):
            self.command("reset", payload)
        self.sync(events=[event(1, "uncertain", {"round": grant["id"], "error": "Crash"})], ready=False)
        self.clock.advance(6)
        self.command("stop")
        self.assertEqual(self.master.session()["status"], "provisional")
        with self.assertRaisesRegex(ValueError, "partite aperte"):
            self.command("reset", payload)
        self.command("reconcile", {"id": "a", "outcome": "unknown", "balance": 20000, "reason": "Verificato"})
        before = deepcopy(self.master.state)
        with patch.object(self.master, "_reset_backup", side_effect=OSError("Disco pieno")):
            with self.assertRaisesRegex(ValueError, "reset annullato"):
                self.command("reset", payload)
        self.assertEqual(self.master.state, before)
        self.assertFalse((self.path.parent / "backups").exists())

    def test_reset_waits_for_client_disarm_and_emergency_receipts(self):
        self.add()
        self.command("disarm", {"id": "a"})
        payload = {"confirmation": "RIPARTI"}
        with self.assertRaisesRegex(ValueError, "disarmare"):
            self.command("reset", payload)
        self.sync(ready=False, disarm_ack=1)
        self.command("emergency")
        with self.assertRaisesRegex(ValueError, "disarmare"):
            self.command("reset", payload)
        self.sync(ready=False, disarm_ack=1, emergency_ack=1)
        self.assertIsNone(self.command("reset", payload)["session"])

    def test_balance_adjustment_waits_for_disarm_receipt(self):
        self.add(balance=2000000)
        self.command("disarm", {"id": "a"})
        payload = {"id": "a", "balance": 1999910, "reason": "Saldo verificato"}
        with self.assertRaisesRegex(ValueError, "Sospendere"):
            self.command("balance", payload)
        self.sync(ready=False, disarm_ack=1)
        self.command("balance", payload)
        self.assertEqual(self.master.device_view("a")["balance"], 1999910)

    def test_last_stake_is_operational_until_settlement_no_other_funds(self):
        self.add("a", balance=100)
        self.add("b")
        self.command("start")
        a = self.sync("a", "a1")["grant"]
        self.assertTrue(self.master.eligible("a"))
        self.sync("a", events=[event(1, "result", result(a, "loss"))])
        self.assertFalse(self.master.eligible("a"))
        self.assertIsNone(self.sync("a", "a2")["grant"])
        self.assertEqual(self.master.state["devices"]["b"]["balance"], 20000)

    def test_scale_and_automatic_sessions(self):
        for count in (1, 4, 20):
            with self.subTest(count=count):
                path = Path(self.temp.name) / f"scale{count}.db"
                m = Coordinator(path, self.clock)
                try:
                    for i in range(count):
                        m.register(str(i), dict(DEFAULT_CONFIG), 20000)
                        m.sync(str(i), {"ready": True, "busy": False, "applied_revision": 1, "events": []})
                    m.command("settings", {**m.state["settings"], "target": 1, "automatic": True, "max_sessions": 2}, str(uuid.uuid4()))
                    m.command("start", {}, str(uuid.uuid4()))
                    first = m.session()["id"]
                    for i in range(count):
                        grant = m.sync(str(i), {"ready": True, "busy": False, "applied_revision": 1, "events": [], "request": "one"})["grant"]
                        if grant:
                            m.sync(str(i), {"ready": True, "busy": False, "applied_revision": 1,
                                           "events": [event(1, "result", result(grant))]})
                    self.assertNotEqual(m.session()["id"], first)
                    self.assertEqual(m.state["counts"][m.day()], 2)
                finally:
                    m.close()


class ExecutorTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ClientStore(Path(self.temp.name) / "client.db")
        self.c = calibration()
        self.emergency, self.stop = threading.Event(), threading.Event()
        self.adapter = type("FakeScreen", (), {})()
        self.clicks = []
        self.adapter.size = lambda: (100, 100)
        self.adapter.click = self.clicks.append
        self.adapter.color = lambda tile: "blue"
        self.adapter.board = lambda: ["blue"] * 19 + ["red"] * 6
        self.engine = GameEngine(self.store, self.emergency, self.stop, adapter_factory=lambda c: self.adapter)
        self.grant = {"id": "round", "config": {**DEFAULT_CONFIG, "selection": "fixed"}, "status": "reserved"}
        self.store.update(round=deepcopy(self.grant))

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_win_two_cells_collect_and_complete_board(self):
        with patch("game_engine.pyautogui.click", side_effect=AssertionError("Real click")):
            self.engine.run_round(self.grant, self.c)
        self.assertEqual(self.clicks, [[70, 70], [10, 10], [20, 10], [70, 70]])
        body = self.store.events()[-1]["body"]
        self.assertEqual(body["outcome"], "win")
        self.assertTrue(body["board_complete"])

    def test_first_and_second_mine(self):
        for outcomes, expected in ((["red"], 2), (["blue", "red"], 3)):
            self.clicks.clear()
            values = iter(outcomes)
            self.adapter.color = lambda tile: next(values)
            self.engine.run_round(self.grant, self.c)
            self.assertEqual(len(self.clicks), expected)
            self.assertEqual(self.store.events()[-1]["body"]["outcome"], "loss")

    def test_unknown_color_stops_and_never_repeats_click(self):
        self.adapter.color = lambda tile: None
        self.engine.run_round(self.grant, self.c)
        self.assertEqual(len(self.clicks), 2)
        self.assertEqual(self.store.events()[-1]["kind"], "uncertain")
        self.assertTrue(self.emergency.is_set())

    def test_manual_stop_drains_but_emergency_interrupts(self):
        def click(point):
            self.clicks.append(point)
            if point == self.c["play"]:
                self.stop.set()
        self.adapter.click = click
        self.engine.run_round(self.grant, self.c)
        self.assertEqual(self.store.events()[-1]["kind"], "result")
        self.stop.clear()
        def emergency(point):
            if point == self.c["play"]:
                self.emergency.set()
        self.adapter.click = emergency
        self.engine.run_round(self.grant, self.c)
        self.assertEqual(self.store.events()[-1]["kind"], "uncertain")

    def test_stop_before_play_cancels_without_emergency(self):
        self.stop.set()
        self.engine.run_round(self.grant, self.c)
        self.assertFalse(self.clicks)
        self.assertEqual(self.store.events()[-1]["kind"], "cancel")
        self.assertFalse(self.emergency.is_set())

    def test_incomplete_board_retained_after_three_attempts(self):
        reads = []
        self.adapter.board = lambda: reads.append(1) or [None] * 25
        self.engine.run_round(self.grant, self.c)
        self.assertEqual(len(reads), 3)
        body = self.store.events()[-1]["body"]
        self.assertFalse(body["board_complete"])
        self.assertEqual(body["board"], [None] * 25)

    def test_bet_reset_and_target_no_tk_or_network(self):
        self.c["bet_values"] = [100, 200, 500]
        self.engine.apply_bet({**DEFAULT_CONFIG, "stake": 500}, 4, self.c)
        self.assertEqual(self.clicks, [[80, 70]] * 3 + [[90, 70]] * 2 + [[70, 80]] * 4 + [[80, 80]])
        self.assertEqual(self.store.snapshot()["applied_revision"], 4)

    def test_restart_intent_is_uncertain_reserved_is_cancelled(self):
        self.store.emit("intent", {"round": "round", "action": "play"})
        path = Path(self.temp.name) / "client.db"
        self.store.close()
        self.store = ClientStore(path)
        self.assertEqual(self.store.snapshot()["round"]["status"], "uncertain")
        self.assertEqual(self.store.events()[-1]["kind"], "uncertain")

    def test_failed_intent_write_prevents_every_physical_click(self):
        with patch.object(self.store, "emit", side_effect=OSError("Disco non disponibile")):
            with self.assertRaises(OSError):
                self.engine.run_round(self.grant, self.c)
        self.assertFalse(self.clicks)

    def test_reserved_round_is_cancelled_on_restart_without_click(self):
        self.store.close()
        self.store = ClientStore(Path(self.temp.name) / "client.db")
        self.assertEqual(self.store.events()[-1]["kind"], "cancel")
        self.assertEqual(self.store.snapshot()["round"]["status"], "pending")

    def test_geometry_and_duplicate_physical_cells_rejected(self):
        for c in (self.c, {**self.c, "tiles": {k: [1, 1] for k in self.c["tiles"]}}):
            with self.assertRaises(ValueError):
                validate_calibration(c, (90, 90) if c is self.c else (100, 100), DEFAULT_CONFIG)


if __name__ == "__main__":
    unittest.main()
