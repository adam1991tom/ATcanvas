import base64
import html
import secrets
import time
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from . import v33

app = v33.app
DB = v33.DB
BASE = v33.BASE
VERSION = '0.3.5'
BASE.APP_VERSION = VERSION
BASE.main.APP_VERSION = VERSION
LOGO_FILE = BASE.UI_FILE.parent / 'assets' / 'atcanvas-logo.webp'
LOGO_DATA = 'data:image/webp;base64,' + base64.b64encode(LOGO_FILE.read_bytes()).decode('ascii')


class DisplayEndpointCreate(BaseModel):
    name: str
    layout_id: int | None = None
    schedule_id: int | None = None


_REMOVE = {
    ('/api/pair/request', 'POST'), ('/api/pair/claim', 'POST'), ('/api/pair/status/{code}', 'GET'),
    ('/api/display/heartbeat', 'POST'), ('/api/displays', 'GET'), ('/api/updates/status', 'GET'),
    ('/display/{token}', 'GET'), ('/pair', 'GET'), ('/', 'GET'), ('/admin-v2.js', 'GET'),
}
app.router.routes[:] = [r for r in app.router.routes if not any(getattr(r, 'path', None) == p and m in getattr(r, 'methods', set()) for p, m in _REMOVE)]
app.router.routes[:] = [r for r in app.router.routes if not (getattr(r, 'path', None) == '/api/displays/{display_id}/command/{command}' and 'POST' in getattr(r, 'methods', set()))]


@app.on_event('startup')
def cleanup_browser_only_model():
    with DB() as c:
        c.execute('DELETE FROM pairing_codes')
        c.execute("UPDATE displays SET client_version='browser-url', last_seen=0, desired_command=NULL")


def _base(request: Request) -> str:
    return str(request.base_url).rstrip('/')


@app.post('/api/display-endpoints')
def create_display_endpoint(body: DisplayEndpointCreate, request: Request):
    name = body.name.strip()
    if not name: raise HTTPException(400, 'Display name is required')
    with DB() as c:
        layout = None
        if body.layout_id:
            layout = c.execute('SELECT id,name FROM layouts WHERE id=?', (body.layout_id,)).fetchone()
            if not layout: raise HTTPException(404, 'Layout not found')
        if body.schedule_id and not c.execute('SELECT 1 FROM schedules WHERE id=?', (body.schedule_id,)).fetchone(): raise HTTPException(404, 'Schedule not found')
        token = secrets.token_urlsafe(12)
        cur = c.execute('''INSERT INTO displays(name,room,token,resolution,orientation,brightness,current_layout,client_version,last_seen,desired_command,layout_id,test_mode,schedule_id)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''', (name,None,token,'browser','landscape',100,layout['name'] if layout else 'Unassigned','browser-url',0,None,body.layout_id,0 if body.layout_id else 1,body.schedule_id))
        did = cur.lastrowid
    return {'id':did,'name':name,'url':f'{_base(request)}/display/{token}','token':token}


@app.delete('/api/display-endpoints/{display_id}')
def delete_display_endpoint(display_id: int):
    with DB() as c:
        cur=c.execute('DELETE FROM displays WHERE id=?',(display_id,))
        if cur.rowcount==0: raise HTTPException(404,'Display endpoint not found')
    return {'deleted':True}


@app.get('/api/displays')
def browser_displays(request: Request):
    with DB() as c:
        rows=c.execute('''SELECT d.*, s.name schedule_name, l.name layout_name FROM displays d LEFT JOIN schedules s ON s.id=d.schedule_id LEFT JOIN layouts l ON l.id=d.layout_id ORDER BY d.name''').fetchall()
        out=[]
        for row in rows:
            d=dict(row); d['online']=True; d['endpoint_ready']=True; d['display_url']=f'{_base(request)}/display/{row["token"]}'; d['active_schedule']=v33.v32.v31.v30._active_block(c,row['schedule_id']); out.append(d)
        return out


def _reload(page: str, seconds: int=15)->str:
    extra=f'''<style>html,body{{cursor:none}}</style><script>setTimeout(()=>location.reload(),{seconds*1000});</script>'''
    return page.replace('</body>',extra+'</body>')


