"""Local pause keys and inter-round pacing; temporary TLS and fake screen only."""
import asyncio
from pathlib import Path
import queue
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch

from pynput import keyboard

from tests.test_lan_network import eventually
from tests.test_lan_system import calibration
from mine_master import MasterService
from client_store import ClientStore
from game_engine import GameEngine
from gratta_e_vinci_gui import GrattaEVinciGUI
from laptop_client import LaptopClient
from mine_protocol import DEFAULT_CONFIG


class PauseKeyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = ClientStore(Path(self.temp.name) / "laptop.sqlite3")
        self.addCleanup(self.store.close)
        self.store.update(connection={"url": "https://unused"}, confirmed=True, balance=20000)
        self.gui = GrattaEVinciGUI.__new__(GrattaEVinciGUI)
        self.gui.ui_queue = queue.Queue()
        self.gui.client = LaptopClient(self.store, self.gui.ui_queue)
        self.gui.client.arm()

    def test_lower_and_upper_p_pause_without_touching_tk_or_emergency(self):
        for char in ("p", "P"):
            with self.subTest(char=char):
                self.gui.client.arm()
                key = keyboard.KeyCode.from_char(char)
                self.gui._key(key)
                self.assertFalse(self.gui.client.armed.is_set())
                self.assertTrue(self.gui.client.ordinary_stop.is_set())
                self.assertTrue(self.gui.client.setup_stop.is_set())
                self.assertFalse(self.gui.client.emergency.is_set())
                self.assertEqual(self.gui.ui_queue.get_nowait(), ("paused", None))
                self.assertTrue(self.gui.ui_queue.empty())
                self.gui._key_release(key)

    def test_held_p_emits_one_pause_and_p_never_resumes(self):
        self.gui.client.busy.set()
        with patch.object(self.gui.client, "disarm", wraps=self.gui.client.disarm) as disarm:
            for char in ("p", "p", "P", "p"):
                self.gui._key(keyboard.KeyCode.from_char(char))
            disarm.assert_called_once_with()
        self.assertEqual(self.gui.ui_queue.get_nowait(), ("paused", None))
        self.assertTrue(self.gui.ui_queue.empty())
        self.gui.client.busy.clear()
        self.gui._key_release(keyboard.KeyCode.from_char("P"))
        self.gui._key(keyboard.KeyCode.from_char("p"))
        self.assertFalse(self.gui.client.armed.is_set())
        self.assertFalse(self.gui.client.emergency.is_set())
        self.assertTrue(self.gui.ui_queue.empty())

    def test_escape_requests_emergency(self):
        self.gui._key(keyboard.Key.esc)
        self.assertFalse(self.gui.client.armed.is_set())
        self.assertTrue(self.gui.client.emergency.is_set())
        self.assertTrue(self.gui.client.ordinary_stop.is_set())
        kind, message = self.gui.ui_queue.get_nowait()
        self.assertEqual(kind, "error")
        self.assertIn("Emergenza", message)


class PauseAndBetweenNetworkTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = MasterService(Path(self.temp.name), admin_port=0, device_port=0)
        await self.service.start()
        self.store = ClientStore(Path(self.temp.name) / "laptop.sqlite3")
        self.cell_entered, self.release_cell = threading.Event(), threading.Event()
        self.release_cell.set()
        self.starts, self.boards, self.clicks = [], [], []
        entered, release = self.cell_entered, self.release_cell
        starts, boards, clicks = self.starts, self.boards, self.clicks

        class FakeScreen:
            def __init__(self, c):
                self.play, self.first = c["play"], c["tiles"]["1"]
                self.play_clicks = 0

            def size(self):
                return (100, 100)

            def click(self, point):
                clicks.append(list(point))
                if point == self.play:
                    if self.play_clicks % 2 == 0:
                        starts.append(time.monotonic())
                    self.play_clicks += 1
                if point == self.first and not entered.is_set():
                    entered.set()
                    if not release.wait(5):
                        raise AssertionError("Il test non ha sbloccato la cella simulata")

            def color(self, tile):
                return "blue"

            def board(self):
                boards.append(time.monotonic())
                return ["blue"] * 19 + ["red"] * 6

        self.ui = queue.Queue()
        self.client = LaptopClient(self.store, self.ui,
            engine_factory=lambda *args: GameEngine(*args, adapter_factory=FakeScreen))
        self.gui = GrattaEVinciGUI.__new__(GrattaEVinciGUI)
        self.gui.client, self.gui.ui_queue = self.client, self.ui
        self.did = self.store.snapshot()["id"]
        self.profile = {**DEFAULT_CONFIG, "selection": "fixed"}
        token = self.service.coordinator.register(self.did, self.profile, 20000)
        self.store.update(confirmed=True, balance=20000, config=self.profile, calibration=calibration(),
            connection={"url": f"https://127.0.0.1:{self.service.device_port}",
                        "fingerprint": self.service.fingerprint, "token": token})
        self.client.start()
        await eventually(lambda: self.service.coordinator.connected(self.did))

    async def asyncTearDown(self):
        self.release_cell.set()
        self.client.stop()
        await eventually(lambda: not self.client.worker.is_alive() and not self.client.network.is_alive())
        self.store.close()
        await self.service.close()
        await asyncio.sleep(0.25)
        self.temp.cleanup()

    async def start_session(self, target):
        m = self.service.coordinator
        self.client.arm()
        await eventually(lambda: m.eligible(self.did))
        m.command("settings", {**m.state["settings"], "target": target}, str(uuid.uuid4()))
        m.command("start", {}, str(uuid.uuid4()))
        self.client.wake()

    async def test_between_delay_prevents_early_grant_despite_frequent_wakes(self):
        c = calibration()
        c["delays"]["between"] = 0.3
        self.store.update(calibration=c)
        await self.start_session(target=160)
        deadline = time.monotonic() + 6
        while len(self.starts) < 2 and time.monotonic() < deadline:
            self.client.wake()
            await asyncio.sleep(0.01)
        self.assertEqual(len(self.starts), 2)
        self.assertGreaterEqual(self.starts[1] - self.boards[0], 0.3)
        m = self.service.coordinator
        await eventually(lambda: m.session()["status"] == "closed")
        await eventually(lambda: self.store.snapshot()["round"] is None)
        rounds = list(m.archive_rows("rounds"))
        self.assertEqual(len(rounds), 2)
        self.assertEqual(m.device_view(self.did)["balance"], 20160)
        self.assertFalse(self.client.emergency.is_set())
        self.assertFalse(self.service.fatal_error)

        self.assertEqual(self.clicks.count(c["difficulty_lower"]), 4)
        self.assertEqual(self.clicks.count(c["difficulty_raise"]), 1)

    async def test_difficulty_is_prepared_once_until_manual_rearm(self):
        c = calibration()
        m = self.service.coordinator
        await self.start_session(target=80)
        await eventually(lambda: m.session()["status"] == "closed" and
                         self.store.snapshot()["round"] is None and not self.client.busy.is_set())
        self.assertEqual(self.clicks.count(c["difficulty_lower"]), 4)
        self.assertEqual(self.clicks.count(c["difficulty_raise"]), 1)
        profile = {**self.profile, "stake": 200}
        m.command("device", {"id": self.did, "revision": 1, "config": profile}, str(uuid.uuid4()))
        self.client.wake()
        await eventually(lambda: self.store.snapshot()["applied_revision"] == 2 and not self.client.busy.is_set())
        self.assertEqual(self.clicks.count(c["difficulty_lower"]), 4)
        await self.start_session(target=80)
        await eventually(lambda: len(self.starts) == 2 and m.session()["status"] == "closed" and
                         self.store.snapshot()["round"] is None and not self.client.busy.is_set())
        self.assertEqual(self.clicks.count(c["difficulty_lower"]), 4)
        self.assertEqual(self.clicks.count(c["difficulty_raise"]), 1)
        self.client.disarm()
        self.client.arm()
        await eventually(lambda: self.store.snapshot()["applied_revision"] == 2 and
                         m.eligible(self.did) and not self.client.busy.is_set())
        self.assertEqual(self.clicks.count(c["difficulty_lower"]), 8)
        self.assertEqual(self.clicks.count(c["difficulty_raise"]), 2)
        self.assertEqual(len(self.starts), 2)

    async def test_p_finishes_open_win_then_stays_paused_through_reconnect(self):
        self.release_cell.clear()
        await self.start_session(target=3000)
        await eventually(self.cell_entered.is_set)
        self.assertTrue(self.client.busy.is_set())
        self.gui._key(keyboard.KeyCode.from_char("P"))
        self.assertFalse(self.client.armed.is_set())
        self.assertFalse(self.client.emergency.is_set())
        self.release_cell.set()
        m = self.service.coordinator
        await eventually(lambda: m.device_view(self.did)["wins"] == 1)
        await eventually(lambda: self.store.snapshot()["round"] is None and not self.client.busy.is_set())
        self.assertEqual(m.device_view(self.did)["balance"], 20080)
        self.assertEqual(m.session()["net"], 80)
        self.assertEqual(m.device_view(self.did)["losses"], 0)
        self.assertEqual(len(self.starts), 1)
        self.assertEqual(self.clicks.count(calibration()["play"]), 2)
        self.assertFalse(self.client.emergency.is_set())

        previous = self.service.peers[self.did]
        self.client.reconnect.set()
        self.client.wake()
        await eventually(lambda: self.did in self.service.peers and self.service.peers[self.did] is not previous)
        await eventually(lambda: m.connected(self.did) and not m.device_view(self.did)["ready"])
        self.gui._key_release(keyboard.KeyCode.from_char("P"))
        self.gui._key(keyboard.KeyCode.from_char("p"))
        for _ in range(20):
            self.client.wake()
            await asyncio.sleep(0.025)
        self.assertFalse(self.client.armed.is_set())
        self.assertFalse(self.client.emergency.is_set())
        self.assertEqual(len(list(m.archive_rows("rounds"))), 1)
        self.assertEqual(len(self.starts), 1)
        self.assertEqual(m.session()["status"], "paused_minimum")
        self.assertFalse(self.store.snapshot()["error"])
        self.assertFalse(self.service.fatal_error)


if __name__ == "__main__":
    unittest.main()
