"""WebSocket link and single mouse worker. GUI communicates through queues."""
import asyncio
import base64
import json
import queue
import random
import threading
import time
import aiohttp
from game_engine import GameEngine, PreparationStopped
from mine_protocol import VERSION


async def associate(store, code):
    state = store.snapshot()
    if state["connection"]:
        raise ValueError("Laptop già associato: non sostituire identità o master con dati esistenti")
    if not state["confirmed"]:
        raise ValueError("Confermare prima il credito iniziale")
    pending = state.get("pair_pending")
    if not code.strip() and not pending:
        raise ValueError("Nel master scegliere Associa laptop e Genera codice monouso; incollarlo nel campo Associazione")
    from urllib.parse import urlsplit
    import binascii
    try:
        raw = code.strip()
        source = json.loads(base64.b64decode(raw, altchars=b"-_", validate=True).decode()) if raw else pending
        details = {key: source[key] for key in ("url", "fingerprint", "secret")}
        if not all(isinstance(value, str) and value for value in details.values()):
            raise ValueError()
        url = urlsplit(details["url"])
        if (url.scheme != "https" or not url.hostname or url.username or url.password or
                url.path not in ("", "/") or url.query or url.fragment):
            raise ValueError()
        url.port
        pin = aiohttp.Fingerprint(bytes.fromhex(details["fingerprint"]))
        details["url"] = details["url"].rstrip("/")
    except (ValueError, TypeError, KeyError, binascii.Error) as exc:
        raise ValueError("Codice del master non valido: copiare l'intero codice generato da Associa laptop") from exc
    import secrets
    if pending:
        details.update({key: pending[key] for key in ("token", "config", "balance")})
    else:
        details.update(token=secrets.token_urlsafe(32), config=state["config"], balance=state["balance"])
    store.update(pair_pending=details)
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as client:
            async with client.post(details["url"] + "/pair", ssl=pin, allow_redirects=False, json={"secret": details["secret"],
                                      "device": state["id"], "config": details["config"], "balance": details["balance"],
                                      "token": details["token"], "sequence": state["sequence"]}) as response:
                if response.status == 403:
                    raise ValueError("Codice scaduto o già usato: generare un nuovo codice nel master e incollarlo qui")
                try:
                    body = await response.json()
                except (aiohttp.ContentTypeError, ValueError) as exc:
                    raise ValueError(f"Risposta associazione non valida (HTTP {response.status})") from exc
                if not isinstance(body, dict):
                    raise ValueError("Risposta associazione non valida")
                if response.status != 200:
                    raise ValueError(body.get("error", f"Associazione rifiutata (HTTP {response.status})"))
                if body.get("token") != details["token"] or body.get("version") != VERSION:
                    raise ValueError("Risposta associazione non valida")
    except aiohttp.ServerFingerprintMismatch as exc:
        raise ValueError("Il certificato non corrisponde al codice: generare un nuovo codice dal master attuale") from exc
    except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as exc:
        raise ValueError("Master non raggiungibile: verificare che sia aperto, sulla stessa rete e con la porta consentita dal firewall") from exc
    store.update(connection={"url": details["url"], "fingerprint": details["fingerprint"], "token": body["token"]},
                 pair_pending=None, emergency=0, master_disarm=0)


