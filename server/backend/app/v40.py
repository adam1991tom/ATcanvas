import html
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from . import v34

app = v34.app
DB = v34.DB
BASE = v34.BASE
VERSION = '0.4.0'
BASE.APP_VERSION = VERSION
BASE.main.APP_VERSION = VERSION

GOOGLE_SCOPE = 'https://www.googleapis.com/auth/calendar.readonly'
AUTH_URL = 'https://accounts.google.com/o/oauth2/v2/auth'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
CALENDAR_API = 'https://www.googleapis.com/calendar/v3'

class GoogleConfig(BaseModel):
    client_id: str
    client_secret: str = ''
    redirect_uri: str
class CalendarSelection(BaseModel):
    calendar_ids: list[str]

def _settings(keys=None):
    with DB() as c:
        if keys:
            marks=','.join('?' for _ in keys); rows=c.execute(f'SELECT key,value FROM settings WHERE key IN ({marks})', tuple(keys)).fetchall()
        else: rows=c.execute('SELECT key,value FROM settings').fetchall()
    return {r['key']:r['value'] for r in rows}
def _set(values):
    with DB() as c:
        for k,v in values.items(): c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,str(v)))
def _delete(keys):
    with DB() as c: c.executemany('DELETE FROM settings WHERE key=?',[(k,) for k in keys])
def _google_error(exc):
    if isinstance(exc, urllib.error.HTTPError):
        try:
            body=exc.read().decode('utf-8','replace'); data=json.loads(body); return str(data.get('error_description') or data.get('error',{}).get('message') or data.get('error') or body)
        except Exception: return f'Google HTTP {exc.code}'
    return str(exc)
def _json_request(url, method='GET', data=None, token=None):
    headers={'User-Agent':'AT-Canvas/0.4','Accept':'application/json'}; body=None
    if token: headers['Authorization']='Bearer '+token
    if data is not None: body=urllib.parse.urlencode(data).encode(); headers['Content-Type']='application/x-www-form-urlencoded'
    try:
        with urllib.request.urlopen(urllib.request.Request(url,data=body,headers=headers,method=method),timeout=12) as r: return json.load(r)
    except Exception as exc: raise HTTPException(502,_google_error(exc))
def _access_token():
    s=_settings(['google_client_id','google_client_secret','google_access_token','google_refresh_token','google_token_expires']); token=s.get('google_access_token',''); expiry=int(s.get('google_token_expires','0') or 0)
    if token and expiry > int(time.time())+60: return token
    refresh=s.get('google_refresh_token','')
    if not refresh: raise HTTPException(401,'Google Calendar is not connected')
    if not s.get('google_client_id') or not s.get('google_client_secret'): raise HTTPException(400,'Google OAuth credentials are incomplete')
    data=_json_request(TOKEN_URL,'POST',{'client_id':s['google_client_id'],'client_secret':s['google_client_secret'],'refresh_token':refresh,'grant_type':'refresh_token'}); token=data.get('access_token')
    if not token: raise HTTPException(502,'Google did not return an access token')
    _set({'google_access_token':token,'google_token_expires':int(time.time())+int(data.get('expires_in',3600))}); return token
def _selected_ids():
    raw=_settings(['google_selected_calendars']).get('google_selected_calendars','[]')
    try:
        ids=json.loads(raw); return ids if isinstance(ids,list) else []
    except Exception: return []

@app.get('/api/google/status')
def google_status(request: Request):
    s=_settings(['google_client_id','google_client_secret','google_refresh_token','google_access_token','google_redirect_uri']); redirect=s.get('google_redirect_uri') or str(request.base_url).rstrip('/')+'/api/google/oauth/callback'
    return {'configured':bool(s.get('google_client_id') and s.get('google_client_secret')),'connected':bool(s.get('google_refresh_token') or s.get('google_access_token')),'client_id':s.get('google_client_id',''),'has_secret':bool(s.get('google_client_secret')),'redirect_uri':redirect}
@app.post('/api/google/config')
def google_config(body: GoogleConfig):
    client_id=body.client_id.strip(); redirect=body.redirect_uri.strip()
    if not client_id or not redirect: raise HTTPException(400,'Client ID and Redirect URI are required')
    values={'google_client_id':client_id,'google_redirect_uri':redirect}
    if body.client_secret.strip(): values['google_client_secret']=body.client_secret.strip()
    _set(values); return {'saved':True}
