#!/usr/bin/env python3
"""AT Canvas display client - V0.1 skeleton.
Stores a paired token locally, sends heartbeats, and is ready for kiosk/update commands.
"""
import json, os, time, urllib.request
from pathlib import Path

SERVER = os.getenv("AT_CANVAS_SERVER", "http://10.0.0.2:8077")
STATE = Path(os.getenv("AT_CANVAS_STATE", "/var/lib/at-canvas/client.json"))
VERSION = "0.1.0"


def post(path, payload):
    req = urllib.request.Request(SERVER + path, data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)


def main():
    while True:
        if not STATE.exists():
            print(f"Not paired. Open {SERVER}/pair on this display for V0.1 pairing.")
            time.sleep(30)
            continue
        state = json.loads(STATE.read_text())
        try:
            reply = post("/api/display/heartbeat", {"token": state["token"], "client_version": VERSION, "resolution": state.get("resolution", "unknown")})
            print(reply)
        except Exception as exc:
            print("heartbeat failed:", exc)
        time.sleep(15)

if __name__ == "__main__":
    main()
