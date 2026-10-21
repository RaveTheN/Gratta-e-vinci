"""Real loopback resets with fake screen actions and temporary databases only."""
import base64
import json
from pathlib import Path
import queue
import sqlite3
import tempfile
import threading
import time
import unittest
import uuid

from tests.test_lan_network import eventually
from tests.test_lan_system import calibration
from mine_master import MasterService
from client_store import ClientStore
from game_engine import GameEngine
from laptop_client import LaptopClient, associate
from mine_protocol import DEFAULT_CONFIG


class ClientResetNetworkTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = MasterService(Path(self.temp.name), admin_port=0, device_port=0)
        await self.service.start()
        self.store = ClientStore(Path(self.temp.name) / "laptop.sqlite3")
        self.entered, self.release = threading.Event(), threading.Event()
        self.release.set()
        self.clicks = []
        entered, release, clicks = self.entered, self.release, self.clicks

        class FakeScreen:
            def __init__(self, c):
                self.play = c["play"]

            def size(self):
                return (100, 100)

            def click(self, point):
                clicks.append(point)
                if point == self.play and not entered.is_set():
                    entered.set()
                    if not release.wait(5):
                        raise AssertionError("Il test non ha sbloccato il click simulato")

            def color(self, tile):
                return "blue"

            def board(self):
                return ["blue"] * 19 + ["red"] * 6

        factory = lambda *args: GameEngine(*args, adapter_factory=FakeScreen)
        self.ui = queue.Queue()
        self.client = LaptopClient(self.store, self.ui, engine_factory=factory)
        self.profile = {**DEFAULT_CONFIG, "selection": "fixed"}
        self.old_id = self.store.snapshot()["id"]
        self.old_token = self.service.coordinator.register(self.old_id, self.profile, 2000000)
        self.lan = f"https://127.0.0.1:{self.service.device_port}"
        self.store.update(confirmed=True, balance=2000000, config=self.profile, calibration=calibration(),
                          connection={"url": self.lan, "fingerprint": self.service.fingerprint, "token": self.old_token})
        self.client.start()
        await eventually(lambda: self.service.coordinator.connected(self.old_id))

    async def asyncTearDown(self):
        import asyncio
        self.release.set()
        self.client.stop()
        await eventually(lambda: not self.client.worker.is_alive() and not self.client.network.is_alive())
        self.store.close()
        await self.service.close()
        await asyncio.sleep(0.25)
        self.temp.cleanup()

    def assert_reset_state_and_backup(self):
        state = self.store.snapshot()
        self.assertNotEqual(state["id"], self.old_id)
        self.assertEqual(state["balance"], 0)
        self.assertFalse(state["confirmed"])
        self.assertIsNone(state["connection"])
        self.assertIsNone(state["round"])
        self.assertEqual(state["sequence"], 0)
        self.assertEqual(state["commands"], [])
        self.assertFalse(self.store.events())
        self.assertEqual(state["calibration"], calibration())
        self.assertFalse(self.client.armed.is_set())
        archive = Path(state["last_reset_backup"])
        self.assertTrue(archive.exists())
        connection = sqlite3.connect(archive)
        try:
            self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            before = json.loads(connection.execute("SELECT payload FROM state WHERE id=1").fetchone()[0])
            self.assertEqual(before["id"], self.old_id)
            self.assertEqual(before["calibration"], calibration())
        finally:
            connection.close()
        return state

    async def test_global_reset_drains_pending_messages_then_requires_new_pair_and_balance(self):
        m = self.service.coordinator
        self.store.emit("clear_error", {})
        self.store.command("device", {"revision": 1, "config": {**self.profile, "name": "Prima del reset"}})
        snapshot = m.command("reset", {"confirmation": "RIPARTI"}, str(uuid.uuid4()))
        self.assertTrue(Path(snapshot["reset_backup"]).exists())
        self.client.wake()
        await eventually(lambda: self.store.snapshot()["id"] != self.old_id)
        state = self.assert_reset_state_and_backup()
        self.assertEqual(self.clicks, [])
        self.assertFalse(m.authenticate(self.old_id, self.old_token))
        self.assertTrue(m.device_view(self.old_id)["reset_required"])
        old_reply = m.sync(self.old_id, {"ready": True, "busy": False, "applied_revision": 1,
                                       "events": [], "request": "old-identity-cannot-play"})
        self.assertIsNone(old_reply["grant"])
        self.assertIsNone(m.session())
        self.service.pair_secret, self.service.pair_until = "new-code", time.monotonic() + 300
        code = base64.urlsafe_b64encode(json.dumps({"url": self.lan, "fingerprint": self.service.fingerprint,
                                                   "secret": "new-code"}).encode()).decode()
        with self.assertRaisesRegex(ValueError, "Confermare prima il credito"):
            await associate(self.store, code)
        with self.assertRaisesRegex(ValueError, "Associazione"):
            self.client.arm()
        self.store.update(balance=1999910, confirmed=True)
        await associate(self.store, code)
        self.client.wake()
        await eventually(lambda: m.connected(state["id"]))
        fresh = m.device_view(state["id"])
        self.assertEqual((fresh["balance"], fresh["net"], fresh["wins"], fresh["losses"]), (1999910, 0, 0, 0))
        self.assertFalse(self.client.armed.is_set())

    async def test_local_reset_waits_for_running_round_and_unpair_ack_before_rotating_identity(self):
        m = self.service.coordinator
        self.release.clear()
        self.client.arm()
        await eventually(lambda: m.eligible(self.old_id))
        m.command("settings", {**m.state["settings"], "target": 80}, str(uuid.uuid4()))
        m.command("start", {}, str(uuid.uuid4()))
        await eventually(self.entered.is_set)
        self.assertTrue(self.client.busy.is_set())
        self.assertIsNone(self.client.reset_local())
        self.assertTrue(self.store.snapshot()["reset_after_unpair"])
        await eventually(lambda: m.state["devices"][self.old_id].get("unpair_requested"))
        self.assertEqual(self.store.snapshot()["id"], self.old_id)
        self.assertTrue(m.state["devices"][self.old_id]["associated"])
        self.release.set()
        self.client.wake()
        await eventually(lambda: self.store.snapshot()["id"] != self.old_id)
        self.assert_reset_state_and_backup()
        old = m.device_view(self.old_id)
        self.assertFalse(old["associated"])
        self.assertEqual((old["balance"], old["net"], old["wins"]), (2000080, 80, 1))
        self.assertEqual(m.session()["net"], 80)
        self.assertEqual(m.session()["status"], "closed")
        self.assertEqual(len(list(m.archive_rows("rounds"))), 1)
        self.assertFalse(m.authenticate(self.old_id, self.old_token))
        self.assertIsNone(m.sync(self.old_id, {"ready": True, "busy": False, "applied_revision": 1,
            "events": [], "request": "retired-local-request"})["grant"])


if __name__ == "__main__":
    unittest.main()
