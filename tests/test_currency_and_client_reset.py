"""Euro input/output and archival client reset; no physical screen operations."""
from contextlib import closing
import json
from pathlib import Path
import queue
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from client_store import ClientStore
from laptop_client import LaptopClient
from mine_protocol import display, euro, money


class CurrencyTest(unittest.TestCase):
    def test_currencies_and_exact_fractional_values(self):
        for raw, expected in (("0,10", 100), ("0.100", 100), ("20", 20000), ("20.000", 20000),
                              ("2000", 2000000), ("2000,00", 2000000), ("1,999.91", 1999910),
                              ("1.999,91", 1999910), ("1.999,91 €", 1999910), ("€ 0,154", 154),
                              ("19,684", 19684), ("1,999", 1999)):
            with self.subTest(raw=raw):
                self.assertEqual(money(raw), expected)
                self.assertEqual(money(display(expected)), expected)
        for raw in ("1,99.91", "1.999.91", "2,000,000", "1€2", "1,", "NaN", "-0,01", "0,0001"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                money(raw)
        self.assertEqual(display(100), "0,10")
        self.assertEqual(display(20000), "20,00")
        self.assertEqual(euro(1999910), "1.999,91 €")
        self.assertEqual(euro(3000), "3,00 €")
        self.assertEqual(euro(154), "0,154 €")
        self.assertEqual(euro(-9), "-0,009 €")
        self.assertEqual(euro(-19684), "-19,684 €")


class ClientResetTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ClientStore(Path(self.temp.name) / "laptop.sqlite3")

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def test_new_client_has_no_assumed_capital(self):
        self.assertEqual(self.store.snapshot()["balance"], 0)
        self.assertFalse(self.store.snapshot()["confirmed"])

    def test_reset_archives_old_balance_identity_and_keeps_calibration(self):
        self.store.update(balance=1999910, confirmed=True, calibration={"sentinel": [1, 2]})
        original = self.store.snapshot()
        archive = self.store.reset()
        fresh = self.store.snapshot()
        self.assertNotEqual(fresh["id"], original["id"])
        self.assertEqual(fresh["balance"], 0)
        self.assertFalse(fresh["confirmed"])
        self.assertEqual(fresh["calibration"], original["calibration"])
        self.assertIsNone(fresh["connection"])
        self.assertEqual(fresh["sequence"], 0)
        with closing(sqlite3.connect(archive)) as db:
            old = json.loads(db.execute("SELECT payload FROM state WHERE id=1").fetchone()[0])
        self.assertEqual(old, original)

    def test_reset_refuses_open_round_unsent_events_and_connected_authority(self):
        self.store.update(round={"id": "one", "status": "uncertain"})
        with self.assertRaises(ValueError):
            self.store.reset()
        self.store.update(round=None)
        self.store.emit("clear_error", {})
        with self.assertRaises(ValueError):
            self.store.reset()
        self.store.db.execute("DELETE FROM outbox")
        self.store.db.commit()
        self.store.update(connection={"url": "https://master"})
        with self.assertRaises(ValueError):
            self.store.reset()

    def test_local_reset_first_requests_master_unpair_without_losing_identity(self):
        self.store.update(connection={"url": "https://master"}, confirmed=True, balance=1999910)
        client = LaptopClient(self.store, queue.Queue())
        original = self.store.snapshot()["id"]
        self.assertIsNone(client.reset_local())
        self.assertEqual(self.store.snapshot()["id"], original)
        self.assertTrue(self.store.snapshot()["reset_after_unpair"])
        self.assertEqual(self.store.snapshot()["commands"][0]["action"], "unpair")
        self.assertIsNone(client.reset_local())
        self.assertEqual(len(self.store.snapshot()["commands"]), 1)

    def test_enable_waits_for_balance_receipt(self):
        self.store.update(connection={"url": "https://master"})
        self.store.command("balance", {"balance": 1999910, "reason": "Verificato"})
        client = LaptopClient(self.store, queue.Queue())
        with self.assertRaisesRegex(ValueError, "conferma del master"):
            client.arm()
        self.assertFalse(client.armed.is_set())

    def test_failed_backup_does_not_reset(self):
        original = self.store.snapshot()
        with patch("client_store.sqlite3.connect", side_effect=OSError("Disk unavailable")):
            with self.assertRaises(OSError):
                self.store.reset()
        self.assertEqual(self.store.snapshot(), original)

    def test_reset_preserves_pending_pairing_until_master_receipt_is_recovered(self):
        self.store.update(pair_pending={"token": "pending-receipt"})
        original = self.store.snapshot()
        with self.assertRaisesRegex(ValueError, "associazione pendente"):
            self.store.reset()
        self.assertEqual(self.store.snapshot(), original)


if __name__ == "__main__":
    unittest.main()
