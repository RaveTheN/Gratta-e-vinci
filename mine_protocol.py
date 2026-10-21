"""Wire v1 validation shared by the portable client and master (no GUI imports)."""
from decimal import Decimal, DecimalException
import json
import os
from pathlib import Path
import re
import sqlite3
import sys

VERSION = 1
DEFAULT_CONFIG = {"name": "Laptop", "stake": 100, "mines": 6,
                  "multiplier": "1.80", "selection": "random", "pair": [1, 2]}


def integer(value, name, minimum=0, maximum=10**12):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name}: intero tra {minimum} e {maximum} richiesto")
    return value


def money(value):
    try:
        text = str(value).strip()
        if isinstance(value, str):
            if text.count("€") > 1:
                raise ValueError("Importo non valido")
            text = text.removeprefix("€").removesuffix("€").strip()
            if "," in text and "." in text:
                decimal = "," if text.rfind(",") > text.rfind(".") else "."
                grouping = "." if decimal == "," else ","
                whole, fraction = text.rsplit(decimal, 1)
                if (not re.fullmatch(r"[0-9]{1,3}(?:" + re.escape(grouping) + r"[0-9]{3})+", whole) or
                        not re.fullmatch(r"[0-9]{1,3}", fraction)):
                    raise ValueError("Importo non valido: usare 2000,00 oppure 1.999,91 / 1,999.91")
                text = whole.replace(grouping, "") + "." + fraction
            elif not re.fullmatch(r"[0-9]+(?:[.,][0-9]{1,3})?", text):
                raise ValueError("Importo non valido: usare euro e fino a tre decimali, per esempio 2000,00")
        amount = Decimal(text.replace(",", ".")) * 1000
        if not amount.is_finite() or amount != amount.to_integral_value():
            raise ValueError("Usare al massimo tre decimali")
        return integer(int(amount), "Importo")
    except (DecimalException, TypeError) as exc:
        raise ValueError("Importo non valido") from exc


def display(value):
    if type(value) is not int:
        raise ValueError("Importo interno non intero")
    whole, fraction = divmod(abs(value), 1000)
    decimals = f"{fraction:03d}"
    if decimals.endswith("0"):
        decimals = decimals[:2]
    return f"{'-' if value < 0 else ''}{whole},{decimals}"


def euro(value):
    decimals = display(value).split(",")[1]
    whole = f"{abs(value) // 1000:,}".replace(",", ".")
    return f"{'-' if value < 0 else ''}{whole},{decimals} €"


def config(raw):
    if not isinstance(raw, dict) or set(raw) != set(DEFAULT_CONFIG):
        raise ValueError("Configurazione incompleta o con campi sconosciuti")
    result = dict(raw)
    name = result["name"]
    if not isinstance(name, str) or not name.strip() or len(name) > 80:
        raise ValueError("Nome richiesto (massimo 80 caratteri)")
    integer(result["stake"], "Puntata", 1)
    integer(result["mines"], "Mine", 0, 23)
    if result["selection"] not in ("random", "fixed"):
        raise ValueError("Selezione non valida")
    pair = result["pair"]
    if not isinstance(pair, list) or len(pair) != 2:
        raise ValueError("Servono due celle")
    for cell in pair:
        integer(cell, "Cella", 1, 25)
    if pair[0] == pair[1]:
        raise ValueError("Le due celle devono essere distinte")
    try:
        multiplier = Decimal(str(result["multiplier"]).replace(",", "."))
        if not multiplier.is_finite() or not 1 <= multiplier <= 100000:
            raise ValueError("Moltiplicatore non valido")
        payout = multiplier * result["stake"]
        if payout != payout.to_integral_value():
            raise ValueError("Il pagamento richiede più di tre decimali")
        integer(int(payout), "Pagamento", 1)
    except DecimalException as exc:
        raise ValueError("Moltiplicatore non valido") from exc
    result["multiplier"] = str(multiplier)
    return result


def payout(profile):
    return int(Decimal(profile["multiplier"]) * profile["stake"])


def dumps(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def database(path):
    db = sqlite3.connect(path, check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA synchronous=FULL")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=5000")
    return db


def data_directory():
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    path = base / "data"
    path.mkdir(exist_ok=True)
    probe = path / f".write-{os.getpid()}"
    with probe.open("x") as stream:
        stream.write("ok")
    probe.unlink()
    return path


class InstanceLock:
    """Keep the file locked for the process lifetime; crashes release the OS lock."""
    def __init__(self, directory):
        import msvcrt
        self.file = (Path(directory) / "instance.lock").open("a+b")
        self.file.seek(0)
        self.file.write(b"0")
        self.file.flush()
        self.file.seek(0)
        try:
            msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self.file.close()
            raise RuntimeError("Applicazione già aperta con questa cartella dati") from None

    def close(self):
        self.file.close()