def _black_page(name:str)->str:
    return _reload(f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(name)}</title><style>html,body{{margin:0;width:100%;height:100%;background:#000;overflow:hidden}}</style></head><body></body></html>''')


@app.get('/display/{token}',response_class=HTMLResponse)
def browser_display(token:str):
    with DB() as c:
        d=c.execute('SELECT * FROM displays WHERE token=?',(token,)).fetchone()
        if not d: raise HTTPException(404,'Display URL not found')
        block=v33.v32.v31.v30._active_block(c,d['schedule_id']); action=block['action'] if block else None
        if action=='screen_off': return _black_page(d['name'])
        layout_id=d['layout_id']
        if block and action=='layout' and block['target']:
            target=str(block['target']).strip(); hit=c.execute('SELECT id FROM layouts WHERE id=?',(int(target),)).fetchone() if target.isdigit() else c.execute('SELECT id FROM layouts WHERE name=?',(target,)).fetchone()
            if hit: layout_id=hit['id']
        if d['test_mode'] or not layout_id: return _reload(v33.v32.v31.v30.TEST_HTML.replace('DISPLAY TEST',html.escape(d['name'])+' · READY'))
        layout=c.execute('SELECT * FROM layouts WHERE id=?',(layout_id,)).fetchone()
        if not layout: return _reload(v33.v32.v31.v30.TEST_HTML.replace('DISPLAY TEST','LAYOUT NOT FOUND'))
        layers=c.execute('SELECT * FROM layers WHERE layout_id=? ORDER BY z',(layout_id,)).fetchall(); page=v33.v32.v31.v30.render_layout_html(layout,layers)
        if action=='dim':
            try: level=max(5,min(95,int(block['target'] or 30)))
            except Exception: level=30
            shade=1-(level/100); page=page.replace('</body>',f'<div style="position:fixed;inset:0;background:rgba(0,0,0,{shade:.2f});z-index:2147483647;pointer-events:none"></div></body>')
        return _reload(page)


@app.get('/api/updates/status')
def browser_update_status():
    import json,urllib.request
    result={'ok':True,'installed':VERSION,'server':{},'release':None}
    try:
        headers={'User-Agent':'AT-Canvas'}; req=urllib.request.Request('https://api.github.com/repos/adam1991tom/ATcanvas/commits/server',headers=headers)
        with urllib.request.urlopen(req,timeout=6) as r: d=json.load(r)
        result['server']={'commit':d['sha'][:7],'message':d['commit']['message'].split('\n')[0]}; req=urllib.request.Request('https://api.github.com/repos/adam1991tom/ATcanvas/releases/latest',headers=headers)
        with urllib.request.urlopen(req,timeout=6) as r: rel=json.load(r)
        result['release']={'tag':rel.get('tag_name'),'name':rel.get('name') or rel.get('tag_name'),'url':rel.get('html_url')}
    except Exception as exc: result['ok']=False; result['error']=str(exc)
    return result


@app.get('/',response_class=HTMLResponse)
def admin_v34():
    src=BASE.UI_FILE.read_text().replace('__VERSION__',VERSION)
    # Embed the real logo so it cannot fail because of a missing /assets static route.
    src=src.replace('/assets/atcanvas-logo.webp',LOGO_DATA)
    src=src.replace('Pair and manage your screens from one place.','Create browser display URLs and manage everything from one place.')
    src=src.replace('<div class="muted">Online</div><div id="mOnline" class="metric">0</div>','<div class="muted">Ready URLs</div><div id="mOnline" class="metric">0</div>')
    old='<div class="section card"><h2>Pair a display</h2><form id="pairForm" class="form"><input id="pairCode" placeholder="6-digit code" required><input id="pairName" placeholder="Display name" required><input id="pairRoom" placeholder="Room"><button class="action">Pair</button></form><div id="pairMsg" class="status" hidden></div></div>'
    new='<div class="section card"><h2>Create display URL</h2><p class="muted">Create an endpoint, then open its URL fullscreen in any modern browser. No display software or pairing code is required.</p><form id="pairForm" class="form"><input id="pairCode" type="hidden" value="000000"><input id="pairName" placeholder="Display name e.g. Kitchen" required><select id="pairSchedule"><option value="">No schedule</option></select><button class="action">Create URL</button></form><div id="pairMsg" class="status" hidden></div></div>'
    src=src.replace(old,new).replace('Monitor and remotely control every paired screen.','Create and manage permanent browser display URLs.').replace('Server and display update status.','AT Canvas server release status.')
    return src


@app.get('/admin-v2.js')
def admin_v34_js():
    base=BASE.UI_FILE.with_name('admin_v33.js').read_text(); patch=BASE.UI_FILE.with_name('admin_v34_patch.js').read_text(); return Response(base+'\n'+patch,media_type='application/javascript')
