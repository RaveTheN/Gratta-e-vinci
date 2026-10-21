"""Real loopback TLS/WebSockets and laptop threads, with fake physical adapters."""
import asyncio
import base64
import json
from pathlib import Path
import queue
import secrets
import sys
import tempfile
import unittest
import uuid
import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Gratta e vinci Master"))
from mine_master import MasterService
from client_store import ClientStore
from laptop_client import LaptopClient, associate
from game_engine import GameEngine
from mine_protocol import DEFAULT_CONFIG
from tests.test_lan_system import calibration, event


async def eventually(predicate, seconds=6):
    deadline = asyncio.get_running_loop().time() + seconds
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.025)
    raise AssertionError("Condizione non raggiunta entro il timeout")


class NetworkTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = MasterService(Path(self.temp.name), admin_port=0, device_port=0)
        await self.service.start()
        self.http = aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True))
        self.admin = f"http://127.0.0.1:{self.service.admin_port}"
        self.lan = f"https://127.0.0.1:{self.service.device_port}"
        self.pin = aiohttp.Fingerprint(bytes.fromhex(self.service.fingerprint))

    async def asyncTearDown(self):
        await self.http.close()
        await self.service.close()
        await asyncio.sleep(0.25)
        self.temp.cleanup()

    async def login(self):
        async with self.http.post(self.admin + "/api/login", json={"token": self.service.bootstrap},
                                  headers={"Origin": self.admin}) as response:
            self.assertEqual(response.status, 200)

    async def test_admin_auth_host_origin_and_backup(self):
        async with self.http.get(self.admin + "/api/status") as response:
            self.assertEqual(response.status, 401)
        await self.login()
        async with self.http.get(self.admin + "/api/status", headers={"Host": "attacker.invalid"}) as response:
            self.assertEqual(response.status, 403)
        async with self.http.post(self.admin + "/api/command", json={}, headers={"Origin": "https://attacker.invalid"}) as response:
            self.assertEqual(response.status, 403)
        async with self.http.get(self.admin + "/api/backup") as response:
            self.assertEqual(response.status, 200)
            self.assertTrue((await response.read()).startswith(b"SQLite format 3"))
        async with self.http.get(self.admin + "/") as response:
            self.assertIn("default-src 'self'", response.headers["Content-Security-Policy"])
            self.assertIn("Mine / Master", await response.text())

    async def test_pairing_pin_retry_and_duplicate_connection(self):
        store = ClientStore(Path(self.temp.name) / "client.sqlite3")
        try:
            store.update(confirmed=True, balance=20000)
            self.service.pair_secret, self.service.pair_until = "one-use", __import__('time').monotonic() + 300
            code = base64.urlsafe_b64encode(json.dumps({"url": self.lan, "fingerprint": self.service.fingerprint,
                                                       "secret": "one-use"}).encode()).decode()
            await associate(store, code)
            state = store.snapshot()
            self.assertTrue(self.service.coordinator.authenticate(state["id"], state["connection"]["token"]))
            async with self.http.post(self.lan + "/pair", ssl=self.pin, json={"device": state["id"],
                            "token": state["connection"]["token"]}) as response:
                self.assertEqual(response.status, 200)
            headers = {"X-Device": state["id"], "Authorization": "Bearer " + state["connection"]["token"]}
            async with self.http.ws_connect(self.lan + "/ws", headers=headers, ssl=self.pin) as ws:
                with self.assertRaises(aiohttp.WSServerHandshakeError) as error:
                    await self.http.ws_connect(self.lan + "/ws", headers=headers, ssl=self.pin)
                self.assertEqual(error.exception.status, 409)
                await ws.send_json({"version": 1, "ready": False, "busy": False, "events": [], "applied_revision": 0})
                self.assertEqual((await ws.receive_json())["ack"], 0)
                await ws.send_json([])
                self.assertIn("error", await ws.receive_json())
                await ws.send_json({"version": 1, "ready": False, "busy": False, "events": [
                    {"id": "invalid", "seq": 1, "kind": "intent", "body": {"round": []}}], "applied_revision": 0})
                self.assertIn("error", await ws.receive_json())
                self.assertFalse(self.service.fatal_error)
                self.service.coordinator.command("unpair", {"id": state["id"]}, str(uuid.uuid4()))
                await ws.send_json({"version": 1, "ready": False, "busy": False, "events": [],
                                    "applied_revision": 0, "disarm_ack": 1})
                receipt = await ws.receive_json()
                self.assertFalse(receipt["device"]["associated"])
                self.assertIsNone(receipt["session"])
                self.service.coordinator.register(state["id"], dict(DEFAULT_CONFIG), 1)
                await ws.send_json({"version": 1, "ready": True, "busy": False, "events": [], "applied_revision": 1})
                self.assertEqual((await ws.receive()).type, aiohttp.WSMsgType.CLOSE)
            with self.assertRaises(aiohttp.ServerFingerprintMismatch):
                await self.http.get(self.lan + "/pair", ssl=aiohttp.Fingerprint(b"x" * 32))
        finally:
            store.close()

    async def test_shutdown_api_preserves_session_in_pause(self):
        m = self.service.coordinator
        m.register("fake", dict(DEFAULT_CONFIG), 20000)
        m.sync("fake", {"ready": True, "busy": False, "applied_revision": 1, "events": []})
        m.command("start", {}, str(uuid.uuid4()))
        sid = m.session()["id"]
        await self.login()
        async with self.http.post(self.admin + "/api/command", json={"id": str(uuid.uuid4()),
                "action": "shutdown", "payload": {}}, headers={"Origin": self.admin}) as response:
            self.assertEqual(response.status, 200)
            body = await response.json()
            self.assertTrue(body["ok"])
            self.assertEqual(body["session"]["status"], "paused_manual")
            self.assertEqual(body["session"]["id"], sid)
        self.assertTrue(self.service.shutdown_event.is_set())

    async def test_new_pairing_code_replaces_failed_attempt_without_changing_identity(self):
        store = ClientStore(Path(self.temp.name) / "client.sqlite3")
        try:
            store.update(confirmed=True, balance=20000)
            self.service.pair_secret, self.service.pair_until = "fresh", __import__('time').monotonic() + 300
            details = {"url": self.lan, "fingerprint": self.service.fingerprint, "secret": "expired"}
            encode = lambda body: base64.urlsafe_b64encode(json.dumps(body).encode()).decode()
            with self.assertRaisesRegex(ValueError, "Codice scaduto"):
                await associate(store, encode(details))
            pending = store.snapshot()["pair_pending"]
            with self.assertRaisesRegex(ValueError, "Codice.*non valido"):
                await associate(store, "not-a-pairing-code")
            self.assertEqual(store.snapshot()["pair_pending"], pending)
            with self.assertRaisesRegex(ValueError, "certificato"):
                await associate(store, encode({**details, "fingerprint": "78" * 32}))
            await associate(store, encode({**details, "secret": "fresh"}))
            state = store.snapshot()
            self.assertIsNone(state["pair_pending"])
            self.assertEqual(state["connection"]["token"], pending["token"])
            self.assertEqual(list(self.service.coordinator.state["devices"]), [state["id"]])
            self.assertEqual(state["balance"], 20000)
            with self.assertRaisesRegex(ValueError, "già associato"):
                await associate(store, encode(details))
        finally:
            store.close()

    async def test_pairing_lost_reply_recovers_saved_credential_with_empty_code(self):
        store = ClientStore(Path(self.temp.name) / "client.sqlite3")
        try:
            store.update(confirmed=True, balance=20000)
            pending = {"url": self.lan, "fingerprint": self.service.fingerprint, "secret": "used",
                       "token": secrets.token_urlsafe(32), "config": dict(DEFAULT_CONFIG), "balance": 20000}
            store.update(pair_pending=pending)
            self.service.coordinator.register(store.snapshot()["id"], pending["config"], pending["balance"], pending["token"])
            await associate(store, "")
            self.assertEqual(store.snapshot()["connection"]["token"], pending["token"])
            self.assertEqual(len(self.service.coordinator.state["devices"]), 1)
        finally:
            store.close()

    async def test_actual_laptop_threads_apply_bet_run_and_stop_without_real_clicks(self):
        store = ClientStore(Path(self.temp.name) / "client.sqlite3")
        clicks = []
        class FakeScreen:
            def __init__(self, c):
                pass
            def size(self):
                return (100, 100)
            def click(self, point):
                clicks.append(point)
            def color(self, tile):
                return "blue"
            def board(self):
                return ["blue"] * 19 + ["red"] * 6
        factory = lambda *args: GameEngine(*args, adapter_factory=FakeScreen)
        client = LaptopClient(store, queue.Queue(), engine_factory=factory)
        try:
            state = store.snapshot()
            token = self.service.coordinator.register(state["id"], dict(DEFAULT_CONFIG), 20000)
            store.update(confirmed=True, balance=20000, calibration=calibration(), connection={"url": self.lan,
                "fingerprint": self.service.fingerprint, "token": token})
            client.start()
            client.arm()
            await eventually(lambda: self.service.coordinator.eligible(state["id"]))
            before = len(clicks)
            self.service.coordinator.command("device", {"id": state["id"], "revision": 1,
                "config": {**DEFAULT_CONFIG, "name": "Solo nome modificato"}}, str(uuid.uuid4()))
            await eventually(lambda: self.service.coordinator.state["devices"][state["id"]]["applied_revision"] == 2)
            self.assertEqual(len(clicks), before)
            self.service.coordinator.command("settings", {**self.service.coordinator.state["settings"], "target": 80}, str(uuid.uuid4()))
            self.service.coordinator.command("start", {}, str(uuid.uuid4()))
            await eventually(lambda: self.service.coordinator.session()["status"] == "closed")
            self.assertEqual(self.service.coordinator.state["devices"][state["id"]]["balance"], 20080)
            self.assertEqual(len(clicks), len(calibration()["bet_values"]) + 9)
            await eventually(lambda: store.snapshot()["round"] is None)
            self.assertEqual(store.snapshot()["balance"], 20080)
            self.service.coordinator.command("unpair", {"id": state["id"]}, str(uuid.uuid4()))
            await eventually(lambda: store.snapshot()["connection"] is None)
            self.assertFalse(client.armed.is_set())
            self.assertEqual(store.snapshot()["id"], state["id"])
            self.assertEqual(store.snapshot()["calibration"], calibration())
            self.assertFalse(store.events())
            self.service.pair_secret, self.service.pair_until = "again", __import__('time').monotonic() + 300
            code = base64.urlsafe_b64encode(json.dumps({"url": self.lan, "fingerprint": self.service.fingerprint,
                                                       "secret": "again"}).encode()).decode()
            await associate(store, code)
            client.wake()
            await eventually(lambda: self.service.coordinator.connected(state["id"]))
            self.assertEqual(store.snapshot()["balance"], 20080)
            self.assertEqual(len(self.service.coordinator.state["devices"]), 1)
            self.assertFalse(client.armed.is_set())
            await eventually(lambda: store.snapshot().get("master_disarm", 0) ==
                             self.service.coordinator.state["devices"][state["id"]]["disarm"])
            client.arm()
            await eventually(lambda: self.service.coordinator.eligible(state["id"]))
        finally:
            client.stop()
            await eventually(lambda: not client.worker.is_alive() and not client.network.is_alive())
            store.close()

    async def test_unknown_balance_reconciliation_ack_and_admin_reset_receipt(self):
        m = self.service.coordinator
        token = m.register("fake", dict(DEFAULT_CONFIG), 2000000)
        m.sync("fake", {"ready": True, "busy": False, "applied_revision": 1, "events": []})
        m.command("start", {}, str(uuid.uuid4()))
        grant = m.sync("fake", {"ready": True, "busy": False, "applied_revision": 1,
                                "request": "uncertain", "events": []})["grant"]
        pending = event(1, "uncertain", {"round": grant["id"], "error": "Esito da verificare"})
        m.sync("fake", {"ready": False, "busy": False, "applied_revision": 1, "events": [pending]})
        headers = {"X-Device": "fake", "Authorization": "Bearer " + token}
        async with self.http.ws_connect(self.lan + "/ws", headers=headers, ssl=self.pin) as ws:
            command = {"id": str(uuid.uuid4()), "action": "reconcile", "payload": {
                "id": "fake", "balance": 1999910, "outcome": "unknown", "reason": "Saldo reale verificato"}}
            body = {"version": 1, "ready": False, "busy": False, "events": [pending],
                    "applied_revision": 1, "command": command}
            for attempt in range(2):
                await ws.send_json(body)
                reply = await ws.receive_json()
                self.assertEqual(reply["command_id"], command["id"])
                self.assertIsNone(reply["command_error"])
                self.assertEqual(reply["ack"], 1)
                self.assertEqual(reply["device"]["balance"], 1999910)
                self.assertEqual(reply["device"]["last_result"]["outcome"], "unknown")
                self.assertEqual(reply["device"]["net"], 0)
            await self.login()
            self.service.pair_secret = "invalidate-code"
            async with self.http.post(self.admin + "/api/command", json={"id": str(uuid.uuid4()),
                    "action": "reset", "payload": {"confirmation": "RIPARTI"}}, headers={"Origin": self.admin}) as response:
                self.assertEqual(response.status, 200)
                reset = await response.json()
                self.assertTrue(Path(reset["reset_backup"]).exists())
                self.assertIsNone(reset["session"])
            self.assertEqual(self.service.pair_secret, "")
            await ws.send_json({"version": 1, "ready": False, "busy": False, "events": [
                event(2, "error", {"error": "Residuo da archiviare"})], "applied_revision": 1,
                "request": "no-grant", "command": {"id": str(uuid.uuid4()), "action": "balance",
                "payload": {"id": "fake", "balance": 1234, "reason": "Comando precedente al reset"}}})
            receipt = await ws.receive_json()
            self.assertTrue(receipt["device"]["reset_required"])
            self.assertFalse(receipt["device"]["associated"])
            self.assertEqual(receipt["ack"], 2)
            self.assertEqual(receipt["device"]["balance"], 1999910)
            self.assertIn("dissociato", receipt["command_error"])
            self.assertIsNone(receipt["grant"])
            self.assertFalse(self.service.fatal_error)


if __name__ == "__main__":
    unittest.main()
