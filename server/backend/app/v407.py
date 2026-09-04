import base64
import hmac
import hashlib
import os
import re
import secrets
import time

from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
from . import v406

app = v406.app
DB = v406.DB
BASE = v406.BASE
VERSION = '0.4.1'
BASE.APP_VERSION = VERSION
BASE.main.APP_VERSION = VERSION

_LOGO_FILE = BASE.UI_FILE.parent / 'assets' / 'atcanvas-logo.webp'
LOGO_DATA = 'data:image/webp;base64,' + base64.b64encode(_LOGO_FILE.read_bytes()).decode('ascii')

ADMIN_USER = os.getenv('AT_CANVAS_ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.getenv('AT_CANVAS_ADMIN_PASSWORD', '')
SESSION_COOKIE = 'atcanvas_session'
SESSION_TTL = 60 * 60 * 24 * 14  # 14 days


_SECRET_KEY_CACHE = None


def _secret_key():
    global _SECRET_KEY_CACHE
    if _SECRET_KEY_CACHE:
        return _SECRET_KEY_CACHE
    with DB() as c:
        row = c.execute("SELECT value FROM settings WHERE key='auth_secret_key'").fetchone()
        if row and row['value']:
            _SECRET_KEY_CACHE = row['value']
            return _SECRET_KEY_CACHE
        key = secrets.token_hex(32)
        c.execute(
            "INSERT INTO settings(key,value) VALUES('auth_secret_key',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key,)
        )
        _SECRET_KEY_CACHE = key
        return key


def _sign(value):
    mac = hmac.new(_secret_key().encode(), value.encode(), hashlib.sha256).hexdigest()
    return f'{value}.{mac}'


def _verify_session(token):
    if not token or '.' not in token:
        return False
    value, _, mac = token.rpartition('.')
    expected = hmac.new(_secret_key().encode(), value.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, expected):
        return False
    try:
        expires = int(value.rsplit(':', 1)[1])
    except (IndexError, ValueError):
        return False
    return expires >= int(time.time())


def _make_session():
    expires = int(time.time()) + SESSION_TTL
    return _sign(f'admin:{expires}')


_MEDIA_FILE_RE = re.compile(r'^/api/media/\d+/file$')
_PUBLIC_EXACT = {'/login', '/api/login', '/api/health', '/assets/atcanvas-logo.webp', '/api/events/active'}
_PUBLIC_PREFIXES = ('/display/', '/api/widget/')
# Wall-display kiosks are unauthenticated by design; a to-do/chore checklist shown on the
# display needs to be tickable from that same screen, so its toggle route stays public too
# (same trust boundary as anyone physically able to touch the display).
_TODO_TOGGLE_RE = re.compile(r'^/api/todos/\d+$')


def _is_public_get(path):
    if path in _PUBLIC_EXACT:
        return True
    if path.startswith(_PUBLIC_PREFIXES):
        return True
    if _MEDIA_FILE_RE.match(path):
        return True
    return False


_NO_CACHE_PATHS = {'/', '/login', '/admin-v2.js'}


@app.middleware('http')

async def require_login(request: Request, call_next):
    path = request.url.path
    if path in ('/login', '/api/login'):
        response = await call_next(request)
    elif request.method == 'GET' and _is_public_get(path):
        response = await call_next(request)
    elif request.method == 'PATCH' and _TODO_TOGGLE_RE.match(path):
        response = await call_next(request)
    elif not _verify_session(request.cookies.get(SESSION_COOKIE, '')):
        if path.startswith('/api/'):
            return JSONResponse({'detail': 'Login required'}, status_code=401)
        return RedirectResponse('/login')
    else:
        response = await call_next(request)
    # The admin shell/JS bundle changes on every deploy - never let a browser (or
    # an intermediate proxy) serve a stale cached copy after an update.
    if path in _NO_CACHE_PATHS:
        response.headers['Cache-Control'] = 'no-store'
    return response


class LoginBody(BaseModel):
    username: str
    password: str


LOGIN_HTML = '''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>AT Canvas</title>
<style>
:root{color-scheme:dark;--bg:#090c10;--card:#12171d;--border:#27303a;--text:#eef3f8;--muted:#91a0b2;--accent:#6aa7ff}
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--text);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.card{width:min(360px,92vw);background:var(--card);border:1px solid var(--border);border-radius:16px;padding:28px}
.brand{display:flex;justify-content:center;margin:0 0 20px}.brand img{width:170px;max-width:100%}
input{width:100%;background:#0e1319;color:var(--text);border:1px solid var(--border);border-radius:10px;padding:10px;margin-bottom:12px;font:inherit}
button{width:100%;background:var(--accent);color:#07111e;border:0;padding:11px;border-radius:10px;font-weight:800;cursor:pointer;font:inherit}
.msg{color:#f2b84b;font-size:13px;min-height:18px;margin-top:10px}
</style></head><body>
<form class="card" id="f">
<div class="brand"><img src="LOGO_DATA_PLACEHOLDER" alt="AT Canvas"></div>
<input id="u" name="username" placeholder="Username" autocomplete="username" required>
<input id="p" name="password" type="password" placeholder="Password" autocomplete="current-password" required>
<button type="submit">Sign in</button>
<div class="msg" id="msg"></div>
</form>
<script>
document.getElementById('f').addEventListener('submit', async e => {
  e.preventDefault();
  const msg = document.getElementById('msg');
  msg.textContent = 'Signing in…';
  const r = await fetch('/api/login', {method:'POST', headers:{'content-type':'application/json'},
    body: JSON.stringify({username: document.getElementById('u').value, password: document.getElementById('p').value})});
  if (r.ok) { location.href = '/'; return; }
  const j = await r.json().catch(() => ({}));
  msg.textContent = j.detail || 'Invalid username or password';
});
</script>
</body></html>'''.replace('LOGO_DATA_PLACEHOLDER', LOGO_DATA)


@app.get('/login', response_class=HTMLResponse)
def login_page():
    return LOGIN_HTML


@app.post('/api/login')
def login(body: LoginBody):
    if not ADMIN_PASSWORD:
        return JSONResponse(
            {'detail': 'Admin password not configured on the server (set AT_CANVAS_ADMIN_PASSWORD)'},
            status_code=500,
        )
    user_ok = hmac.compare_digest(body.username.strip().encode(), ADMIN_USER.encode())
    pass_ok = hmac.compare_digest(body.password.encode(), ADMIN_PASSWORD.encode())
    if not (user_ok and pass_ok):
        return JSONResponse({'detail': 'Invalid username or password'}, status_code=401)
    resp = JSONResponse({'ok': True})
    resp.set_cookie(SESSION_COOKIE, _make_session(), max_age=SESSION_TTL, httponly=True, samesite='lax')
    return resp


@app.post('/api/logout')
def logout():
    resp = JSONResponse({'ok': True})
    resp.delete_cookie(SESSION_COOKIE)
    return resp


LOGOUT_WIDGET = (
    '<a href="#" id="atcLogout" style="position:fixed;top:14px;right:18px;z-index:999;'
    'background:#12171d;color:#eef3f8;border:1px solid #27303a;padding:8px 14px;'
    'border-radius:10px;text-decoration:none;font-size:13px;font-weight:600;'
    'font-family:Inter,ui-sans-serif,system-ui,sans-serif">Log out</a>'
    '<script>document.getElementById("atcLogout").addEventListener("click", async e => {'
    'e.preventDefault(); await fetch("/api/logout", {method:"POST"}); location.href = "/login";});</script>'
)

_prev_root_route = next(
    r for r in app.router.routes
    if getattr(r, 'path', None) == '/' and 'GET' in getattr(r, 'methods', set())
)
_prev_root_endpoint = _prev_root_route.endpoint
app.router.routes[:] = [r for r in app.router.routes if r is not _prev_root_route]


@app.get('/', response_class=HTMLResponse)
def admin_v407():
    return _prev_root_endpoint().replace('</body>', LOGOUT_WIDGET + '</body>')