class LaptopClient:
    def __init__(self, store, ui_queue, engine_factory=GameEngine):
        self.store, self.ui = store, ui_queue
        self.armed, self.busy = threading.Event(), threading.Event()
        self.emergency, self.ordinary_stop, self.shutdown = threading.Event(), threading.Event(), threading.Event()
        self.setup_stop = threading.Event()
        self.setup_stop.set()
        self.reconnect = threading.Event()
        self.ordinary_stop.set()
        self.jobs = queue.Queue()
        self.engine = engine_factory(store, self.emergency, self.ordinary_stop, self.wake)
        self.engine.setup_stop = self.setup_stop
        self.next_round_at = 0.0
        self.loop, self.wakeup = None, None
        self.scheduled = set()
        self.worker = threading.Thread(target=self._worker, name="mouse-worker", daemon=False)
        self.network = threading.Thread(target=self._network, name="master-link", daemon=False)

    def start(self):
        self.worker.start()
        self.network.start()

    def wake(self):
        if self.loop and self.wakeup and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.wakeup.set)

    def arm(self):
        if self.armed.is_set() and not self.emergency.is_set():
            return
        if self.busy.is_set() or not self.jobs.empty():
            raise ValueError("Attendere la fine delle operazioni prima di abilitare nuovamente il laptop")
        state = self.store.snapshot()
        if any(c["action"] in ("balance", "reconcile") for c in state["commands"]):
            raise ValueError("Attendere la conferma del master sulla rettifica del saldo prima di abilitare")
        if state.get("unpair_requested") or state.get("reset_after_unpair"):
            raise ValueError("Attendere il completamento della dissociazione")
        if state["round"] or state.get("master_round"):
            raise ValueError("Riconciliare prima la partita aperta")
        if not state["connection"]:
            raise ValueError("Prima completare Associazione: nel master generare un codice, incollarlo nel client e premere Associa codice del master")
        self.store.update(error="", applied_revision=0, applied_stake=None)
        self.store.update(confirmed_profile={key: state["config"][key] for key in ("mines", "multiplier")})
        self.store.emit("clear_error", {})
        self.engine.difficulty_prepared = False
        self.emergency.clear()
        self.setup_stop.clear()
        self.armed.set()
        self.wake()

    def disarm(self, emergency=False):
        self.armed.clear()
        self.setup_stop.set()
        self.ordinary_stop.set()
        if emergency:
            self.emergency.set()
        self.wake()

    def reset_local(self):
        self.disarm()
        if self.store.request_reset():
            self.wake()
            return None
        if self.busy.is_set() or not self.jobs.empty() or self.scheduled:
            raise ValueError("Attendere il completamento delle operazioni prima di ripartire")
        return self.store.reset()

    def _worker(self):
        while True:
            job = self.jobs.get()
            if job is None:
                return
            self.busy.set()
            kind, payload, calibration = job
            try:
                if kind == "bet":
                    if self.armed.is_set() and not self.emergency.is_set():
                        self.engine.apply_bet(payload["config"], payload["revision"], calibration)
                else:
                    self.engine.run_round(payload, calibration)
            except PreparationStopped:
                self.ui.put(("status", "Impostazione interrotta dalla pausa; verrà ripetuta prima della ripresa"))
            except Exception as exc:
                self.armed.clear()
                self.emergency.set()
                try:
                    self.store.emit("error", {"error": str(exc)})
                except Exception:
                    pass
                self.ui.put(("error", str(exc)))
            finally:
                if kind == "round":
                    self.next_round_at = time.monotonic() + calibration["delays"]["between"]
                    self.scheduled.discard(payload["id"])
                self.busy.clear()
                self.ui.put(("status", ""))
                self.wake()

    def _network(self):
        try:
            asyncio.run(self._network_lifetime())
        except Exception as exc:
            self.armed.clear()
            self.ordinary_stop.set()
            self.ui.put(("error", f"Collegamento arrestato: {exc}"))

    async def _network_lifetime(self):
        try:
            await self._connect()
        finally:
            await asyncio.sleep(0.25)

    async def _connect(self):
        self.loop, self.wakeup = asyncio.get_running_loop(), asyncio.Event()
        retry = 1
        while not self.shutdown.is_set():
            self.reconnect.clear()
            state = self.store.snapshot()
            if not state["connection"]:
                await self._wait(1)
                self.wakeup.clear()
                continue
            c = state["connection"]
            try:
                pin = aiohttp.Fingerprint(bytes.fromhex(c["fingerprint"]))
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                    async with session.ws_connect(c["url"] + "/ws", ssl=pin,
                            headers={"X-Device": state["id"], "Authorization": "Bearer " + c["token"]},
                            heartbeat=2, max_msg_size=262144) as ws:
                        retry = 1
                        while not self.shutdown.is_set() and not self.reconnect.is_set():
                            self.wakeup.clear()
                            state = self.store.snapshot()
                            ready = self.armed.is_set() and not self.emergency.is_set() and not state["error"]
                            if (ready and not self.busy.is_set() and not state["round"] and
                                    state["applied_revision"] == state["revision"] and time.monotonic() >= self.next_round_at):
                                self.store.new_request()
                                state = self.store.snapshot()
                            await ws.send_json({"version": VERSION, "events": self.store.events(), "ready": ready,
                                "busy": self.busy.is_set(), "applied_revision": state["applied_revision"],
                                "emergency_ack": state["emergency"],
                                "disarm_ack": state.get("master_disarm", 0),
                                "request": state["request"], "command": state["commands"][0] if state["commands"] else None})
                            response = await asyncio.wait_for(ws.receive_json(), 4)
                            if response.get("error"):
                                self.armed.clear()
                                self.store.update(error=response["error"])
                                self.ui.put(("error", response["error"]))
                                raise RuntimeError(response["error"])
                            self.store.reply(response)
                            self.ui.put(("reply", response))
                            if response.get("command_error"):
                                self.disarm()
                                self.ui.put(("error", response["command_error"]))
                            d, group = response["device"], response["session"]
                            if not d.get("associated", True):
                                self.disarm()
                                if not self.busy.is_set() and self.jobs.empty():
                                    resetting = d.get("reset_required") or self.store.snapshot().get("reset_after_unpair")
                                    if resetting:
                                        current = self.store.snapshot()
                                        if (not current["round"] and not current.get("master_round") and
                                                not current["commands"] and not self.store.events()):
                                            archive = self.store.reset(master_confirmed=True)
                                            self.ui.put(("reset", archive))
                                            break
                                    elif self.store.finish_unpair():
                                        self.ui.put(("unpaired", None))
                                        break
                                await self._wait(1)
                                continue
                            if d.get("unpair_requested"):
                                self.disarm()
                                ready = False
                            if d.get("disarm", 0) > self.store.snapshot().get("master_disarm", 0):
                                self.store.update(master_disarm=d["disarm"])
                                self.disarm()
                            confirmed = state.get("confirmed_profile")
                            if confirmed and any(d["config"][key] != confirmed[key] for key in confirmed):
                                self.disarm()
                                self.ui.put(("error", "Profilo mine/pagamento cambiato: verificare il gioco e riarmare localmente"))
                            if d["emergency"] > self.store.snapshot()["emergency"]:
                                self.store.update(emergency=d["emergency"])
                                self.disarm(emergency=True)
                            allowed = (group and group["status"] == "active" and state["id"] in group["baseline"]
                                       and d["enabled"] and self.armed.is_set())
                            if allowed:
                                self.ordinary_stop.clear()
                            else:
                                self.ordinary_stop.set()
                            state = self.store.snapshot()
                            item = state["round"]
                            if item and item["status"] == "reserved" and item["id"] not in self.scheduled:
                                self.scheduled.add(item["id"])
                                self.jobs.put(("round", item, state["calibration"]))
                            elif (ready and not item and not self.busy.is_set() and self.jobs.empty()
                                  and state["applied_revision"] != state["revision"]):
                                if state.get("applied_stake") == state["config"]["stake"]:
                                    self.store.update(applied_revision=state["revision"])
                                    self.wake()
                                else:
                                    self.jobs.put(("bet", {"config": state["config"], "revision": state["revision"]}, state["calibration"]))
                            remaining = self.next_round_at - time.monotonic()
                            await self._wait(min(1, remaining) if ready and remaining > 0 else 1)
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ValueError, RuntimeError) as exc:
                self.ordinary_stop.set()
                self.ui.put(("connection", f"Disconnesso: {exc}"))
                self.wakeup.clear()
                await self._wait(retry + random.random() * 0.2)
                retry = min(retry * 2, 10)

    async def _wait(self, delay):
        try:
            await asyncio.wait_for(self.wakeup.wait(), delay)
        except asyncio.TimeoutError:
            pass

    def stop(self):
        self.disarm()
        self.shutdown.set()
        self.wake()
        self.jobs.put(None)
