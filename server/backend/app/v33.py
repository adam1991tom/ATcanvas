import html, json, time, urllib.request
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from . import v32

app = v32.app
BASE = v32.BASE
DB = v32.v31.v30.DB
VERSION = '0.3.3'
BASE.APP_VERSION = VERSION
BASE.main.APP_VERSION = VERSION


class LayoutPatch(BaseModel):
    name: str | None = None
    width: int | None = None
    height: int | None = None
    background: str | None = None


class EventPatch(BaseModel):
    name: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    notes: str | None = None


class ScheduleBlockPatch(BaseModel):
    start_time: str | None = None
    end_time: str | None = None
    action: str | None = None
    target: str | None = None
    days: str | None = None


@app.patch('/api/layouts/{layout_id}')
def patch_layout(layout_id: int, body: LayoutPatch):
    vals = body.model_dump(exclude_none=True)
    if 'name' in vals:
        vals['name'] = vals['name'].strip()
        if not vals['name']:
            raise HTTPException(400, 'Layout name is required')
    if 'width' in vals:
        vals['width'] = max(320, min(7680, int(vals['width'])))
    if 'height' in vals:
        vals['height'] = max(240, min(4320, int(vals['height'])))
    vals['updated_at'] = int(time.time())
    with DB() as c:
        try:
            cur = c.execute('UPDATE layouts SET ' + ','.join(f'{k}=?' for k in vals) + ' WHERE id=?', (*vals.values(), layout_id))
        except Exception as exc:
            if 'UNIQUE' in str(exc).upper():
                raise HTTPException(400, 'Layout name already exists')
            raise
        if cur.rowcount == 0:
            raise HTTPException(404, 'Layout not found')
    return {'ok': True}


@app.post('/api/layouts/{layout_id}/duplicate')
def duplicate_layout(layout_id: int):
    now = int(time.time())
    with DB() as c:
        layout = c.execute('SELECT * FROM layouts WHERE id=?', (layout_id,)).fetchone()
        if not layout:
            raise HTTPException(404, 'Layout not found')
        base_name = layout['name'] + ' Copy'
        name = base_name
        n = 2
        while c.execute('SELECT 1 FROM layouts WHERE name=?', (name,)).fetchone():
            name = f'{base_name} {n}'
            n += 1
        cur = c.execute('INSERT INTO layouts(name,width,height,background,created_at,updated_at) VALUES(?,?,?,?,?,?)',
                        (name, layout['width'], layout['height'], layout['background'], now, now))
        new_id = cur.lastrowid
        for layer in c.execute('SELECT * FROM layers WHERE layout_id=? ORDER BY z', (layout_id,)).fetchall():
            c.execute('''INSERT INTO layers(layout_id,name,type,x,y,w,h,z,visible,locked,opacity,config)
                         VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                      (new_id, layer['name'], layer['type'], layer['x'], layer['y'], layer['w'], layer['h'], layer['z'], layer['visible'], layer['locked'], layer['opacity'], layer['config']))
    return {'id': new_id, 'name': name}


@app.post('/api/layers/{layer_id}/duplicate')
def duplicate_layer(layer_id: int):
    with DB() as c:
        layer = c.execute('SELECT * FROM layers WHERE id=?', (layer_id,)).fetchone()
        if not layer:
            raise HTTPException(404, 'Layer not found')
        z = c.execute('SELECT COALESCE(MAX(z),0)+1 n FROM layers WHERE layout_id=?', (layer['layout_id'],)).fetchone()['n']
        cur = c.execute('''INSERT INTO layers(layout_id,name,type,x,y,w,h,z,visible,locked,opacity,config)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (layer['layout_id'], layer['name'] + ' Copy', layer['type'], min(95, layer['x']+2), min(95, layer['y']+2), layer['w'], layer['h'], z, layer['visible'], layer['locked'], layer['opacity'], layer['config']))
    return {'id': cur.lastrowid}


@app.patch('/api/events/{event_id}')
def patch_event(event_id: int, body: EventPatch):
    vals = body.model_dump(exclude_none=True)
    if not vals:
        return {'ok': True}
    if 'name' in vals and not vals['name'].strip():
        raise HTTPException(400, 'Event name is required')
    with DB() as c:
        cur = c.execute('UPDATE events SET ' + ','.join(f'{k}=?' for k in vals) + ' WHERE id=?', (*vals.values(), event_id))
        if cur.rowcount == 0:
            raise HTTPException(404, 'Event not found')
    return {'ok': True}


