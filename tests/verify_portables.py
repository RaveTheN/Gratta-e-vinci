"""Validate extracted executables in a clean PATH and benchmark 20 synthetic peers.

Run from the laptop project: python tests/verify_portables.py dist/packages-....json
No browser, screenshots, physical mouse, or real accounts are used.
"""
import argparse
import asyncio
from contextlib import closing
import csv
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile

import aiohttp
import psutil

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mine_protocol import DEFAULT_CONFIG


async def poll(predicate, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        await asyncio.sleep(0.1)
    raise AssertionError("Timeout verifica portatile")


def environment():
    result = dict(os.environ)
    for key in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
        result.pop(key, None)
    result["PATH"] = str(Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32")
    return result


def extract(product, directory):
    directory.mkdir()
    with zipfile.ZipFile(product["zip"]) as archive:
        for name in archive.namelist():
            assert (directory / name).resolve().is_relative_to(directory.resolve())
            assert "/data/" not in name and not name.endswith((".sqlite3", "master.key", "master.crt", "gratta_settings.json"))
        archive.extractall(directory)
    return directory / Path(product["exe"]).parent.name / Path(product["exe"]).name


async def verify(manifest):
    products = {p["target"]: p for p in json.loads(manifest.read_text(encoding="utf-8"))}
    assert set(products) == {"client", "master"}
    report = {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "packages": products,
              "physical_clicks": 0, "environment": "Windows x64; PATH solo System32, PYTHONHOME/PYTHONPATH rimossi",
              "limits": "Host con Python installato; non è una macchina Windows vergine. DPI e hardware esterni non verificati."}
    with tempfile.TemporaryDirectory(prefix="mine-portable-check-") as temporary:
        base = Path(temporary)
        client_exe = extract(products["client"], base / "client")
        master_exe = extract(products["master"], base / "master")
        output = base / "client-check.json"
        started = time.monotonic()
        process = subprocess.Popen([str(client_exe), "--data-dir", str(base / "client-data"), "--self-test", str(output)],
            cwd=base, env=environment(), creationflags=subprocess.CREATE_NO_WINDOW)
        peak = 0
        deadline = time.monotonic() + 60
        try:
            while process.poll() is None:
                assert time.monotonic() < deadline, "Client self-test bloccato"
                try:
                    peak = max(peak, psutil.Process(process.pid).memory_info().rss)
                except psutil.NoSuchProcess:
                    pass
                await asyncio.sleep(0.05)
            assert process.returncode == 0
            client_check = json.loads(output.read_text())
            assert client_check["ok"] and client_check["physical_clicks"] == 0
            assert client_check["tabs"] == ["Stato", "Calibrazione", "Cambio/reset puntata", "Tempi"]
            report["client"] = {"self_test_ok": True, "startup_and_hidden_gui_seconds": time.monotonic() - started,
                                 "peak_rss_mib": peak / 2**20, "tabs": client_check["tabs"]}
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        log_path = base / "master.log"
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen([str(master_exe), "--data-dir", str(base / "master-data"), "--no-browser",
                                          "--admin-port", "0", "--device-port", "0"], stdout=log, stderr=log,
                cwd=base, env=environment(), creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                def address():
                    assert process.poll() is None, log_path.read_text(errors="replace")
                    return re.search(r"http://127\.0\.0\.1:(\d+)/#([\w-]+)", log_path.read_text(errors="replace"))
                started = time.monotonic()
                match = await poll(address)
                master_startup = time.monotonic() - started
                admin = "http://127.0.0.1:" + match[1]
                peers, identities, tokens, sequences = [], [], [], []
                latencies = []
                usage_start = psutil.Process(process.pid).cpu_times()
                cpu_start, cpu_wall = usage_start.user + usage_start.system, time.monotonic()
                memory = psutil.Process(process.pid).memory_info().rss
                async with aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True), timeout=aiohttp.ClientTimeout(total=20)) as http:
                    async def api(path, payload=None):
                        async with http.request("POST" if payload is not None else "GET", admin + "/api/" + path,
                                                json=payload, headers={"Origin": admin}) as r:
                            data = await r.json()
                            assert r.status == 200, data
                            return data
                    async def command(action, payload):
                        return await api("command", {"id": str(uuid.uuid4()), "action": action, "payload": payload})
                    await api("login", {"token": match[2]})
                    async with http.get(admin + "/app.js") as r:
                        assert r.status == 200
                        script_bytes = await r.read()
                        assert script_bytes == (ROOT.parent / "Gratta e vinci Master" / "web" / "app.js").read_bytes()
                        script = script_bytes.decode("utf-8")
                        assert "function moneyInput(value)" in script and "0,10" in script
                        assert "fraction[2]==='0'?fraction.slice(0,2):fraction" in script
                        assert all("function " + name + "(" in script for name in ("durationInput", "duration", "budgetSeconds"))
                        assert "duration(snapshot.usage)+' / '+duration(snapshot.settings.budget)" in script
                    async with http.get(admin + "/") as r:
                        assert r.status == 200
                        html_bytes = await r.read()
                        assert html_bytes == (ROOT.parent / "Gratta e vinci Master" / "web" / "index.html").read_bytes()
                        html = html_bytes.decode("utf-8")
                        for name in ("hours", "minutes", "seconds"):
                            assert re.search(r'name="' + name + r'" type="number"[^>]*step="1"', html)
                    status = await api("status")
                    lan = f"https://127.0.0.1:{status['device_port']}"
                    for index in range(20):
                        paired = await api("pair-code", {"host": "127.0.0.1"})
                        import base64, secrets
                        details = json.loads(base64.urlsafe_b64decode(paired["code"]))
                        pin = aiohttp.Fingerprint(bytes.fromhex(details["fingerprint"]))
                        did, token = str(uuid.uuid4()), secrets.token_urlsafe(32)
                        async with http.post(lan + "/pair", ssl=pin, json={"device": did, "token": token,
                                "secret": details["secret"], "config": {**DEFAULT_CONFIG, "name": f"SIMULATO {index+1}"}, "balance": 20000}) as r:
                            assert r.status == 200, await r.text()
                        peers.append(await http.ws_connect(lan + "/ws", ssl=pin,
                            headers={"X-Device": did, "Authorization": "Bearer " + token}))
                        identities.append(did)
                        tokens.append(token)
                        sequences.append(0)

                    async def sync(index, request=None, events=None):
                        before = time.perf_counter()
                        await peers[index].send_json({"version": 1, "ready": True, "busy": False,
                            "applied_revision": 1, "request": request, "events": events or []})
                        data = await peers[index].receive_json()
                        assert "error" not in data, data
                        latencies.append((time.perf_counter() - before) * 1000)
                        return data
                    await asyncio.gather(*(sync(i) for i in range(20)))
                    await command("settings", {**status["settings"], "target": 1000000})
                    await command("start", {})
                    expected, rounds = 400000, 0
                    for cycle in range(20):
                        grants = await asyncio.gather(*(sync(i, str(uuid.uuid4())) for i in range(20)))
                        events = []
                        for i, reply in enumerate(grants):
                            grant = reply["grant"]
                            assert grant and grant["status"] == "reserved"
                            won = (cycle + i) % 3 != 0
                            expected += 80 if won else -100
                            rounds += 1
                            board = ["blue"] * 19 + ["red"] * 6
                            if not won:
                                board[0], board[19] = "red", "blue"
                            sequences[i] += 1
                            events.append({"id": str(uuid.uuid4()), "seq": sequences[i], "kind": "result", "time": time.time(),
                                "body": {"round": grant["id"], "outcome": "win" if won else "loss",
                                         "selected": [1, 2] if won else [1], "observed": ["blue", "blue"] if won else ["red"],
                                         "board": board, "board_complete": True}})
                        await asyncio.gather(*(sync(i, events=[events[i]]) for i in range(20)))
                        memory = max(memory, psutil.Process(process.pid).memory_info().rss)
                    status = await api("status")
                    assert sum(d["balance"] for d in status["devices"]) == expected
                    assert status["session"]["progress"] == expected - 400000
                    await command("stop", {})
                    status = await api("status")
                    assert status["session"]["status"] == "closed"
                    async with http.get(admin + "/api/export/json") as r:
                        archive = await r.json()
                        assert len(archive["rounds"]) == rounds
                        assert all(token not in json.dumps(archive) for token in tokens)
                    async with http.get(admin + "/api/export/csv") as r:
                        rows = list(csv.DictReader(io.StringIO((await r.read()).decode("utf-8-sig"))))
                        assert len(rows) == rounds
                    async with http.get(admin + "/api/backup") as r:
                        assert (await r.read()).startswith(b"SQLite format 3")
                    cpu_end = psutil.Process(process.pid).cpu_times()
                    wall = time.monotonic() - cpu_wall
                    report["master"] = {"startup_seconds": master_startup, "clients": 20, "rounds": rounds,
                        "requests": len(latencies), "peak_rss_mib": memory / 2**20,
                        "cpu_seconds": cpu_end.user + cpu_end.system - cpu_start,
                        "cpu_percent_of_one_core": (cpu_end.user + cpu_end.system - cpu_start) / wall * 100,
                        "benchmark_wall_seconds": wall, "round_trip_median_ms": statistics.median(latencies),
                        "round_trip_p95_ms": sorted(latencies)[int(len(latencies)*0.95)],
                        "round_trip_max_ms": max(latencies), "final_total_milli": expected,
                        "json_csv_backup_verified": True, "served_money_assets_verified": True,
                        "served_duration_assets_verified": True}
                    idle_start = psutil.Process(process.pid).cpu_times()
                    idle_wall = time.monotonic()
                    for _ in range(3):
                        await asyncio.sleep(1)
                        await asyncio.gather(*(sync(i) for i in range(20)))
                    idle_end = psutil.Process(process.pid).cpu_times()
                    report["master"]["idle_20_peers_cpu_percent_of_one_core"] = (
                        idle_end.user + idle_end.system - idle_start.user - idle_start.system) / (time.monotonic()-idle_wall)*100
                    resumed = await command("start", {})
                    session_id = resumed["session"]["id"]
                    await command("pause", {})
                    resumed = await command("resume", {})
                    assert resumed["session"]["status"] == "active" and resumed["session"]["id"] == session_id
                    await command("pause", {})
                    unpairing = await command("unpair", {"id": identities[0]})
                    device = next(d for d in unpairing["devices"] if d["id"] == identities[0])
                    await peers[0].send_json({"version": 1, "ready": False, "busy": False, "events": [],
                                              "applied_revision": 1, "disarm_ack": device["disarm"]})
                    receipt = await peers[0].receive_json()
                    assert receipt["device"]["associated"] is False and receipt["grant"] is None
                    saved_balance = receipt["device"]["balance"]
                    await peers[0].close()
                    code = await api("pair-code", {"host": "127.0.0.1"})
                    details = json.loads(base64.urlsafe_b64decode(code["code"]))
                    token = secrets.token_urlsafe(32)
                    async with http.post(lan + "/pair", ssl=pin, json={"device": identities[0], "token": token,
                            "secret": details["secret"], "config": dict(DEFAULT_CONFIG), "balance": 1,
                            "sequence": sequences[0]}) as r:
                        assert r.status == 200, await r.text()
                    peers[0] = await http.ws_connect(lan + "/ws", ssl=pin,
                        headers={"X-Device": identities[0], "Authorization": "Bearer " + token})
                    receipt = await sync(0)
                    assert receipt["device"]["balance"] == saved_balance
                    for peer in peers:
                        await peer.close()
                    for _ in range(30):
                        status = await api("status")
                        if not any(d["online"] for d in status["devices"]):
                            break
                        await asyncio.sleep(0.1)
                    assert not any(d["online"] or d["busy"] or d["round"] for d in status["devices"])
                    async with http.post(admin + "/api/command", headers={"Origin": admin}, json={
                            "id": str(uuid.uuid4()), "action": "reset", "payload": {"confirmation": ""}}) as r:
                        assert r.status == 400, await r.text()
                    reset = await command("reset", {"confirmation": "RIPARTI"})
                    backup = Path(reset["reset_backup"])
                    assert backup.resolve().is_relative_to((base / "master-data" / "backups").resolve())
                    assert backup.is_file()
                    with closing(sqlite3.connect(backup.as_uri() + "?mode=ro", uri=True)) as connection:
                        assert connection.execute("PRAGMA quick_check").fetchone()[0] == "ok"
                        assert connection.execute("SELECT COUNT(*) FROM rounds").fetchone()[0] == rounds
                        previous = json.loads(connection.execute("SELECT payload FROM state WHERE id=1").fetchone()[0])
                        assert previous["current"] == session_id
                    assert reset["session"] is None and reset["usage"] == 0 and reset["sessions_today"] == 0
                    assert reset["settings"] == {"target": 3000, "budget": 18000, "minimum": 1,
                                                  "automatic": False, "max_sessions": 0}
                    assert {d["id"] for d in reset["devices"]} == set(identities)
                    assert all(d["reset_required"] and not d["associated"] and not d["enabled"] for d in reset["devices"])
                    assert {d["id"]: d["balance"] for d in reset["devices"]} == {d["id"]: d["balance"] for d in status["devices"]}
                    preserved = await api("export/json")
                    assert preserved["rounds"] == archive["rounds"]
                    assert next(s for s in preserved["sessions"] if s["id"] == session_id)["reason"] == "reset"
                    code = await api("pair-code", {"host": "127.0.0.1"})
                    details = json.loads(base64.urlsafe_b64decode(code["code"]))
                    did, token = str(uuid.uuid4()), secrets.token_urlsafe(32)
                    async with http.post(lan + "/pair", ssl=pin, json={"device": did, "token": token,
                            "secret": details["secret"], "config": {**DEFAULT_CONFIG, "name": "NUOVO DOPO RESET"},
                            "balance": 1999910}) as r:
                        assert r.status == 200, await r.text()
                    peers.append(await http.ws_connect(lan + "/ws", ssl=pin,
                        headers={"X-Device": did, "Authorization": "Bearer " + token}))
                    fresh = (await sync(len(peers) - 1))["device"]
                    assert fresh["balance"] == 1999910 and fresh["net"] == fresh["wins"] == fresh["losses"] == 0
                    assert fresh.get("last_result") is None
                    restarted = await command("start", {})
                    session = restarted["session"]
                    assert session["id"] != session_id
                    session_id = session["id"]
                    assert session["baseline"] == {did: 1999910} and session["net_by_device"] == {did: 0}
                    assert session["net"] == session["progress"] == session["capital_flow"] == 0
                    assert (await api("export/json?session=" + session_id))["rounds"] == []
                    await peers[-1].close()
                    closed = await command("shutdown", {})
                    assert closed["session"]["status"] == "paused_manual" and closed["session"]["id"] == session_id
                    assert closed["session"]["net"] == closed["session"]["progress"] == 0
                    report["master"]["resume_unpair_reassociate_shutdown_verified"] = True
                    report["master"]["reset_backup_archive_fresh_baseline_verified"] = True
                await poll(lambda: process.poll() is not None, 10)
                assert process.returncode == 0, log_path.read_text(errors="replace")
                await asyncio.sleep(0.25)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
    destination = ROOT / "bulk_results" / ("lan_portables_validation_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%fZ") + ".json")
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("VALIDATION_REPORT=" + str(destination), flush=True)
    print(json.dumps({k: report[k] for k in ("client", "master")}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    arguments = parser.parse_args()
    asyncio.run(verify(arguments.manifest))
