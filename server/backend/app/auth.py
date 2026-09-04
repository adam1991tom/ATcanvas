import hashlib
import hmac
import os
import re
import secrets
import time

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from . import db as dbmod
from .deps import templates

ADMIN_USER = os.getenv('AT_CANVAS_ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.getenv('AT_CANVAS_ADMIN_PASSWORD', '')
SESSION_COOKIE = 'atcanvas_session'
SESSION_TTL = 60 * 60 * 24 * 14  # 14 days

router = APIRouter()

# Kiosk display pages have no login of their own - anyone standing in front of the
# screen is trusted to interact with what's shown there (ticking a chore, viewing
# a calendar). Everything under these prefixes stays reachable without a session.
PUBLIC_PREFIXES = ('/display/', '/api/widget/', '/static/')
PUBLIC_EXACT = {'/login', '/api/login', '/api/health'}

_secret_cache = None


def _secret_key():
    global _secret_cache
    if _secret_cache:
        return _secret_cache
    conn = dbmod.get_db()
    try:
        row = conn.execute("SELECT value FROM secrets WHERE key='session_key'").fetchone()
        if row:
            _secret_cache = row['value']
            return _secret_cache
        key = secrets.token_hex(32)
        conn.execute("INSERT INTO secrets(key,value) VALUES('session_key',?)", (key,))
        conn.commit()
        _secret_cache = key
        return key
    finally:
        conn.close()


def _sign(value: str) -> str:
    mac = hmac.new(_secret_key().encode(), value.encode(), hashlib.sha256).hexdigest()
    return f'{value}.{mac}'


def _verify_session(token: str) -> bool:
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


def _make_session() -> str:
    expires = int(time.time()) + SESSION_TTL
    return _sign(f'admin:{expires}')


def is_public(path: str) -> bool:
    if path in PUBLIC_EXACT:
        return True
    return path.startswith(PUBLIC_PREFIXES)


async def require_login(request: Request, call_next):
    path = request.url.path
    if is_public(path) or path == '/api/login':
        response = await call_next(request)
    elif not _verify_session(request.cookies.get(SESSION_COOKIE, '')):
        if path.startswith('/api/'):
            return JSONResponse({'detail': 'Login required'}, status_code=401)
        return RedirectResponse('/login')
    else:
        response = await call_next(request)
    if path in ('/', '/login') or path.startswith('/static/js/admin'):
        response.headers['Cache-Control'] = 'no-store'
    return response


class LoginBody(BaseModel):
    username: str
    password: str


@router.get('/login', response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, 'login.html', {})


@router.post('/api/login')
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


@router.post('/api/logout')
def logout():
    resp = JSONResponse({'ok': True})
    resp.delete_cookie(SESSION_COOKIE)
    return resp