@app.patch('/api/schedule-blocks/{block_id}')
def patch_schedule_block(block_id: int, body: ScheduleBlockPatch):
    vals = body.model_dump(exclude_none=True)
    if 'action' in vals and vals['action'] not in {'layout','screen_off','screen_on','dim','normal'}:
        raise HTTPException(400, 'Unsupported schedule action')
    if not vals:
        return {'ok': True}
    with DB() as c:
        cur = c.execute('UPDATE schedule_blocks SET ' + ','.join(f'{k}=?' for k in vals) + ' WHERE id=?', (*vals.values(), block_id))
        if cur.rowcount == 0:
            raise HTTPException(404, 'Schedule block not found')
    return {'ok': True}


# Replace schedule deletion so blocks are removed too.
app.router.routes[:] = [r for r in app.router.routes if not (getattr(r, 'path', None) == '/api/schedules/{schedule_id}' and 'DELETE' in getattr(r, 'methods', set()))]

@app.delete('/api/schedules/{schedule_id}')
def delete_schedule_v33(schedule_id: int):
    with DB() as c:
        c.execute('UPDATE displays SET schedule_id=NULL WHERE schedule_id=?', (schedule_id,))
        c.execute('DELETE FROM schedule_blocks WHERE schedule_id=?', (schedule_id,))
        c.execute('DELETE FROM schedules WHERE id=?', (schedule_id,))
    return {'deleted': True}


@app.get('/api/updates/status')
def update_status_v33():
    headers = {'User-Agent': 'AT-Canvas'}
    result = {'ok': True, 'installed': VERSION, 'server': {}, 'screen': {}, 'release': None}
    try:
        for branch in ('server', 'screen'):
            req = urllib.request.Request(f'https://api.github.com/repos/adam1991tom/ATcanvas/commits/{branch}', headers=headers)
            with urllib.request.urlopen(req, timeout=6) as r:
                d = json.load(r)
            result[branch] = {'commit': d['sha'][:7], 'message': d['commit']['message'].split('\n')[0]}
        req = urllib.request.Request('https://api.github.com/repos/adam1991tom/ATcanvas/releases/latest', headers=headers)
        with urllib.request.urlopen(req, timeout=6) as r:
            rel = json.load(r)
        result['release'] = {'tag': rel.get('tag_name'), 'name': rel.get('name') or rel.get('tag_name'), 'url': rel.get('html_url')}
    except Exception as exc:
        result['ok'] = False
        result['error'] = str(exc)
    return result


# Schedules now actively affect the display heartbeat instead of being informational only.
app.router.routes[:] = [r for r in app.router.routes if not (getattr(r, 'path', None) == '/api/display/heartbeat' and 'POST' in getattr(r, 'methods', set()))]

@app.post('/api/display/heartbeat')
def heartbeat_v33(body: BASE.main.Heartbeat, request: Request):
    now = int(time.time())
    with DB() as c:
        row = c.execute('''SELECT d.*,s.name schedule_name,l.name layout_name
                           FROM displays d
                           LEFT JOIN schedules s ON s.id=d.schedule_id
                           LEFT JOIN layouts l ON l.id=d.layout_id
                           WHERE d.token=?''', (body.token,)).fetchone()
        if not row:
            raise HTTPException(401, 'Unknown display token')
        c.execute('UPDATE displays SET last_seen=?,client_version=?,resolution=? WHERE token=?',
                  (now, body.client_version, body.resolution, body.token))
        block = v32.v31.v30._active_block(c, row['schedule_id'])
        command = row['desired_command']
        brightness = row['brightness']
        layout_id = row['layout_id']
        layout_name = row['layout_name'] or row['current_layout']
        test_mode = bool(row['test_mode'])

        if block:
            action = block['action']
            target = block.get('target') or ''
            if action == 'layout' and target:
                try:
                    target_id = int(target)
                except ValueError:
                    target_id = 0
                layout = c.execute('SELECT id,name FROM layouts WHERE id=?', (target_id,)).fetchone()
                if layout:
                    if layout_id != target_id or test_mode:
                        c.execute('UPDATE displays SET layout_id=?,current_layout=?,test_mode=0 WHERE id=?',
                                  (target_id, layout['name'], row['id']))
                        command = 'reload'
                    layout_id = target_id
                    layout_name = layout['name']
                    test_mode = False
            elif action in {'screen_off', 'screen_on'}:
                command = action
            elif action == 'dim':
                try:
                    brightness = max(10, min(100, int(target or 25)))
                except ValueError:
                    brightness = 25
            elif action == 'normal':
                brightness = 100

        base = str(request.base_url).rstrip('/')
        renderer_url = f"{base}/display/{row['token']}"
        return {
            'ok': True,
            'display': row['name'],
            'version': VERSION,
            'renderer_url': renderer_url,
            'render_url': renderer_url,
            'display_url': renderer_url,
            'url': renderer_url,
            'test_mode': test_mode,
            'layout_id': layout_id,
            'layout': layout_name,
            'brightness': brightness,
            'orientation': row['orientation'] or 'landscape',
            'schedule_id': row['schedule_id'],
            'schedule_name': row['schedule_name'],
            'scheduled_action': block,
            'command': command,
        }


