from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from pathlib import Path
import os, sqlite3, secrets, time

APP_VERSION = os.getenv("AT_CANVAS_VERSION", "0.1.0")
DB_PATH = os.getenv("AT_CANVAS_DB", "/data/at-canvas.db")

app = FastAPI(title="AT Canvas API", version=APP_VERSION)


def db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS pairing_codes (
            code TEXT PRIMARY KEY,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            claimed INTEGER NOT NULL DEFAULT 0,
            device_token TEXT
        );
        CREATE TABLE IF NOT EXISTS displays (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            room TEXT,
            token TEXT UNIQUE NOT NULL,
            resolution TEXT DEFAULT '1920x1080',
            orientation TEXT DEFAULT 'landscape',
            brightness INTEGER DEFAULT 100,
            current_layout TEXT DEFAULT 'Unassigned',
            client_version TEXT DEFAULT 'unknown',
            last_seen INTEGER DEFAULT 0,
            desired_command TEXT
        );
        """)


@app.on_event("startup")
def startup():
    init_db()


class PairClaim(BaseModel):
    code: str
    name: str
    room: str | None = None


class Heartbeat(BaseModel):
    token: str
    client_version: str = "unknown"
    resolution: str = "unknown"


@app.get("/api/health")
def health():
    return {"ok": True, "version": APP_VERSION}


@app.post("/api/pair/request")
def pair_request():
    now = int(time.time())
    for _ in range(20):
        code = f"{secrets.randbelow(1000000):06d}"
        try:
            with db() as c:
                c.execute("INSERT INTO pairing_codes(code,created_at,expires_at) VALUES(?,?,?)", (code, now, now + 900))
            return {"code": code, "expires_in": 900}
        except sqlite3.IntegrityError:
            continue
    raise HTTPException(500, "Could not allocate pairing code")


@app.post("/api/pair/claim")
def pair_claim(body: PairClaim):
    now = int(time.time())
    with db() as c:
        row = c.execute("SELECT * FROM pairing_codes WHERE code=?", (body.code,)).fetchone()
        if not row or row["claimed"] or row["expires_at"] < now:
            raise HTTPException(400, "Invalid or expired pairing code")
        token = secrets.token_urlsafe(32)
        cur = c.execute("INSERT INTO displays(name,room,token,last_seen) VALUES(?,?,?,?)", (body.name, body.room, token, now))
        c.execute("UPDATE pairing_codes SET claimed=1,device_token=? WHERE code=?", (token, body.code))
        return {"paired": True, "display_id": cur.lastrowid, "token": token}


@app.get("/api/pair/status/{code}")
def pair_status(code: str):
    with db() as c:
        row = c.execute("SELECT * FROM pairing_codes WHERE code=?", (code,)).fetchone()
        if not row:
            raise HTTPException(404, "Pairing code not found")
        return {"claimed": bool(row["claimed"]), "token": row["device_token"] if row["claimed"] else None}


@app.post("/api/display/heartbeat")
def display_heartbeat(body: Heartbeat):
    now = int(time.time())
    with db() as c:
        row = c.execute("SELECT * FROM displays WHERE token=?", (body.token,)).fetchone()
        if not row:
            raise HTTPException(401, "Unknown display token")
        c.execute("UPDATE displays SET last_seen=?,client_version=?,resolution=? WHERE token=?", (now, body.client_version, body.resolution, body.token))
        return {"ok": True, "display": row["name"], "layout": row["current_layout"], "brightness": row["brightness"], "command": row["desired_command"]}


@app.get("/api/displays")
def displays():
    now = int(time.time())
    with db() as c:
        rows = c.execute("SELECT * FROM displays ORDER BY name").fetchall()
        return [dict(r) | {"online": now - r["last_seen"] < 60} for r in rows]


@app.post("/api/displays/{display_id}/command/{command}")
def send_command(display_id: int, command: str):
    allowed = {"reload", "reboot", "screen_off", "screen_on", "update", "identify"}
    if command not in allowed:
        raise HTTPException(400, "Unsupported command")
    with db() as c:
        cur = c.execute("UPDATE displays SET desired_command=? WHERE id=?", (command, display_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Display not found")
    return {"queued": True, "command": command}


ADMIN_HTML = '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AT Canvas</title><style>
:root{color-scheme:dark;--bg:#0b0d10;--panel:#13171c;--card:#171c22;--border:#262d35;--text:#eef2f6;--muted:#8e9aa7;--accent:#6aa7ff;--good:#45d483}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,system-ui,sans-serif}.shell{display:grid;grid-template-columns:230px 1fr;min-height:100vh}.side{background:#0f1216;border-right:1px solid var(--border);padding:22px}.brand{font-size:22px;font-weight:800;margin-bottom:24px}.brand span{color:var(--accent)}.nav a{display:block;color:var(--muted);padding:11px 12px;border-radius:10px;margin:3px 0}.nav a.active{background:var(--panel);color:var(--text)}main{padding:28px}.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px}.badge,.card{border:1px solid var(--border);background:var(--card);border-radius:16px}.badge{padding:7px 10px;color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.card{padding:18px}.metric{font-size:30px;font-weight:800}.muted{color:var(--muted);font-size:13px}.section{margin-top:20px}.form{display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:10px}button,input{font:inherit}button{background:var(--accent);border:0;padding:10px 14px;border-radius:10px;font-weight:700;cursor:pointer}.secondary{background:var(--panel);color:var(--text);border:1px solid var(--border)}input{background:#0f1318;color:var(--text);border:1px solid var(--border);border-radius:10px;padding:10px}.display{display:flex;justify-content:space-between;gap:12px;padding:14px 0;border-bottom:1px solid var(--border)}.dot{width:9px;height:9px;background:var(--good);border-radius:50%;display:inline-block;margin-right:8px}.offline{background:#6b7280}.actions{display:flex;gap:7px;flex-wrap:wrap}@media(max-width:900px){.shell{grid-template-columns:1fr}.side{display:none}.grid{grid-template-columns:1fr 1fr}.form{grid-template-columns:1fr}}</style></head><body><div class="shell"><aside class="side"><div class="brand">AT <span>Canvas</span></div><nav class="nav"><a class="active">Dashboard</a><a>Displays</a><a>Layouts</a><a>Media</a><a>Calendars</a><a>Events</a><a>Schedules</a><a>Updates</a><a>Settings</a></nav></aside><main><div class="top"><div><h1>Display Control</h1><div class="muted">Pair and manage your screens from one place.</div></div><div class="badge">v__VERSION__</div></div><div class="grid"><div class="card"><div class="muted">Displays</div><div id="total" class="metric">0</div></div><div class="card"><div class="muted">Online</div><div id="online" class="metric">0</div></div><div class="card"><div class="muted">Layouts</div><div class="metric">0</div></div><div class="card"><div class="muted">Updates</div><div class="metric">✓</div></div></div><div class="section card"><h2>Pair a display</h2><form id="pair" class="form"><input id="code" placeholder="6-digit code" maxlength="6" required><input id="name" placeholder="Display name e.g. Kitchen" required><input id="room" placeholder="Room (optional)"><button>Pair</button></form><div id="msg" class="muted" style="margin-top:10px"></div></div><div class="section card"><div class="top"><h2 style="margin:0">Displays</h2><button id="refresh" class="secondary" type="button">Refresh</button></div><div id="list"></div></div></main></div><script>
function esc(v){return String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}async function load(){const r=await fetch('/api/displays');const d=await r.json();document.getElementById('total').textContent=d.length;document.getElementById('online').textContent=d.filter(x=>x.online).length;const list=document.getElementById('list');list.innerHTML=d.length?'':'<div class="muted">No displays paired yet.</div>';d.forEach(x=>{const el=document.createElement('div');el.className='display';el.innerHTML=`<div><div><span class="dot ${x.online?'':'offline'}"></span><strong>${esc(x.name)}</strong></div><div class="muted">${esc(x.room||'No room')} · ${esc(x.resolution||'unknown')} · client ${esc(x.client_version||'unknown')} · ${esc(x.current_layout)}</div></div><div class="actions"><button class="secondary" data-id="${x.id}" data-cmd="identify">Identify</button><button class="secondary" data-id="${x.id}" data-cmd="reload">Reload</button><button class="secondary" data-id="${x.id}" data-cmd="screen_off">Off</button><button data-id="${x.id}" data-cmd="update">Update</button></div>`;list.appendChild(el)});document.querySelectorAll('[data-cmd]').forEach(b=>b.onclick=async()=>{await fetch(`/api/displays/${b.dataset.id}/command/${b.dataset.cmd}`,{method:'POST'});b.textContent='Queued ✓'})}document.getElementById('pair').onsubmit=async e=>{e.preventDefault();const msg=document.getElementById('msg');msg.textContent='Pairing…';const r=await fetch('/api/pair/claim',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({code:document.getElementById('code').value,name:document.getElementById('name').value,room:document.getElementById('room').value||null})});const j=await r.json();msg.textContent=r.ok?'Display paired successfully.':'Pairing failed: '+(j.detail||'Unknown error');if(r.ok){e.target.reset();load()}};document.getElementById('refresh').onclick=load;load();setInterval(load,15000)</script></body></html>'''.replace("__VERSION__", APP_VERSION)


@app.get("/", response_class=HTMLResponse)
def admin_ui():
    return ADMIN_HTML


PAIR_HTML = '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;background:#050608;color:#f4f7fb;font-family:system-ui;display:grid;place-items:center;min-height:100vh;text-align:center}.box{padding:40px}.code{font-size:clamp(58px,12vw,140px);letter-spacing:.12em;font-weight:850}.muted{color:#8290a0;font-size:20px}.ok{color:#54dd91}</style></head><body><div class="box"><div class="muted">PAIR THIS DISPLAY</div><div class="code" id="code">------</div><div class="muted" id="status">Requesting pairing code…</div></div><script>let c='';async function start(){let r=await fetch('/api/pair/request',{method:'POST'});let j=await r.json();c=j.code;document.getElementById('code').textContent=c;document.getElementById('status').textContent='Enter this code in AT Canvas';setInterval(check,2000)}async function check(){if(!c)return;let r=await fetch('/api/pair/status/'+c);let j=await r.json();if(j.claimed){const s=document.getElementById('status');s.className='muted ok';s.textContent='Paired ✓ — display can now start';}}start()</script></body></html>'''


@app.get("/pair", response_class=HTMLResponse)
def pairing_screen():
    return PAIR_HTML
