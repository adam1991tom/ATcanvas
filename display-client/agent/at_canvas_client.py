#!/usr/bin/env python3
"""AT Canvas Display Client.

Linux display appliance agent for AT Canvas. Uses only Python's standard library.
It owns pairing, local kiosk status UI, heartbeats and remote command execution.
"""

from __future__ import annotations

import html
import json
import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

VERSION = "0.2.0"
SERVER = os.getenv("AT_CANVAS_SERVER", "http://10.0.0.2:8077").rstrip("/")
STATE_DIR = Path(os.getenv("AT_CANVAS_STATE_DIR", "/var/lib/at-canvas"))
STATE_FILE = STATE_DIR / "client.json"
LOCAL_PORT = int(os.getenv("AT_CANVAS_LOCAL_PORT", "8787"))
HEARTBEAT_SECONDS = int(os.getenv("AT_CANVAS_HEARTBEAT_SECONDS", "15"))
PAIR_POLL_SECONDS = int(os.getenv("AT_CANVAS_PAIR_POLL_SECONDS", "3"))
DISPLAY = os.getenv("DISPLAY", ":0")
XAUTHORITY = os.getenv("XAUTHORITY", "/home/atcanvas/.Xauthority")
KIOSK_USER = os.getenv("AT_CANVAS_KIOSK_USER", "atcanvas")
AUTO_LAUNCH = os.getenv("AT_CANVAS_AUTO_LAUNCH", "1") not in {"0", "false", "False"}

runtime = {
    "mode": "starting",
    "pair_code": None,
    "pair_expires": None,
    "display_name": None,
    "room": None,
    "online": False,
    "last_seen": None,
    "last_error": None,
    "resolution": "unknown",
    "brightness": 100,
    "identify_until": 0,
}
lock = threading.Lock()
browser_process: subprocess.Popen | None = None


def log(message: str) -> None:
    print(time.strftime("%Y-%m-%d %H:%M:%S"), message, flush=True)


def api(method: str, path: str, payload: dict | None = None, timeout: int = 10) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        SERVER + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "User-Agent": f"AT-Canvas-Client/{VERSION}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(STATE_FILE)


def detect_resolution() -> str:
    try:
        out = subprocess.check_output(
            ["xrandr", "--current"],
            env={**os.environ, "DISPLAY": DISPLAY, "XAUTHORITY": XAUTHORITY},
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=4,
        )
        for line in out.splitlines():
            if " connected " in line:
                for part in line.split():
                    if "x" in part and "+" in part and part[0].isdigit():
                        return part.split("+")[0]
    except Exception:
        pass
    return "unknown"


