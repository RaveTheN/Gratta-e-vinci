"""SQLite identity, configuration, unfinished round and durable client outbox."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
import time
import uuid
from game_config import BET_VALUES, TARGET_BLUE, TARGET_RED
from mine_protocol import DEFAULT_CONFIG, database, dumps, integer, money


def default_calibration():
    return {"tiles": {}, "play": [0, 0], "raise": [0, 0], "lower": [0, 0],
            "difficulty_lower": [0, 0], "difficulty_raise": [0, 0], "screen": [],
            "blue": dict(TARGET_BLUE), "red": dict(TARGET_RED), "tolerance": 50,
            "delays": {"play": 1.0, "after_play": 0.5, "tile": 1.0, "after_tile": 0.5,
                       "retry": 1.0, "reveal": 1.0, "bet": 0.2, "reset": 0.05, "between": 0.0,
                       "collect": 1.0, "second_tile": 1.0, "after_second_tile": 0.5,
                       "difficulty_lower": 0.05, "difficulty_raise": 0.2, "after_difficulty": 0.5,
                       "after_click": 0.1, "board_retry": 1.0},
            "bet_values": [money(v) for v in BET_VALUES], "steps": [{"action": "reset"}, {"action": "target"}]}


def initial_state():
    return {"id": str(uuid.uuid4()), "config": dict(DEFAULT_CONFIG), "balance": 0, "confirmed": False,
            "revision": 0, "applied_revision": 0, "sequence": 0, "connection": None,
            "calibration": default_calibration(), "round": None, "request": None, "error": "",
            "commands": [], "emergency": 0, "bet_in_progress": False}


def validate_calibration(c, screen, profile):
    if c["screen"] != list(screen):
        raise ValueError("Geometria schermo cambiata o non confermata: salvare la calibrazione")
    if set(c["tiles"]) != {str(i) for i in range(1, 26)}:
        raise ValueError("Calibrare tutte le 25 celle")
    for key in ("difficulty_lower", "difficulty_raise"):
        if c.get(key) in (None, [0, 0]):
            raise ValueError("Calibrare entrambi i pulsanti difficoltà per impostare Medium prima di Play")
    positions = list(c["tiles"].values()) + [c[k] for k in ("play", "raise", "lower", "difficulty_lower", "difficulty_raise")]
    for point in positions:
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("Coordinate non valide")
        for value in point:
            integer(value, "Coordinata", 0, 100000)
        if point[0] >= screen[0] or point[1] >= screen[1]:
            raise ValueError("Coordinate fuori dallo schermo")
    if len({tuple(p) for p in positions}) != 30:
        raise ValueError("Le coordinate di celle e pulsanti devono essere distinte")
    values = c["bet_values"]
    if not isinstance(values, list) or not values or len(values) > 100 or values != sorted(set(values)):
        raise ValueError("Valori puntata: lista crescente senza duplicati (massimo 100)")
    for value in values:
        integer(value, "Puntata disponibile", 1)
    if profile["stake"] not in values:
        raise ValueError("Puntata richiesta assente dalla lista dei pulsanti del gioco")
    integer(c["tolerance"], "Tolleranza", 0, 255)
    for target in (c["blue"], c["red"]):
        if set(target) != {"r", "g", "b"}:
            raise ValueError("Colore RGB non valido")
        for value in target.values():
            integer(value, "Canale RGB", 0, 255)
    if set(c["delays"]) != set(default_calibration()["delays"]):
        raise ValueError("Tempi incompleti o sconosciuti")
    for value in c["delays"].values():
        if type(value) not in (int, float) or not 0 <= value <= 60:
            raise ValueError("Pause comprese tra zero e sessanta secondi")
    steps = c["steps"]
    if not isinstance(steps, list) or not 2 <= len(steps) <= 100:
        raise ValueError("Sequenza cambio puntata non valida")
    actions = [s.get("action") for s in steps]
    if actions.count("reset") != 1 or actions.count("target") != 1 or actions.index("reset") > actions.index("target"):
        raise ValueError("Servono un reset seguito da una sola applicazione della puntata")
    for step in steps:
        if step["action"] == "wait":
            if type(step.get("seconds")) not in (int, float) or not 0 <= step["seconds"] <= 60:
                raise ValueError("Attesa non valida")
        elif step["action"] == "click":
            point = step.get("point")
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError("Punto click non valido")
            for value in point:
                integer(value, "Coordinata", 0, 100000)
            if not (point[0] < screen[0] and point[1] < screen[1]):
                raise ValueError("Click fuori dallo schermo")
        elif step["action"] not in ("reset", "target"):
            raise ValueError("Azione della sequenza non valida")


class ClientStore:
    def __init__(self, path):
        self.path = Path(path).resolve()
        self.db, self.lock = database(path), threading.RLock()
        self.db.executescript("""CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS outbox(seq INTEGER PRIMARY KEY, payload TEXT NOT NULL);""")
        row = self.db.execute("SELECT payload FROM state WHERE id=1").fetchone()
        self.state = json.loads(row[0]) if row else initial_state()
        with self.transaction():
            c = self.state["calibration"]
            for key in ("difficulty_lower", "difficulty_raise"):
                c.setdefault(key, [0, 0])
            delays = c["delays"]
            for new, old in (("collect", "play"), ("second_tile", "tile"), ("after_second_tile", "after_tile"),
                             ("board_retry", "reveal")):
                delays.setdefault(new, delays[old])
            for key in ("difficulty_lower", "difficulty_raise", "after_difficulty", "after_click"):
                delays.setdefault(key, default_calibration()["delays"][key])
            if self.state["bet_in_progress"]:
                self.state.update(error="Cambio puntata interrotto: verificare e riarmare", bet_in_progress=False)
            self.state["applied_revision"] = 0
            self.state["applied_stake"] = None
            item = self.state["round"]
            if item and item["status"] == "reserved":
                self._emit("cancel", {"round": item["id"], "reason": "Riavvio prima di Play"})
                item["status"] = "pending"
            elif item and item["status"] not in ("pending", "uncertain"):
                self._emit("uncertain", {"round": item["id"], "error": "Applicazione interrotta durante i click"})
                item["status"] = "uncertain"
                self.state["error"] = "Partita interrotta: riconciliare dal master"

    @contextmanager
    def transaction(self):
        with self.lock:
            before = deepcopy(self.state)
            try:
                with self.db:
                    yield
                    self.db.execute("INSERT OR REPLACE INTO state VALUES(1,?)", (dumps(self.state),))
            except BaseException:
                self.state = before
                raise

    def snapshot(self):
        with self.lock:
            return deepcopy(self.state)

    def update(self, **values):
        with self.transaction():
            self.state.update(deepcopy(values))

    def _emit(self, kind, body):
        self.state["sequence"] += 1
        event = {"id": str(uuid.uuid4()), "seq": self.state["sequence"], "kind": kind, "body": body, "time": time.time()}
        self.db.execute("INSERT INTO outbox VALUES(?,?)", (event["seq"], dumps(event)))
        return event

    def emit(self, kind, body):
        with self.transaction():
            event = self._emit(kind, body)
            if kind in ("intent", "result", "uncertain", "cancel") and self.state["round"]:
                if kind != "intent" or body.get("action") not in ("difficulty_lower", "difficulty_raise"):
                    self.state["round"]["status"] = "started" if kind == "intent" else "uncertain" if kind == "uncertain" else "pending"
            if kind in ("uncertain", "error"):
                self.state["error"] = body.get("error", "Errore")
            return event

    def events(self):
        with self.lock:
            return [json.loads(r[0]) for r in self.db.execute("SELECT payload FROM outbox ORDER BY seq LIMIT 200")]

    def command(self, action, payload):
        with self.transaction():
            item = {"id": str(uuid.uuid4()), "action": action, "payload": {"id": self.state["id"], **payload}}
            self.state["commands"].append(item)
        return item

    def new_request(self):
        with self.transaction():
            if not self.state["request"]:
                self.state["request"] = str(uuid.uuid4())
            return self.state["request"]

    def request_reset(self):
        with self.transaction():
            opened = self.state.get("master_round") or self.state["round"]
            if opened and opened["status"] == "uncertain":
                raise ValueError("Verificare il saldo e riconciliare la partita incerta prima di ripartire")
            if not self.state["connection"]:
                return False
            self.state.update(reset_after_unpair=True, unpair_requested=True)
            if not any(c["action"] == "unpair" for c in self.state["commands"]):
                self.state["commands"].append({"id": str(uuid.uuid4()), "action": "unpair",
                                               "payload": {"id": self.state["id"]}})
            return True

    def finish_unpair(self):
        with self.transaction():
            if (self.state["round"] or self.state.get("master_round") or self.state["commands"] or
                    self.db.execute("SELECT 1 FROM outbox LIMIT 1").fetchone()):
                return False
            self.state.update(connection=None, pair_pending=None, request=None, revision=0, applied_revision=0,
                              applied_stake=None, unpair_requested=False, error="")
            return True

    def reset(self, master_confirmed=False):
        with self.lock:
            if self.state.get("pair_pending"):
                raise ValueError("Completare o recuperare l'associazione pendente prima di ripartire da zero")
            if self.state["connection"] and not master_confirmed:
                raise ValueError("Attendere la conferma di dissociazione dal master prima del ripristino")
            if (self.state["round"] or self.state.get("master_round") or self.state["bet_in_progress"] or
                    self.state["commands"] or self.db.execute("SELECT 1 FROM outbox LIMIT 1").fetchone()):
                raise ValueError("Prima di ripartire verificare le partite aperte e sincronizzare gli eventi")
            directory = self.path.parent / "backups"
            directory.mkdir(exist_ok=True)
            archive = directory / ("laptop-" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f") +
                                   "-" + uuid.uuid4().hex + ".sqlite3")
            target = sqlite3.connect(archive)
            try:
                self.db.backup(target)
            finally:
                target.close()
            calibration = deepcopy(self.state["calibration"])
            with self.transaction():
                self.state = initial_state()
                self.state.update(calibration=calibration, last_reset_backup=str(archive))
            return archive

    def reply(self, response):
        with self.transaction():
            self.db.execute("DELETE FROM outbox WHERE seq<=?", (response["ack"],))
            d = response["device"]
            self.state.update(balance=d["balance"], config=d["config"], revision=d["revision"],
                              master_error=d["error"], last_result=d.get("last_result"), master_round=d["round"],
                              balance_is_estimate=d.get("balance_is_estimate", True),
                              balance_verified_at=d.get("balance_verified_at"), balance_verified_source=d.get("balance_verified_source"),
                              unpair_requested=d.get("unpair_requested", False),
                              session_net=d.get("session_net"), net=d.get("net", 0), wins=d.get("wins", 0), losses=d.get("losses", 0))
            if response.get("command_id"):
                self.state["commands"] = [c for c in self.state["commands"] if c["id"] != response["command_id"]]
            if self.state["round"] and not d["round"] and not self.db.execute("SELECT 1 FROM outbox LIMIT 1").fetchone():
                self.state.update(round=None, request=None)
            grant = response.get("grant")
            if grant and grant["status"] == "reserved" and self.state["round"] is None:
                self.state["round"] = deepcopy(grant)
            if grant and grant["status"] == "settled" and self.state["round"] is None:
                self.state["request"] = None

    def import_legacy(self, path):
        raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        c = default_calibration()
        c["tiles"] = {str(k): list(v) for k, v in raw.get("tiles", {}).items()}
        for key in ("play", "raise", "lower"):
            c[key] = [int(raw.get(key + "_x", 0)), int(raw.get(key + "_y", 0))]
        for new, old in (("difficulty_lower", "lower_diff"), ("difficulty_raise", "raise_diff")):
            c[new] = [int(raw.get(old + "_x", 0)), int(raw.get(old + "_y", 0))]
        mapping = {"play": "sleep_play_or_collect", "after_play": "sleep_after_play", "tile": "sleep_click_tile",
                   "after_tile": "sleep_after_tile_click", "retry": "sleep_color_retry", "reveal": "tile_reveal_delay",
                   "reset": "sleep_decrease_bet_force", "bet": "sleep_increase_bet", "between": "sleep_between_rounds",
                   "collect": "sleep_play_or_collect", "second_tile": "sleep_click_tile",
                   "after_second_tile": "sleep_after_tile_click", "difficulty_lower": "sleep_decrease_diff_force",
                   "difficulty_raise": "sleep_set_difficulty", "board_retry": "tile_reveal_delay"}
        for new, old in mapping.items():
            if old in raw:
                c["delays"][new] = raw[old]
        c["tolerance"] = raw.get("color_tolerance", 50)
        steps = []
        for old in raw.get("init_steps", []):
            if old.get("action") == "set_bet_min":
                steps.append({"action": "reset"})
            elif old.get("action") == "wait":
                steps.append({"action": "wait", "seconds": old.get("seconds", 1)})
            elif old.get("action") == "click":
                steps.append({"action": "click", "point": [old.get("x", 0), old.get("y", 0)]})
        if sum(s["action"] == "reset" for s in steps) == 1:
            c["steps"] = steps + [{"action": "target"}]
        self.update(calibration=c)

    def close(self):
        self.db.close()
