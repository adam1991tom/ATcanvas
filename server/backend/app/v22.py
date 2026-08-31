from pathlib import Path
from fastapi.responses import FileResponse, HTMLResponse
from . import v21

app = v21.app
v21.v2.APP_VERSION = '0.2.2'
v21.v2.main.APP_VERSION = '0.2.2'

ASSET_DIR = Path(__file__).with_name('assets')
LOGO_FILE = ASSET_DIR / 'atcanvas-logo.webp'

@app.get('/assets/atcanvas-logo.webp')
def atcanvas_logo():
    return FileResponse(LOGO_FILE, media_type='image/webp')

# Replace the original pairing page with the branded AT Canvas pairing screen.
app.router.routes[:] = [
    r for r in app.router.routes
    if not (getattr(r, 'path', None) == '/pair' and 'GET' in getattr(r, 'methods', set()))
]

PAIR_HTML = '''<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pair AT Canvas</title>
<link rel="icon" href="/assets/atcanvas-logo.webp">
<style>
:root{color-scheme:dark;--accent:#b100ff;--accent2:#7b2cff;--text:#f7f3fb;--muted:#ad9aba}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:radial-gradient(circle at 50% 15%,#2a0a3c 0,#0c0711 34%,#050507 72%);color:var(--text);font-family:Inter,system-ui,sans-serif;text-align:center}
.wrap{width:min(900px,92vw);padding:42px 24px}
.logo{width:min(440px,72vw);height:auto;filter:drop-shadow(0 0 28px rgba(177,0,255,.28));margin-bottom:24px}
.kicker{font-size:16px;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);font-weight:700}
.code{font-size:clamp(64px,13vw,150px);font-weight:900;letter-spacing:.14em;line-height:1;margin:18px 0;background:linear-gradient(180deg,#fff,#dcb8ff 58%,#a949ff);-webkit-background-clip:text;background-clip:text;color:transparent;text-shadow:0 0 32px rgba(177,0,255,.12)}
.status{font-size:20px;color:var(--muted)}
.ok{color:#66e39b}
.pill{display:inline-flex;margin-top:22px;padding:9px 14px;border:1px solid #4b2b5c;border-radius:999px;background:#150d1d;color:#c7b6d1;font-size:13px}
</style>
</head>
<body>
<div class="wrap">
<img class="logo" src="/assets/atcanvas-logo.webp" alt="AT Canvas">
<div class="kicker">Pair this display</div>
<div class="code" id="code">------</div>
<div class="status" id="status">Requesting pairing code…</div>
<div class="pill">Enter this code in AT Canvas → Displays</div>
</div>
<script>
let code='';
async function start(){
  const r=await fetch('/api/pair/request',{method:'POST'});
  const j=await r.json();
  code=j.code;
  document.getElementById('code').textContent=code.slice(0,3)+' '+code.slice(3);
  document.getElementById('status').textContent='Waiting for the server to claim this display';
  setInterval(check,2000);
}
async function check(){
  if(!code)return;
  const r=await fetch('/api/pair/status/'+code);
  if(!r.ok)return;
  const j=await r.json();
  if(j.claimed){
    const s=document.getElementById('status');
    s.className='status ok';
    s.textContent='Paired successfully ✓';
  }
}
start();
</script>
</body>
</html>'''

@app.get('/pair', response_class=HTMLResponse)
def pairing_screen_v22():
    return PAIR_HTML