@app.get('/api/google/auth/start')
def google_auth_start(request: Request):
    s=_settings(['google_client_id','google_client_secret','google_redirect_uri'])
    if not s.get('google_client_id') or not s.get('google_client_secret'): raise HTTPException(400,'Configure Google Client ID and Client Secret first')
    redirect=s.get('google_redirect_uri') or str(request.base_url).rstrip('/')+'/api/google/oauth/callback'; state=secrets.token_urlsafe(24); _set({'google_oauth_state':state,'google_redirect_uri':redirect})
    q=urllib.parse.urlencode({'client_id':s['google_client_id'],'redirect_uri':redirect,'response_type':'code','scope':GOOGLE_SCOPE,'access_type':'offline','prompt':'consent','include_granted_scopes':'true','state':state}); return {'url':AUTH_URL+'?'+q,'redirect_uri':redirect}
@app.get('/api/google/oauth/callback', response_class=HTMLResponse)
def google_oauth_callback(code: str='', state: str='', error: str=''):
    if error: return f'<!doctype html><html><body style="font-family:system-ui;background:#0b0710;color:#fff;padding:40px"><h2>Google connection failed</h2><p>{html.escape(error)}</p></body></html>'
    s=_settings(['google_client_id','google_client_secret','google_redirect_uri','google_oauth_state'])
    if not code or not state or state != s.get('google_oauth_state'): raise HTTPException(400,'Invalid Google OAuth state')
    data=_json_request(TOKEN_URL,'POST',{'code':code,'client_id':s.get('google_client_id',''),'client_secret':s.get('google_client_secret',''),'redirect_uri':s.get('google_redirect_uri',''),'grant_type':'authorization_code'}); values={'google_access_token':data.get('access_token',''),'google_token_expires':int(time.time())+int(data.get('expires_in',3600))}
    if data.get('refresh_token'): values['google_refresh_token']=data['refresh_token']
    _set(values); _delete(['google_oauth_state']); return '<!doctype html><html><body style="font-family:system-ui;background:#0b0710;color:#fff;display:grid;place-items:center;height:100vh;margin:0"><div style="text-align:center"><h1 style="color:#c338ff">Google Calendar connected ✓</h1><p>You can close this window and return to AT Canvas.</p></div><script>if(window.opener){window.opener.postMessage(\'atcanvas-google-connected\',\'*\');setTimeout(()=>window.close(),800)}</script></body></html>'
@app.post('/api/google/disconnect')
def google_disconnect(): _delete(['google_access_token','google_refresh_token','google_token_expires','google_selected_calendars','google_oauth_state']); return {'disconnected':True}
@app.get('/api/google/calendars')
def google_calendars():
    token=_access_token(); selected=set(_selected_ids()); data=_json_request(CALENDAR_API+'/users/me/calendarList?'+urllib.parse.urlencode({'maxResults':250}),token=token); out=[]
    for c in data.get('items',[]): out.append({'id':c.get('id'),'summary':c.get('summaryOverride') or c.get('summary') or c.get('id'),'primary':bool(c.get('primary')),'selected':c.get('id') in selected,'backgroundColor':c.get('backgroundColor'),'accessRole':c.get('accessRole')})
    return out
@app.patch('/api/google/calendars/selection')
def google_calendar_selection(body: CalendarSelection):
    cleaned=[]
    for x in body.calendar_ids:
        x=str(x).strip()
        if x and x not in cleaned: cleaned.append(x)
    _set({'google_selected_calendars':json.dumps(cleaned)}); return {'saved':True,'calendar_ids':cleaned}
@app.get('/api/google/events')
def google_events(days: int=14, limit: int=20):
    token=_access_token(); ids=_selected_ids()
    if not ids: return {'events':[],'selected_calendars':0}
    days=max(1,min(90,days)); limit=max(1,min(100,limit)); now=datetime.now(timezone.utc); end=now+timedelta(days=days); events=[]
    for cid in ids:
        q=urllib.parse.urlencode({'timeMin':now.isoformat().replace('+00:00','Z'),'timeMax':end.isoformat().replace('+00:00','Z'),'singleEvents':'true','orderBy':'startTime','maxResults':limit}); url=CALENDAR_API+'/calendars/'+urllib.parse.quote(cid,safe='')+'/events?'+q; data=_json_request(url,token=token)
        for e in data.get('items',[]):
            start=e.get('start',{}); finish=e.get('end',{}); events.append({'id':e.get('id'),'summary':e.get('summary') or '(No title)','start':start.get('dateTime') or start.get('date'),'end':finish.get('dateTime') or finish.get('date'),'all_day':'date' in start,'location':e.get('location',''),'calendar_id':cid,'calendar_name':data.get('summary') or cid})
    events.sort(key=lambda e:e.get('start') or ''); return {'events':events[:limit],'selected_calendars':len(ids)}