@app.get('/layout/{layout_id}/preview', response_class=HTMLResponse)
def layout_preview_v33(layout_id: int):
    with DB() as c:
        layout = c.execute('SELECT * FROM layouts WHERE id=?', (layout_id,)).fetchone()
        if not layout:
            raise HTTPException(404, 'Layout not found')
        layers = c.execute('SELECT * FROM layers WHERE layout_id=? ORDER BY z', (layout_id,)).fetchall()
    page = v32.v31.v30.render_layout_html(layout, layers)
    return page.replace('</body>', '<script>setInterval(()=>location.reload(),5000)</script></body>')


# Live display pages refresh periodically so editor changes become visible during testing.
app.router.routes[:] = [r for r in app.router.routes if not (getattr(r, 'path', None) == '/display/{token}' and 'GET' in getattr(r, 'methods', set()))]

@app.get('/display/{token}', response_class=HTMLResponse)
def display_page_v33(token: str):
    with DB() as c:
        d = c.execute('SELECT * FROM displays WHERE token=?', (token,)).fetchone()
        if not d:
            raise HTTPException(404, 'Display not paired')
        if d['test_mode'] or not d['layout_id']:
            page = v32.v31.v30.TEST_HTML.replace('DISPLAY TEST', html.escape(d['name']) + ' · TEST MODE')
            return page.replace('AT Canvas v0.3.0', f'AT Canvas v{VERSION}')
        layout = c.execute('SELECT * FROM layouts WHERE id=?', (d['layout_id'],)).fetchone()
        if not layout:
            return v32.v31.v30.TEST_HTML.replace('DISPLAY TEST', 'LAYOUT NOT FOUND')
        layers = c.execute('SELECT * FROM layers WHERE layout_id=? ORDER BY z', (layout['id'],)).fetchall()
    page = v32.v31.v30.render_layout_html(layout, layers)
    return page.replace('</body>', '<script>setInterval(()=>location.reload(),5000)</script></body>')


# Replace admin routes entirely with the clean v0.3.3 controller.
app.router.routes[:] = [
    r for r in app.router.routes
    if not (
        (getattr(r, 'path', None) == '/' and 'GET' in getattr(r, 'methods', set()))
        or (getattr(r, 'path', None) == '/admin-v2.js' and 'GET' in getattr(r, 'methods', set()))
    )
]

@app.get('/', response_class=HTMLResponse)
def admin_v33():
    src = BASE.UI_FILE.read_text().replace('__VERSION__', VERSION)
    # Use a reliable text mark until the full static branding asset is rebuilt.
    src = src.replace('<div class="brand"><img src="/assets/atcanvas-logo.webp" alt="AT Canvas"></div>', '<div class="brand"><div style="font-size:28px;font-weight:950;letter-spacing:-.04em">AT <span style="color:#c338ff">Canvas</span></div></div>')
    src = src.replace('<input id="pairRoom" placeholder="Room">', '<select id="pairSchedule"><option value="">No schedule</option></select>')
    return src

@app.get('/admin-v2.js')
def admin_v33_js():
    js = BASE.UI_FILE.with_name('admin_v33.js').read_text()
    return Response(js, media_type='application/javascript')
