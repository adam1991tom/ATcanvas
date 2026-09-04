import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .. import db as dbmod

router = APIRouter()

GOOGLE_SCOPE = 'https://www.googleapis.com/auth/calendar.readonly'
AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
CALENDAR_API = 'https://www.googleapis.com/calendar/v3'


def _secret(keys):
    with dbmod.get_db() as c:
        marks = ','.join('?' for _ in keys)
        rows = c.execute(f'SELECT key,value FROM secrets WHERE key IN ({marks})', tuple(keys)).fetchall()
    return {r['key']: r['value'] for r in rows}


def _set_secret(values):
    with dbmod.get_db() as c:
        for k, v in values.items():
            c.execute('INSERT INTO secrets(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (k, str(v)))


def _delete_secret(keys):
    with dbmod.get_db() as c:
        c.executemany('DELETE FROM secrets WHERE key=?', [(k,) for k in keys])


def _setting(keys):
    with dbmod.get_db() as c:
        marks = ','.join('?' for _ in keys)
        rows = c.execute(f'SELECT key,value FROM settings WHERE key IN ({marks})', tuple(keys)).fetchall()
    return {r['key']: r['value'] for r in rows}


def _set_setting(values):
    with dbmod.get_db() as c:
        for k, v in values.items():
            c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (k, str(v)))


def _json_request(url, method='GET', data=None, token=None):
    headers = {'User-Agent': 'AT-Canvas/1.0', 'Accept': 'application/json'}
    body = None
    if token:
        headers['Authorization'] = 'Bearer ' + token
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=headers, method=method), timeout=12) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode('utf-8', 'replace'))
            msg = detail.get('error_description') or detail.get('error', {}).get('message') or detail.get('error')
        except Exception:
            msg = f'Google HTTP {exc.code}'
        raise HTTPException(502, str(msg))
    except Exception as exc:
        raise HTTPException(502, str(exc))


def _access_token():
    s = _secret(['google_client_id', 'google_client_secret', 'google_access_token', 'google_refresh_token', 'google_token_expires'])
    token = s.get('google_access_token', '')
    expiry = int(s.get('google_token_expires', '0') or 0)
    if token and expiry > int(time.time()) + 60:
        return token
    refresh = s.get('google_refresh_token', '')
    if not refresh:
        raise HTTPException(401, 'Google Calendar is not connected')
    if not s.get('google_client_id') or not s.get('google_client_secret'):
        raise HTTPException(400, 'Google OAuth credentials are incomplete')
    data = _json_request(TOKEN_URL, 'POST', {
        'client_id': s['google_client_id'], 'client_secret': s['google_client_secret'],
        'refresh_token': refresh, 'grant_type': 'refresh_token',
    })
    token = data.get('access_token')
    if not token:
        raise HTTPException(502, 'Google did not return an access token')
    _set_secret({'google_access_token': token, 'google_token_expires': int(time.time()) + int(data.get('expires_in', 3600))})
    return token


def _selected_ids():
    raw = _setting(['google_selected_calendars']).get('google_selected_calendars', '[]')
    try:
        ids = json.loads(raw)
        return ids if isinstance(ids, list) else []
    except Exception:
        return []


class GoogleConfig(BaseModel):
    client_id: str
    client_secret: str = ''
    redirect_uri: str


class CalendarSelection(BaseModel):
    calendar_ids: list[str]


@router.get('/api/google/status')
def google_status(request: Request):
    s = {**_secret(['google_client_id', 'google_client_secret', 'google_refresh_token']), **_setting(['google_redirect_uri'])}
    redirect = s.get('google_redirect_uri') or str(request.base_url).rstrip('/') + '/api/google/oauth/callback'
    return {
        'configured': bool(s.get('google_client_id') and s.get('google_client_secret')),
        'connected': bool(s.get('google_refresh_token')),
        'client_id': s.get('google_client_id', ''),
        'redirect_uri': redirect,
    }


@router.post('/api/google/config')
def google_config(body: GoogleConfig):
    client_id = body.client_id.strip()
    redirect = body.redirect_uri.strip()
    if not client_id or not redirect:
        raise HTTPException(400, 'Client ID and Redirect URI are required')
    _set_secret({'google_client_id': client_id, **({'google_client_secret': body.client_secret.strip()} if body.client_secret.strip() else {})})
    _set_setting({'google_redirect_uri': redirect})
    return {'saved': True}


@router.get('/api/google/auth/start')
def google_auth_start(request: Request):
    s = {**_secret(['google_client_id', 'google_client_secret']), **_setting(['google_redirect_uri'])}
    if not s.get('google_client_id') or not s.get('google_client_secret'):
        raise HTTPException(400, 'Configure Google Client ID and Client Secret first')
    redirect = s.get('google_redirect_uri') or str(request.base_url).rstrip('/') + '/api/google/oauth/callback'
    state = secrets.token_urlsafe(24)
    _set_secret({'google_oauth_state': state})
    _set_setting({'google_redirect_uri': redirect})
    q = urllib.parse.urlencode({
        'client_id': s['google_client_id'], 'redirect_uri': redirect, 'response_type': 'code',
        'scope': GOOGLE_SCOPE, 'access_type': 'offline', 'prompt': 'consent', 'include_granted_scopes': 'true', 'state': state,
    })
    return {'url': AUTH_URL + '?' + q}