def run_command(args: list[str], timeout: int = 15) -> bool:
    try:
        subprocess.run(args, check=True, timeout=timeout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as exc:
        log(f"command failed ({' '.join(args)}): {exc}")
        return False


def xcmd(*args: str) -> bool:
    env = {**os.environ, "DISPLAY": DISPLAY, "XAUTHORITY": XAUTHORITY}
    try:
        subprocess.run(list(args), check=True, env=env, timeout=10, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def screen_power(on: bool) -> None:
    # Raspberry Pi KMS/legacy helper when available.
    if shutil.which("vcgencmd"):
        run_command(["vcgencmd", "display_power", "1" if on else "0"])
    # Generic X11 fallback.
    xcmd("xset", "dpms", "force", "on" if on else "off")


def set_brightness(percent: int) -> None:
    percent = max(10, min(100, int(percent)))
    with lock:
        runtime["brightness"] = percent
    if shutil.which("brightnessctl"):
        run_command(["brightnessctl", "set", f"{percent}%"])
        return
    # xrandr software brightness fallback.
    try:
        env = {**os.environ, "DISPLAY": DISPLAY, "XAUTHORITY": XAUTHORITY}
        out = subprocess.check_output(["xrandr", "--current"], env=env, text=True, timeout=4)
        output = next(line.split()[0] for line in out.splitlines() if " connected " in line)
        subprocess.run(
            ["xrandr", "--output", output, "--brightness", f"{percent / 100:.2f}"],
            env=env,
            check=False,
            timeout=5,
        )
    except Exception:
        pass


def execute_remote_command(command: str | None) -> None:
    if not command:
        return
    log(f"remote command: {command}")
    if command == "reload":
        launch_browser(force=True)
    elif command == "identify":
        with lock:
            runtime["identify_until"] = time.time() + 15
    elif command == "screen_off":
        screen_power(False)
    elif command == "screen_on":
        screen_power(True)
    elif command == "reboot":
        run_command(["systemctl", "reboot"], timeout=5)
    elif command == "update":
        updater = Path("/usr/local/sbin/at-canvas-update")
        if updater.exists():
            subprocess.Popen([str(updater)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def request_pairing_code() -> None:
    reply = api("POST", "/api/pair/request", {})
    now = int(time.time())
    with lock:
        runtime["mode"] = "pairing"
        runtime["pair_code"] = reply["code"]
        runtime["pair_expires"] = now + int(reply.get("expires_in", 900))
        runtime["last_error"] = None
    log(f"pairing code: {reply['code']}")


def pairing_loop() -> dict:
    while True:
        with lock:
            code = runtime.get("pair_code")
            expires = runtime.get("pair_expires") or 0
        if not code or time.time() >= expires:
            try:
                request_pairing_code()
            except Exception as exc:
                with lock:
                    runtime["last_error"] = f"Cannot reach AT Canvas server: {exc}"
                time.sleep(5)
                continue
            with lock:
                code = runtime["pair_code"]

        try:
            reply = api("GET", f"/api/pair/status/{code}")
            if reply.get("claimed") and reply.get("token"):
                state = {"token": reply["token"], "paired_at": int(time.time()), "server": SERVER}
                save_state(state)
                with lock:
                    runtime["mode"] = "connected"
                    runtime["pair_code"] = None
                    runtime["online"] = True
                log("display paired successfully")
                return state
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                with lock:
                    runtime["pair_code"] = None
            else:
                with lock:
                    runtime["last_error"] = f"Pairing status error: HTTP {exc.code}"
        except Exception as exc:
            with lock:
                runtime["last_error"] = f"Pairing status error: {exc}"
        time.sleep(PAIR_POLL_SECONDS)


def heartbeat_loop(state: dict) -> None:
    last_command = None
    while True:
        resolution = detect_resolution()
        with lock:
            runtime["resolution"] = resolution
        try:
            reply = api(
                "POST",
                "/api/display/heartbeat",
                {"token": state["token"], "client_version": VERSION, "resolution": resolution},
            )
            with lock:
                runtime["mode"] = "connected"
                runtime["online"] = True
                runtime["display_name"] = reply.get("display")
                runtime["last_seen"] = int(time.time())
                runtime["last_error"] = None
            if reply.get("brightness") is not None:
                set_brightness(reply["brightness"])
            command = reply.get("command")
            # Current server stores one desired command. Run it only once per
            # agent session to prevent command loops until command ACK lands.
            if command and command != last_command:
                execute_remote_command(command)
                last_command = command
            if not command:
                last_command = None
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                log("server rejected token; returning to pairing mode")
                try:
                    STATE_FILE.unlink()
                except FileNotFoundError:
                    pass
                with lock:
                    runtime["online"] = False
                    runtime["mode"] = "pairing"
                return
            with lock:
                runtime["online"] = False
                runtime["last_error"] = f"Heartbeat HTTP {exc.code}"
        except Exception as exc:
            with lock:
                runtime["online"] = False
                runtime["last_error"] = f"Server offline: {exc}"
        time.sleep(HEARTBEAT_SECONDS)


def status_html() -> str:
    with lock:
        state = dict(runtime)
    identify = state["identify_until"] > time.time()
    mode = state["mode"]
    code = state.get("pair_code") or "------"
    if mode == "pairing":
        headline = "Pair this display"
        content = f'<div class="code">{html.escape(code)}</div><p>Open AT Canvas on the server, go to <b>Displays</b>, and enter this code.</p>'
    elif mode == "connected":
        name = html.escape(state.get("display_name") or "AT Canvas Display")
        network = "Connected" if state.get("online") else "Server unavailable — using local fallback"
        headline = name
        content = f'<div class="ok">● {network}</div><p>Client v{VERSION} · {html.escape(state.get("resolution") or "unknown")}</p><p class="small">Waiting for the assigned AT Canvas layout renderer.</p>'
    else:
        headline = "AT Canvas is starting"
        content = "<p>Preparing display client…</p>"
    error = f'<div class="error">{html.escape(str(state["last_error"]))}</div>' if state.get("last_error") else ""
    identify_class = " identify" if identify else ""
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>AT Canvas Display</title><style>
html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:#080b0f;color:#f4f7fb;font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif}}body{{display:grid;place-items:center}}.wrap{{width:min(900px,88vw);text-align:center}}.brand{{font-weight:900;letter-spacing:.04em;color:#78aaff;margin-bottom:45px;font-size:clamp(22px,3vw,38px)}}h1{{font-size:clamp(36px,6vw,76px);margin:0 0 26px}}.code{{font-size:clamp(82px,15vw,180px);font-weight:950;letter-spacing:.12em;line-height:1;margin:35px 0;color:#fff}}p{{font-size:clamp(17px,2vw,28px);line-height:1.5;color:#a9b5c5}}.ok{{font-size:clamp(22px,3vw,38px);color:#50dc8e;font-weight:800;margin:35px 0 12px}}.small{{font-size:16px}}.error{{margin-top:30px;padding:14px 18px;border:1px solid #66353b;background:#2b1519;border-radius:12px;color:#ffabb3}}.identify{{position:fixed;inset:0;border:28px solid #78aaff;box-sizing:border-box;pointer-events:none;animation:pulse .65s infinite alternate}}@keyframes pulse{{to{{border-width:55px}}}}
</style><meta http-equiv='refresh' content='2'></head><body><div class='wrap'><div class='brand'>AT CANVAS</div><h1>{headline}</h1>{content}{error}</div><div class='{identify_class.strip()}'></div></body></html>"""


class StatusHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            payload = json.dumps({"ok": True, "version": VERSION, "mode": runtime["mode"]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        body = status_html().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:
        return


def serve_local_ui() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", LOCAL_PORT), StatusHandler)
    server.serve_forever()


def chromium_binary() -> str | None:
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(name)
        if found:
            return found
    return None


def launch_browser(force: bool = False) -> None:
    global browser_process
    if not AUTO_LAUNCH:
        return
    if browser_process and browser_process.poll() is None:
        if not force:
            return
        browser_process.terminate()
        try:
            browser_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            browser_process.kill()

    chromium = chromium_binary()
    if not chromium:
        log("Chromium not installed; local UI remains available on port 8787")
        return
    url = f"http://127.0.0.1:{LOCAL_PORT}/"
    args = [
        chromium,
        "--kiosk",
        "--no-first-run",
        "--disable-session-crashed-bubble",
        "--disable-infobars",
        "--disable-translate",
        "--overscroll-history-navigation=0",
        "--check-for-update-interval=31536000",
        url,
    ]
    env = {**os.environ, "DISPLAY": DISPLAY, "XAUTHORITY": XAUTHORITY}
    if os.geteuid() == 0 and shutil.which("runuser") and KIOSK_USER:
        args = ["runuser", "-u", KIOSK_USER, "--"] + args
    try:
        browser_process = subprocess.Popen(args, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("Chromium kiosk launched")
    except Exception as exc:
        log(f"Chromium launch failed: {exc}")


def browser_watchdog() -> None:
    while True:
        launch_browser()
        time.sleep(5)


def main() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TZ", "Europe/London")
    try:
        time.tzset()
    except AttributeError:
        pass

    threading.Thread(target=serve_local_ui, daemon=True, name="local-ui").start()
    threading.Thread(target=browser_watchdog, daemon=True, name="browser-watchdog").start()

    log(f"AT Canvas Display Client v{VERSION} starting; server={SERVER}; host={socket.gethostname()}")
    while True:
        state = load_state()
        if not state.get("token"):
            state = pairing_loop()
        heartbeat_loop(state)
        time.sleep(2)


if __name__ == "__main__":
    main()