_ORIGINAL_RENDER=v34.v33.v32.v31.v30.render_layout_html
def _google_render(layout,layers):
    page=_ORIGINAL_RENDER(layout,layers)
    if 'Calendar widget' not in page: return page
    widget='<div class="at-gcal" style="width:100%;height:100%;padding:18px;overflow:hidden;text-align:left"><div style="font-weight:800;margin-bottom:10px">Upcoming</div><div class="at-gcal-events" style="display:grid;gap:8px;font-size:.62em">Loading calendar…</div></div>'; page=page.replace('Calendar widget',widget)
    script='''<script>(async()=>{try{const r=await fetch('/api/google/events?days=14&limit=8');const j=await r.json();document.querySelectorAll('.at-gcal-events').forEach(root=>{if(!r.ok){root.textContent=j.detail||'Google Calendar error';return}if(!j.events.length){root.textContent='No upcoming events';return}root.innerHTML=j.events.map(e=>{const d=e.all_day?new Date(e.start+'T00:00:00'):new Date(e.start);const when=e.all_day?d.toLocaleDateString('en-GB',{weekday:'short',day:'numeric',month:'short'}):d.toLocaleString('en-GB',{weekday:'short',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'});return `<div style="padding:8px 0;border-bottom:1px solid rgba(255,255,255,.15)"><div style="font-weight:700">${String(e.summary||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}</div><div style="opacity:.7;font-size:.8em">${when} · ${String(e.calendar_name||'')}</div></div>`}).join('')})}catch(e){document.querySelectorAll('.at-gcal-events').forEach(x=>x.textContent='Calendar unavailable')}})();</script>'''; return page.replace('</body>',script+'</body>')
v34.v33.v32.v31.v30.render_layout_html=_google_render

app.router.routes[:]=[r for r in app.router.routes if not ((getattr(r,'path',None)=='/' and 'GET' in getattr(r,'methods',set())) or (getattr(r,'path',None)=='/admin-v2.js' and 'GET' in getattr(r,'methods',set())))]
def _replace_section(src, section_id, replacement):
    start=src.find(f'<section class="page" id="{section_id}">')
    if start<0: return src
    end=src.find('</section>',start)
    if end<0: return src
    return src[:start]+replacement+src[end+10:]
@app.get('/',response_class=HTMLResponse)
def admin_v40():
    src=v34.admin_v34(); calendar='''<section class="page" id="page-calendars"><div class="top"><div><h1>Calendars</h1><div class="muted">Connect Google Calendar and choose exactly which calendars appear on AT Canvas.</div></div><div class="actions"><button class="secondary" id="googleSetup">Google Settings</button><button class="action" id="googleConnect">Connect Google</button><button class="danger" id="googleDisconnect" hidden>Disconnect</button></div></div><div class="two"><div class="card"><h2>Google Calendar</h2><div id="googleStatus" class="status">Checking…</div><div class="top" style="margin-top:18px"><div><h3 style="margin:0">Calendars</h3><div class="muted">Tick every calendar you want available to Calendar widgets.</div></div><button class="action" id="googleSaveCalendars" hidden>Save Calendars</button></div><div id="googleCalendarList"><div class="empty">Connect Google to load calendars.</div></div></div><div class="card"><div class="top"><div><h2 style="margin:0">Upcoming events</h2><div class="muted">Preview of the calendars selected for your displays.</div></div><button class="secondary" id="googleRefreshEvents">Refresh</button></div><div id="googleEventPreview"><div class="empty">No Google events yet.</div></div></div></div></section>'''; return _replace_section(src,'page-calendars',calendar)
@app.get('/admin-v2.js')
def admin_v40_js():
    base=v34.admin_v34_js().body.decode('utf-8'); google=BASE.UI_FILE.with_name('google_patch.js').read_text(); designer=BASE.UI_FILE.with_name('designer_v2_patch.js').read_text(); return Response(base+'\n'+google+'\n'+designer,media_type='application/javascript')