@router.get('/api/google/oauth/callback', response_class=HTMLResponse)
def google_oauth_callback(code: str = '', state: str = '', error: str = ''):
    import html as htmllib
    if error:
        return f'<!doctype html><html><body style="font-family:system-ui;background:#0b0710;color:#fff;padding:40px"><h2>Google connection failed</h2><p>{htmllib.escape(error)}</p></body></html>'
    s = {**_secret(['google_client_id', 'google_client_secret', 'google_oauth_state']), **_setting(['google_redirect_uri'])}
    if not code or not state or state != s.get('google_oauth_state'):
        raise HTTPException(400, 'Invalid Google OAuth state')
    data = _json_request(TOKEN_URL, 'POST', {
        'code': code, 'client_id': s.get('google_client_id', ''), 'client_secret': s.get('google_client_secret', ''),
        'redirect_uri': s.get('google_redirect_uri', ''), 'grant_type': 'authorization_code',
    })
    values = {'google_access_token': data.get('access_token', ''), 'google_token_expires': int(time.time()) + int(data.get('expires_in', 3600))}
    if data.get('refresh_token'):
        values['google_refresh_token'] = data['refresh_token']
    _set_secret(values)
    _delete_secret(['google_oauth_state'])
    return '''<!doctype html><html><body style="font-family:system-ui;background:#0b0710;color:#fff;display:grid;place-items:center;height:100vh;margin:0">
<div style="text-align:center"><h1 style="color:#b100ff">Google Calendar connected ✓</h1><p>You can close this window.</p></div>
<script>if(window.opener){window.opener.postMessage('atcanvas-google-connected','*');setTimeout(()=>window.close(),800)}</script>
</body></html>'''


@router.post('/api/google/disconnect')
def google_disconnect():
    _delete_secret(['google_access_token', 'google_refresh_token', 'google_token_expires', 'google_oauth_state'])
    _set_setting({'google_selected_calendars': '[]'})
    return {'disconnected': True}


@router.get('/api/google/calendars')
def google_calendars():
    token = _access_token()
    selected = set(_selected_ids())
    data = _json_request(CALENDAR_API + '/users/me/calendarList?' + urllib.parse.urlencode({'maxResults': 250}), token=token)
    out = []
    for cal in data.get('items', []):
        out.append({
            'id': cal.get('id'), 'summary': cal.get('summaryOverride') or cal.get('summary') or cal.get('id'),
            'primary': bool(cal.get('primary')), 'selected': cal.get('id') in selected,
            'backgroundColor': cal.get('backgroundColor'),
        })
    return out


@router.patch('/api/google/calendars/selection')
def google_calendar_selection(body: CalendarSelection):
    cleaned = []
    for x in body.calendar_ids:
        x = str(x).strip()
        if x and x not in cleaned:
            cleaned.append(x)
    _set_setting({'google_selected_calendars': json.dumps(cleaned)})
    return {'saved': True, 'calendar_ids': cleaned}


@router.get('/api/widget/calendar-events')
def google_events(days: int = 14, limit: int = 40):
    token = _access_token()
    ids = _selected_ids()
    if not ids:
        return {'events': [], 'selected_calendars': 0}
    days = max(1, min(90, days))
    limit = max(1, min(200, limit))
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    events = []
    with dbmod.get_db() as c:
        colour_rows = c.execute("SELECT value FROM settings WHERE key='google_calendar_colors'").fetchone()
    colours = {}
    try:
        colours = json.loads(colour_rows['value']) if colour_rows else {}
    except Exception:
        colours = {}
    for cid in ids:
        q = urllib.parse.urlencode({
            'timeMin': now.isoformat().replace('+00:00', 'Z'), 'timeMax': end.isoformat().replace('+00:00', 'Z'),
            'singleEvents': 'true', 'orderBy': 'startTime', 'maxResults': limit,
        })
        data = _json_request(CALENDAR_API + '/calendars/' + urllib.parse.quote(cid, safe='') + '/events?' + q, token=token)
        for e in data.get('items', []):
            start = e.get('start', {})
            finish = e.get('end', {})
            events.append({
                'id': e.get('id'), 'summary': e.get('summary') or '(No title)',
                'start': start.get('dateTime') or start.get('date'), 'end': finish.get('dateTime') or finish.get('date'),
                'all_day': 'date' in start, 'location': e.get('location', ''),
                'calendar_id': cid, 'calendar_name': data.get('summary') or cid,
                'color': colours.get(cid, '#6aa7ff'),
            })
    events.sort(key=lambda e: e.get('start') or '')
    return {'events': events[:limit], 'selected_calendars': len(ids)}
