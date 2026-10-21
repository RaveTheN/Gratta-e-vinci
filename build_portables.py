"""Build clean, uniquely named Windows bundles; never replace an application's data/."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", choices=("client", "master", "both"), default="both")
    args = parser.parse_args()
    if sys.platform != "win32" or sys.maxsize <= 2**32:
        raise SystemExit("Eseguire con Python Windows a 64 bit")
    client = Path(__file__).resolve().parent
    master = client.parent / "Gratta e vinci Master"
    if (client / "mine_protocol.py").read_bytes() != (master / "mine_protocol.py").read_bytes():
        raise SystemExit("Sincronizzare la copia di mine_protocol.py nel master prima del build")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%fZ")
    products = []
    for target, root, name, entry in (("client", client, "MineLaptop", "gratta_e_vinci_gui.py"),
                                       ("master", master, "MineMaster", "mine_master.py")):
        if args.target not in (target, "both"):
            continue
        destination = root / "dist" / stamp
        work = client / "build" / stamp / target
        work.mkdir(parents=True)
        command = [sys.executable, "-m", "PyInstaller", "--onedir", "--name", name,
                   "--distpath", str(destination), "--workpath", str(work / "work"),
                   "--specpath", str(work), "--exclude-module", "openpyxl", "--exclude-module", "pytest"]
        for module in ("cv2", "numpy", "matplotlib", "scipy", "IPython"):
            command += ["--exclude-module", module]
        if target == "client":
            command += ["--windowed", "--hidden-import", "pynput.keyboard._win32", "--hidden-import", "pynput.mouse._win32"]
        else:
            command += ["--add-data", str(master / "web") + ";web", "--exclude-module", "tkinter",
                        "--exclude-module", "PIL", "--exclude-module", "pyautogui", "--exclude-module", "pynput"]
        command.append(str(root / entry))
        subprocess.run(command, cwd=root, check=True)
        folder = destination / name
        shutil.copy2(root / "README.md", folder / "LEGGIMI.md")
        forbidden = {"data", "gratta_settings.json", "master.key", "master.crt", ".venv", "bulk_results"}
        for path in folder.rglob("*"):
            if ((path.parent == folder and path.name == "data") or path.name in (forbidden - {"data"})
                    or path.suffix in (".sqlite3", ".db", ".xlsx")):
                raise RuntimeError(f"Dato personale inatteso nel pacchetto: {path.name}")
        archive = root / "dist" / f"{name}-{stamp}-win-x64.zip"
        with zipfile.ZipFile(archive, "x", zipfile.ZIP_DEFLATED) as zipped:
            for path in sorted(folder.rglob("*")):
                if path.is_file():
                    zipped.write(path, path.relative_to(destination))
        with archive.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        products.append({"target": target, "exe": str(folder / (name + ".exe")), "zip": str(archive),
                         "zip_bytes": archive.stat().st_size, "sha256": digest})
    manifest = client / "dist" / f"packages-{stamp}.json"
    manifest.write_text(json.dumps(products, indent=2), encoding="utf-8")
    print("PACKAGES_MANIFEST=" + str(manifest), flush=True)


if __name__ == "__main__":
    main()
