from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from pathlib import Path
import os, sqlite3, secrets, time

APP_VERSION = os.getenv("AT_CANVAS_VERSION", "0.1.1")
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


ADMIN_HTML = r'''<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AT Canvas</title>
<style>
:root{color-scheme:dark;--bg:#090c10;--side:#0d1116;--panel:#12171d;--card:#171d24;--border:#27303a;--text:#eef3f8;--muted:#91a0b2;--accent:#6aa7ff;--accent2:#4e8ff0;--good:#45d483;--warn:#f2b84b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.shell{display:grid;grid-template-columns:230px minmax(0,1fr);min-height:100vh}.side{background:var(--side);border-right:1px solid var(--border);padding:22px 18px;position:sticky;top:0;height:100vh}.brand{font-size:22px;font-weight:850;margin:3px 0 24px}.brand span{color:var(--accent)}.nav{display:flex;flex-direction:column;gap:4px}.nav button{width:100%;text-align:left;background:transparent;color:var(--muted);border:0;padding:11px 12px;border-radius:10px;font-weight:500;cursor:pointer}.nav button:hover{background:#131920;color:var(--text)}.nav button.active{background:var(--panel);color:var(--text);box-shadow:inset 3px 0 0 var(--accent)}main{padding:28px;min-width:0}.top{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:24px}.top h1{margin:0 0 6px;font-size:30px}.badge,.card{border:1px solid var(--border);background:var(--card);border-radius:16px}.badge{padding:7px 10px;color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.card{padding:18px}.metric{font-size:30px;font-weight:850;margin-top:2px}.muted{color:var(--muted);font-size:13px}.section{margin-top:20px}.form{display:grid;grid-template-columns:1fr 1fr 1fr auto;gap:10px}button,input{font:inherit}button.action{background:var(--accent);color:#07111e;border:0;padding:10px 14px;border-radius:10px;font-weight:800;cursor:pointer}.secondary{background:var(--panel)!important;color:var(--text)!important;border:1px solid var(--border)!important}input{background:#0e1319;color:var(--text);border:1px solid var(--border);border-radius:10px;padding:10px}.display{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 0;border-bottom:1px solid var(--border)}.display:last-child{border-bottom:0}.dot{width:9px;height:9px;background:var(--good);border-radius:50%;display:inline-block;margin-right:8px}.offline{background:#6b7280}.actions{display:flex;gap:7px;flex-wrap:wrap}.actions button{padding:8px 11px}.page{display:none}.page.active{display:block}.placeholder{display:grid;grid-template-columns:1.2fr .8fr;gap:16px}.empty{min-height:180px;display:flex;align-items:center;justify-content:center;text-align:center;border:1px dashed #34404d;border-radius:14px;padding:28px;color:var(--muted)}.feature-list{display:grid;gap:10px}.feature{padding:13px 14px;border-radius:12px;background:#10161c;border:1px solid var(--border)}.feature strong{display:block;margin-bottom:4px}.toolbar{display:flex;gap:9px;flex-wrap:wrap}.schedule-row{display:grid;grid-template-columns:120px 1fr auto;gap:12px;align-items:center;padding:12px 0;border-bottom:1px solid var(--border)}.mobile-nav{display:none}.status-good{color:var(--good)}.status-warn{color:var(--warn)}
@media(max-width:1000px){.grid{grid-template-columns:1fr 1fr}.form{grid-template-columns:1fr 1fr}.form button{grid-column:span 2}.placeholder{grid-template-columns:1fr}}
@media(max-width:760px){.shell{grid-template-columns:1fr}.side{display:none}.mobile-nav{display:flex;overflow:auto;gap:7px;margin-bottom:18px;padding-bottom:3px}.mobile-nav button{white-space:nowrap;background:var(--panel);color:var(--muted);border:1px solid var(--border);padding:9px 11px;border-radius:10px}.mobile-nav button.active{color:var(--text);border-color:var(--accent)}main{padding:18px}.grid{grid-template-columns:1fr 1fr}.form{grid-template-columns:1fr}.form button{grid-column:auto}.display{align-items:flex-start;flex-direction:column}.top{align-items:flex-start}.top h1{font-size:26px}}
</style>
</head>
<body>
<div class="shell">
<aside class="side">
  <div class="brand">AT <span>Canvas</span></div>
  <nav class="nav" id="desktopNav">
    <button class="active" data-page="dashboard">Dashboard</button>
    <button data-page="displays">Displays</button>
    <button data-page="layouts">Layouts</button>
    <button data-page="media">Media</button>
    <button data-page="calendars">Calendars</button>
    <button data-page="events">Events</button>
    <button data-page="schedules">Schedules</button>
    <button data-page="updates">Updates</button>
    <button data-page="settings">Settings</button>
  </nav>
</aside>
<main>
  <div class="mobile-nav" id="mobileNav"></div>

  <section class="page active" id="page-dashboard">
    <div class="top"><div><h1>Display Control</h1><div class="muted">Pair and manage your screens from one place.</div></div><div class="badge">v__VERSION__</div></div>
    <div class="grid"><div class="card"><div class="muted">Displays</div><div id="total" class="metric">0</div></div><div class="card"><div class="muted">Online</div><div id="online" class="metric">0</div></div><div class="card"><div class="muted">Layouts</div><div class="metric">0</div></div><div class="card"><div class="muted">System</div><div class="metric status-good">✓</div></div></div>
    <div class="section card"><h2>Pair a display</h2><form id="pair" class="form"><input id="code" placeholder="6-digit code" maxlength="6" required><input id="name" placeholder="Display name e.g. Kitchen" required><input id="room" placeholder="Room (optional)"><button class="action">Pair</button></form><div id="msg" class="muted" style="margin-top:10px"></div></div>
    <div class="section card"><div class="top"><div><h2 style="margin:0 0 4px">Displays</h2><div class="muted">Live status of paired screens.</div></div><button id="refresh" class="action secondary" type="button">Refresh</button></div><div id="list"></div></div>
  </section>

  <section class="page" id="page-displays">
    <div class="top"><div><h1>Displays</h1><div class="muted">Pair, monitor and remotely control every AT Canvas screen.</div></div><div class="badge">Device manager</div></div>
    <div class="card"><div class="top"><div><h2 style="margin:0">Paired displays</h2><div class="muted">Updates every 15 seconds.</div></div><button id="refreshDisplays" class="action secondary" type="button">Refresh</button></div><div id="displayManager"></div></div>
  </section>

  <section class="page" id="page-layouts">
    <div class="top"><div><h1>Layouts</h1><div class="muted">Create screen designs with layers and reusable widgets.</div></div><button class="action" type="button" disabled title="Coming in v0.2">+ New layout</button></div>
    <div class="placeholder"><div class="card"><h2>Layout designer</h2><div class="empty">The 16:9 drag-and-drop canvas is next to build.<br>It will include resize, positioning, locking and layer ordering.</div></div><div class="card"><h2>Layers</h2><div class="feature-list"><div class="feature"><strong>Background</strong><span class="muted">Base colour, image or video</span></div><div class="feature"><strong>Widgets</strong><span class="muted">Clock, calendar, photos, weather and more</span></div><div class="feature"><strong>Event overlays</strong><span class="muted">GIFs, animations and seasonal layers</span></div></div></div></div>
  </section>

  <section class="page" id="page-media"><div class="top"><div><h1>Media</h1><div class="muted">Manage photos, images, GIFs and videos used by layouts.</div></div><button class="action" type="button" disabled>Upload media</button></div><div class="card"><div class="empty">Media library coming next.<br>Planned: local uploads, Google Photos albums, GIF, WebP, MP4 and WebM.</div></div></section>

  <section class="page" id="page-calendars"><div class="top"><div><h1>Calendars</h1><div class="muted">Connect Google accounts and select multiple calendars per layout.</div></div><button class="action" type="button" disabled>Connect Google</button></div><div class="placeholder"><div class="card"><h2>Google Calendar</h2><div class="empty">Google OAuth integration will live on the server, not on the display clients.</div></div><div class="card"><h2>Planned views</h2><div class="feature-list"><div class="feature"><strong>Agenda</strong><span class="muted">Upcoming events</span></div><div class="feature"><strong>Week</strong><span class="muted">Seven-day overview</span></div><div class="feature"><strong>Month</strong><span class="muted">Traditional calendar grid</span></div></div></div></div></section>

  <section class="page" id="page-events"><div class="top"><div><h1>Events</h1><div class="muted">Seasonal and one-off overlays without changing the base dashboard.</div></div><button class="action" type="button" disabled>+ New event</button></div><div class="card"><div class="empty">Create Christmas, Halloween, birthdays, wedding countdowns and other scheduled overlays here.</div></div></section>

  <section class="page" id="page-schedules"><div class="top"><div><h1>Schedules</h1><div class="muted">Control layouts, brightness and screen power by time of day.</div></div><button class="action" type="button" disabled>+ New schedule</button></div><div class="card"><h2>Example weekday schedule</h2><div class="schedule-row"><strong>06:00</strong><span>Normal dashboard</span><span class="muted">100%</span></div><div class="schedule-row"><strong>22:00</strong><span>Night dashboard</span><span class="muted">10%</span></div><div class="schedule-row"><strong>23:30</strong><span>Screen off</span><span class="muted">Until 06:00</span></div></div></section>

  <section class="page" id="page-updates"><div class="top"><div><h1>Updates</h1><div class="muted">Server and display-client update management.</div></div><div class="badge">v__VERSION__</div></div><div class="grid"><div class="card"><div class="muted">Server version</div><div class="metric">__VERSION__</div></div><div class="card"><div class="muted">Update channel</div><div class="metric" style="font-size:22px">Development</div></div><div class="card"><div class="muted">Display updates</div><div class="metric">—</div></div><div class="card"><div class="muted">GitHub</div><div class="metric status-good">✓</div></div></div><div class="section card"><h2>Update controls</h2><p class="muted">The UI is ready for the update workflow. Automatic GitHub release checks, backup/rollback and remote display deployment will be wired into this section.</p></div></section>

  <section class="page" id="page-settings"><div class="top"><div><h1>Settings</h1><div class="muted">System-wide AT Canvas configuration.</div></div></div><div class="placeholder"><div class="card"><h2>Appearance</h2><div class="feature"><strong>Dark mode</strong><span class="muted">Default AT Canvas theme</span></div></div><div class="card"><h2>System</h2><div class="feature-list"><div class="feature"><strong>Timezone</strong><span class="muted">Europe/London</span></div><div class="feature"><strong>Version</strong><span class="muted">__VERSION__</span></div></div></div></div></section>
</main>
</div>
<script>
function esc(v){return String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
const pageNames=['dashboard','displays','layouts','media','calendars','events','schedules','updates','settings'];
const desktopButtons=[...document.querySelectorAll('#desktopNav [data-page]')];
const mobileNav=document.getElementById('mobileNav');
desktopButtons.forEach(b=>{const clone=b.cloneNode(true);clone.classList.remove('active');mobileNav.appendChild(clone)});
function showPage(name,push=true){if(!pageNames.includes(name))name='dashboard';document.querySelectorAll('.page').forEach(p=>p.classList.toggle('active',p.id==='page-'+name));document.querySelectorAll('[data-page]').forEach(b=>b.classList.toggle('active',b.dataset.page===name));if(push){history.replaceState(null,'','#'+name)}if(name==='displays')loadDisplays()}
document.querySelectorAll('[data-page]').forEach(b=>b.addEventListener('click',()=>showPage(b.dataset.page)));
window.addEventListener('hashchange',()=>showPage(location.hash.slice(1)||'dashboard',false));
async function getDisplays(){const r=await fetch('/api/displays');if(!r.ok)throw new Error('Could not load displays');return await r.json()}
function renderDisplayList(target,d){const list=document.getElementById(target);list.innerHTML=d.length?'':'<div class="muted">No displays paired yet.</div>';d.forEach(x=>{const el=document.createElement('div');el.className='display';el.innerHTML=`<div><div><span class="dot ${x.online?'':'offline'}"></span><strong>${esc(x.name)}</strong></div><div class="muted">${esc(x.room||'No room')} · ${esc(x.resolution||'unknown')} · client ${esc(x.client_version||'unknown')} · ${esc(x.current_layout)}</div></div><div class="actions"><button class="action secondary" data-id="${x.id}" data-cmd="identify">Identify</button><button class="action secondary" data-id="${x.id}" data-cmd="reload">Reload</button><button class="action secondary" data-id="${x.id}" data-cmd="screen_off">Off</button><button class="action" data-id="${x.id}" data-cmd="update">Update</button></div>`;list.appendChild(el)});list.querySelectorAll('[data-cmd]').forEach(b=>b.addEventListener('click',async()=>{const old=b.textContent;const r=await fetch(`/api/displays/${b.dataset.id}/command/${b.dataset.cmd}`,{method:'POST'});b.textContent=r.ok?'Queued ✓':'Failed';setTimeout(()=>b.textContent=old,1800)}))}
async function load(){try{const d=await getDisplays();document.getElementById('total').textContent=d.length;document.getElementById('online').textContent=d.filter(x=>x.online).length;renderDisplayList('list',d)}catch(e){document.getElementById('list').innerHTML='<div class="muted">Could not load displays.</div>'}}
async function loadDisplays(){try{renderDisplayList('displayManager',await getDisplays())}catch(e){document.getElementById('displayManager').innerHTML='<div class="muted">Could not load displays.</div>'}}
document.getElementById('pair').addEventListener('submit',async e=>{e.preventDefault();const msg=document.getElementById('msg');msg.textContent='Pairing…';const r=await fetch('/api/pair/claim',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({code:document.getElementById('code').value,name:document.getElementById('name').value,room:document.getElementById('room').value||null})});const j=await r.json();msg.textContent=r.ok?'Display paired successfully.':'Pairing failed: '+(j.detail||'Unknown error');if(r.ok){e.target.reset();load();loadDisplays()}});
document.getElementById('refresh').addEventListener('click',load);document.getElementById('refreshDisplays').addEventListener('click',loadDisplays);showPage(location.hash.slice(1)||'dashboard',false);load();setInterval(()=>{load();if(document.getElementById('page-displays').classList.contains('active'))loadDisplays()},15000);
</script>
</body>
</html>'''.replace("__VERSION__", APP_VERSION)


@app.get("/", response_class=HTMLResponse)
def admin_ui():
    return ADMIN_HTML


PAIR_HTML = '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;background:#050608;color:#f4f7fb;font-family:system-ui;display:grid;place-items:center;min-height:100vh;text-align:center}.box{padding:40px}.code{font-size:clamp(58px,12vw,140px);letter-spacing:.12em;font-weight:850}.muted{color:#8290a0;font-size:20px}.ok{color:#54dd91}</style></head><body><div class="box"><div class="muted">PAIR THIS DISPLAY</div><div class="code" id="code">------</div><div class="muted" id="status">Requesting pairing code…</div></div><script>let c='';async function start(){let r=await fetch('/api/pair/request',{method:'POST'});let j=await r.json();c=j.code;document.getElementById('code').textContent=c;document.getElementById('status').textContent='Enter this code in AT Canvas';setInterval(check,2000)}async function check(){if(!c)return;let r=await fetch('/api/pair/status/'+c);let j=await r.json();if(j.claimed){const s=document.getElementById('status');s.className='muted ok';s.textContent='Paired ✓ — display can now start';}}start()</script></body></html>'''


@app.get("/pair", response_class=HTMLResponse)
def pairing_screen():
    return PAIR_HTML
