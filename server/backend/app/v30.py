import html, json, time
from datetime import datetime
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from . import v24

app = v24.app
DB = v24.v23.v22.v21.v2.db
BASE = v24.v23.v22.v21.v2
VERSION = '0.3.0'
BASE.APP_VERSION = VERSION
BASE.main.APP_VERSION = VERSION


class LayerEdit(BaseModel):
    name: str | None = None
    x: float | None = None
    y: float | None = None
    w: float | None = None
    h: float | None = None
    visible: bool | None = None
    locked: bool | None = None
    opacity: float | None = None
    z: int | None = None
    config: dict | None = None


class DisplayOutput(BaseModel):
    test_mode: bool = False
    layout_id: int | None = None


class ScheduleCreateV3(BaseModel):
    name: str


class ScheduleBlockCreate(BaseModel):
    start_time: str
    end_time: str
    action: str
    target: str = ''
    days: str = '0,1,2,3,4,5,6'


def _columns(c, table):
    return {r['name'] for r in c.execute(f'PRAGMA table_info({table})').fetchall()}


@app.on_event('startup')
def init_v30():
    with DB() as c:
        dcols = _columns(c, 'displays')
        if 'layout_id' not in dcols:
            c.execute('ALTER TABLE displays ADD COLUMN layout_id INTEGER')
        if 'test_mode' not in dcols:
            c.execute('ALTER TABLE displays ADD COLUMN test_mode INTEGER NOT NULL DEFAULT 1')
        c.execute('''
        CREATE TABLE IF NOT EXISTS schedule_blocks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            action TEXT NOT NULL,
            target TEXT DEFAULT '',
            days TEXT DEFAULT '0,1,2,3,4,5,6',
            created_at INTEGER NOT NULL
        )
        ''')
        # Migrate old schedule rows into a first block once, preserving the names users already made.
        for s in c.execute('SELECT * FROM schedules').fetchall():
            exists = c.execute('SELECT 1 FROM schedule_blocks WHERE schedule_id=? LIMIT 1', (s['id'],)).fetchone()
            if not exists and s['start_time'] and s['end_time']:
                c.execute('INSERT INTO schedule_blocks(schedule_id,start_time,end_time,action,target,created_at) VALUES(?,?,?,?,?,?)',
                          (s['id'], s['start_time'], s['end_time'], s['action'] or 'layout', s['target'] or '', int(time.time())))


# Replace routes that are now fully implemented by v0.3.0.
_REPLACE = {
    ('/api/layers/{layer_id}', 'PATCH'),
    ('/api/displays', 'GET'),
    ('/api/display/heartbeat', 'POST'),
    ('/api/schedules', 'POST'),
    ('/', 'GET'),
    ('/admin-v2.js', 'GET'),
}
app.router.routes[:] = [r for r in app.router.routes if not any(
    getattr(r, 'path', None) == p and m in getattr(r, 'methods', set()) for p, m in _REPLACE
)]


@app.patch('/api/layers/{layer_id}')
def edit_layer_v30(layer_id: int, body: LayerEdit):
    vals = body.model_dump(exclude_none=True)
    for k in ('visible', 'locked'):
        if k in vals:
            vals[k] = 1 if vals[k] else 0
    if 'opacity' in vals:
        vals['opacity'] = max(0.05, min(1.0, float(vals['opacity'])))
    for k in ('x','y','w','h'):
        if k in vals:
            vals[k] = max(0.0, min(100.0, float(vals[k])))
    if 'config' in vals:
        vals['config'] = json.dumps(vals['config'])
    if not vals:
        return {'ok': True}
    with DB() as c:
        cur = c.execute('UPDATE layers SET ' + ','.join(f'{k}=?' for k in vals) + ' WHERE id=?', (*vals.values(), layer_id))
        if cur.rowcount == 0:
            raise HTTPException(404, 'Layer not found')
    return {'ok': True}


def _active_block(c, schedule_id):
    if not schedule_id:
        return None
    now = datetime.now()
    day = str(now.weekday())
    hm = now.strftime('%H:%M')
    blocks = c.execute('SELECT * FROM schedule_blocks WHERE schedule_id=? ORDER BY start_time', (schedule_id,)).fetchall()
    for b in blocks:
        days = (b['days'] or '0,1,2,3,4,5,6').split(',')
        if day not in days:
            continue
        start, end = b['start_time'], b['end_time']
        active = (start <= hm < end) if start <= end else (hm >= start or hm < end)
        if active:
            return dict(b)
    return None


@app.get('/api/displays')
def displays_v30():
    now = int(time.time())
    with DB() as c:
        rows = c.execute('''
        SELECT d.*, s.name schedule_name, l.name layout_name
        FROM displays d
        LEFT JOIN schedules s ON s.id=d.schedule_id
        LEFT JOIN layouts l ON l.id=d.layout_id
        ORDER BY d.name
        ''').fetchall()
        out=[]
        for r in rows:
            x=dict(r)
            x['online'] = now - (r['last_seen'] or 0) < 60
            x['display_url'] = f"/display/{r['token']}"
            x['active_schedule'] = _active_block(c, r['schedule_id'])
            out.append(x)
        return out


@app.patch('/api/displays/{display_id}/output')
def display_output(display_id: int, body: DisplayOutput):
    with DB() as c:
        layout_name = 'Test Screen'
        if not body.test_mode:
            if not body.layout_id:
                raise HTTPException(400, 'Select a layout')
            layout = c.execute('SELECT id,name FROM layouts WHERE id=?', (body.layout_id,)).fetchone()
            if not layout:
                raise HTTPException(404, 'Layout not found')
            layout_name = layout['name']
        cur = c.execute('UPDATE displays SET test_mode=?,layout_id=?,current_layout=?,desired_command=? WHERE id=?',
                        (1 if body.test_mode else 0, None if body.test_mode else body.layout_id, layout_name, 'reload', display_id))
        if cur.rowcount == 0:
            raise HTTPException(404, 'Display not found')
    return {'ok': True, 'test_mode': body.test_mode, 'layout_id': body.layout_id}


@app.post('/api/display/heartbeat')
def heartbeat_v30(body: BASE.main.Heartbeat):
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
        block = _active_block(c, row['schedule_id'])
        return {
            'ok': True,
            'display': row['name'],
            'version': VERSION,
            'display_url': f"/display/{row['token']}",
            'test_mode': bool(row['test_mode']),
            'layout_id': row['layout_id'],
            'layout': row['layout_name'] or row['current_layout'],
            'brightness': row['brightness'],
            'orientation': row['orientation'] or 'landscape',
            'schedule_id': row['schedule_id'],
            'schedule_name': row['schedule_name'],
            'scheduled_action': block,
            'command': row['desired_command'],
        }


@app.post('/api/schedules')
def create_schedule_v30(body: ScheduleCreateV3):
    name = body.name.strip()
    if not name:
        raise HTTPException(400, 'Schedule name is required')
    with DB() as c:
        cur = c.execute("INSERT INTO schedules(name,start_time,end_time,action,target,created_at) VALUES(?,?,?,?,?,?)",
                        (name, '', '', 'profile', '', int(time.time())))
        return {'id': cur.lastrowid}


@app.get('/api/schedules/{schedule_id}/blocks')
def schedule_blocks(schedule_id: int):
    with DB() as c:
        return [dict(r) for r in c.execute('SELECT * FROM schedule_blocks WHERE schedule_id=? ORDER BY start_time', (schedule_id,)).fetchall()]


@app.post('/api/schedules/{schedule_id}/blocks')
def add_schedule_block(schedule_id: int, body: ScheduleBlockCreate):
    allowed={'layout','screen_off','screen_on','dim','normal'}
    if body.action not in allowed:
        raise HTTPException(400, 'Unsupported schedule action')
    with DB() as c:
        if not c.execute('SELECT 1 FROM schedules WHERE id=?',(schedule_id,)).fetchone():
            raise HTTPException(404,'Schedule not found')
        cur=c.execute('INSERT INTO schedule_blocks(schedule_id,start_time,end_time,action,target,days,created_at) VALUES(?,?,?,?,?,?,?)',
                      (schedule_id,body.start_time,body.end_time,body.action,body.target,body.days,int(time.time())))
        return {'id':cur.lastrowid}


@app.delete('/api/schedule-blocks/{block_id}')
def delete_schedule_block(block_id:int):
    with DB() as c:
        c.execute('DELETE FROM schedule_blocks WHERE id=?',(block_id,))
    return {'deleted':True}


@app.get('/api/schedules/{schedule_id}/now')
def schedule_now(schedule_id:int):
    with DB() as c:
        return {'active':_active_block(c,schedule_id)}


TEST_HTML = '''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AT Canvas Test</title><style>
*{box-sizing:border-box}body{margin:0;background:#06040a;color:white;font-family:Inter,system-ui,sans-serif;overflow:hidden}.frame{position:absolute;inset:18px;border:4px solid #b100ff;border-radius:22px;box-shadow:0 0 45px #8b18ff88 inset,0 0 30px #8b18ff55}.top{display:flex;justify-content:space-between;align-items:flex-start;padding:48px 56px}.brand{font-size:42px;font-weight:950;letter-spacing:-.04em}.brand b{color:#bd36ff}.ok{display:inline-flex;align-items:center;gap:10px;border:1px solid #5a3470;background:#160d20;padding:10px 16px;border-radius:999px}.dot{width:12px;height:12px;background:#48e58b;border-radius:50%;box-shadow:0 0 16px #48e58b}.center{position:absolute;inset:20% 5% 18%;display:grid;place-items:center;text-align:center}.title{font-size:clamp(52px,8vw,120px);font-weight:950;line-height:.95}.sub{font-size:clamp(18px,2vw,30px);color:#c9b8d4;margin-top:18px}.bars{display:flex;width:min(900px,82vw);height:36px;margin:30px auto 0;border-radius:12px;overflow:hidden}.bars i{flex:1}.bars i:nth-child(1){background:#fff}.bars i:nth-child(2){background:#ffe04a}.bars i:nth-child(3){background:#39e6df}.bars i:nth-child(4){background:#55e46a}.bars i:nth-child(5){background:#e95cff}.bars i:nth-child(6){background:#ff514d}.bars i:nth-child(7){background:#5168ff}.move{position:absolute;width:38px;height:38px;border-radius:10px;background:#bd36ff;animation:move 6s linear infinite}@keyframes move{0%{left:7%;top:14%}25%{left:90%;top:14%}50%{left:90%;top:85%}75%{left:7%;top:85%}100%{left:7%;top:14%}}.bottom{position:absolute;left:56px;right:56px;bottom:48px;display:flex;justify-content:space-between;color:#b8a6c4;font-size:20px}@media(prefers-reduced-motion:reduce){.move{animation:none;left:7%;top:14%}}</style></head><body><div class="frame"></div><div class="move"></div><div class="top"><div class="brand">AT <b>Canvas</b></div><div class="ok"><span class="dot"></span><span id="server">SERVER CHECKING</span></div></div><div class="center"><div><div class="title">DISPLAY TEST</div><div class="sub">If you can see this page, the AT Canvas browser/render path is working.</div><div class="bars"><i></i><i></i><i></i><i></i><i></i><i></i><i></i></div></div></div><div class="bottom"><div id="res"></div><div id="clock"></div><div>AT Canvas v0.3.0</div></div><script>function tick(){document.getElementById('clock').textContent=new Date().toLocaleString('en-GB',{hour12:false});document.getElementById('res').textContent=`Viewport ${innerWidth} × ${innerHeight} · DPR ${devicePixelRatio}`};tick();setInterval(tick,1000);fetch('/api/health').then(r=>r.ok?r.json():Promise.reject()).then(j=>{document.getElementById('server').textContent='SERVER ONLINE · v'+j.version}).catch(()=>{document.getElementById('server').textContent='SERVER ERROR';document.querySelector('.dot').style.background='#ff514d'})</script></body></html>'''


@app.get('/display/test',response_class=HTMLResponse)
def public_test_screen():
    return TEST_HTML


def _config(layer):
    try:return json.loads(layer['config'] or '{}')
    except:return {}


def render_layout_html(layout,layers):
    parts=[]
    needs_clock=False
    for l in layers:
        if not l['visible']: continue
        cfg=_config(l)
        typ=l['type']; content=''
        if typ=='clock':
            needs_clock=True; content='<div class="liveclock">--:--</div>'
        elif typ=='text': content=html.escape(str(cfg.get('text','Double-click/edit this text')))
        elif typ=='countdown': content=html.escape(str(cfg.get('text','Countdown')))
        elif typ=='calendar': content='Calendar widget'
        elif typ=='photos': content='Photo slideshow'
        elif typ=='weather': content='Weather widget'
        elif typ=='media' and cfg.get('media_id'):
            mid=int(cfg['media_id']); content=f'<img src="/api/media/{mid}/file" style="width:100%;height:100%;object-fit:cover">'
        else: content=html.escape(l['name'])
        style=f"left:{l['x']}%;top:{l['y']}%;width:{l['w']}%;height:{l['h']}%;z-index:{l['z']};opacity:{l['opacity']};color:{cfg.get('color','#ffffff')};background:{cfg.get('background','transparent')};font-size:{int(cfg.get('font_size',32))}px;"
        parts.append(f'<div class="layer {typ}" style="{style}">{content}</div>')
    script="<script>function t(){document.querySelectorAll('.liveclock').forEach(e=>e.textContent=new Date().toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'}))}t();setInterval(t,1000)</script>" if needs_clock else ''
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>*{{box-sizing:border-box}}html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:{layout['background']};font-family:Inter,system-ui,sans-serif}}.stage{{position:relative;width:100%;height:100%}}.layer{{position:absolute;overflow:hidden;display:flex;align-items:center;justify-content:center;white-space:pre-wrap}}.liveclock{{font-size:clamp(44px,7vw,130px);font-weight:800}}</style></head><body><div class="stage">{''.join(parts)}</div>{script}</body></html>'''


@app.get('/display/{token}',response_class=HTMLResponse)
def display_page(token:str):
    with DB() as c:
        d=c.execute('SELECT * FROM displays WHERE token=?',(token,)).fetchone()
        if not d: raise HTTPException(404,'Display not paired')
        if d['test_mode'] or not d['layout_id']:
            return TEST_HTML.replace('DISPLAY TEST', html.escape(d['name'])+' · TEST MODE')
        layout=c.execute('SELECT * FROM layouts WHERE id=?',(d['layout_id'],)).fetchone()
        if not layout: return TEST_HTML.replace('DISPLAY TEST','LAYOUT NOT FOUND')
        layers=c.execute('SELECT * FROM layers WHERE layout_id=? ORDER BY z',(layout['id'],)).fetchall()
        return render_layout_html(layout,layers)


# Admin page: keep the supplied logo, but guarantee a text fallback instead of a broken icon.
@app.get('/',response_class=HTMLResponse)
def admin_v30():
    src=v24.v23.v22.v21.v2.UI_FILE.read_text().replace('__VERSION__',VERSION)
    src=src.replace('/assets/atcanvas-logo.webp', v24.v23.LOGO_DATA)
    src=src.replace('<div class="brand"><img src="'+v24.v23.LOGO_DATA+'" alt="AT Canvas"></div>',
                    '<div class="brand"><img src="'+v24.v23.LOGO_DATA+'" alt="AT Canvas" onerror="this.style.display=\'none\';this.nextElementSibling.style.display=\'block\'"><div style="display:none;font-size:26px;font-weight:900">AT <span style="color:#b100ff">Canvas</span></div></div>')
    src=src.replace('<input id="pairRoom" placeholder="Room">','<select id="pairSchedule"><option value="">No schedule</option></select>')
    return src


ADMIN_PATCH = r'''

// ===== AT Canvas v0.3.0 working-model controls =====
function showToast(msg){let x=document.getElementById('v3toast');if(!x){x=document.createElement('div');x.id='v3toast';Object.assign(x.style,{position:'fixed',right:'22px',bottom:'22px',zIndex:9999,background:'#24112f',border:'1px solid #6d3b83',padding:'12px 16px',borderRadius:'10px',color:'white'});document.body.appendChild(x)}x.textContent=msg;x.style.display='block';clearTimeout(x._t);x._t=setTimeout(()=>x.style.display='none',2400)}

// Add a guaranteed server test-screen preview button to Displays.
const dispTop=document.querySelector('#page-displays .top');
if(dispTop){const b=document.createElement('button');b.className='action';b.textContent='Open Server Test Screen';b.onclick=()=>window.open('/display/test','_blank');dispTop.appendChild(b)}

// Add test/layout output assignment to every display row.
async function enhanceOutputControls(){
  let ds=[],ls=[];try{[ds,ls]=await Promise.all([api('/api/displays'),api('/api/layouts')])}catch{return}
  for(const target of ['#dashDisplays','#displayManager']){const root=$(target);if(!root)continue;root.querySelectorAll('.display').forEach(row=>{const any=row.querySelector('[data-id]');if(!any)return;const id=+any.dataset.id,d=ds.find(x=>x.id===id);if(!d)return;const a=row.querySelector('.actions');if(!a)return;
    let sel=a.querySelector('[data-layout-output]');if(!sel){sel=document.createElement('select');sel.dataset.layoutOutput=id;sel.style.width='auto';sel.innerHTML='<option value="">Choose layout…</option>';a.prepend(sel);sel.onchange=async()=>{if(!sel.value)return;await api(`/api/displays/${id}/output`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({test_mode:false,layout_id:+sel.value})});showToast('Layout sent to display');loadDisplays()}}
    sel.innerHTML='<option value="">Choose layout…</option>'+ls.map(l=>`<option value="${l.id}">${esc(l.name)}</option>`).join('');if(d.layout_id)sel.value=d.layout_id;
    if(!a.querySelector('[data-test-mode]')){const t=document.createElement('button');t.className='secondary';t.dataset.testMode=id;t.textContent='Test Screen';t.onclick=async()=>{await api(`/api/displays/${id}/output`,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({test_mode:true})});showToast('Test screen sent');loadDisplays()};a.appendChild(t)}
    if(!a.querySelector('[data-open-display]')){const o=document.createElement('button');o.className='secondary';o.dataset.openDisplay=id;o.textContent='Open Display';o.onclick=()=>window.open(d.display_url,'_blank');a.appendChild(o)}
  })}}
setTimeout(enhanceOutputControls,300);setInterval(enhanceOutputControls,1800);

// Property editor for the selected layout layer.
const layerCard=$('#layerList')?.parentElement;
if(layerCard){const box=document.createElement('div');box.id='propertyEditor';box.className='section';box.innerHTML='<div class="empty">Select a layer to edit its properties.</div>';layerCard.appendChild(box)}
function cfgOf(l){try{return JSON.parse(l.config||'{}')}catch{return {}}}
function drawProps(){const e=$('#propertyEditor');if(!e)return;const l=layers.find(x=>x.id===selectedLayer);if(!l){e.innerHTML='<div class="empty">Select a layer to edit its properties.</div>';return}const c=cfgOf(l);e.innerHTML=`<h3>Properties</h3><div style="display:grid;gap:8px"><label>Name<input id="pName" value="${esc(l.name)}"></label>${['text','countdown'].includes(l.type)?`<label>Text<textarea id="pText">${esc(c.text||'')}</textarea></label>`:''}<div class="two"><label>Text colour<input id="pColor" type="color" value="${esc(c.color||'#ffffff')}"></label><label>Background<input id="pBg" type="color" value="${esc(c.background&&c.background.startsWith('#')?c.background:'#000000')}"></label></div><div class="two"><label>Font size<input id="pFont" type="number" min="8" max="240" value="${c.font_size||32}"></label><label>Opacity<input id="pOpacity" type="number" min="0.05" max="1" step="0.05" value="${l.opacity}"></label></div><div class="two"><label>X %<input id="pX" type="number" step="0.1" value="${l.x}"></label><label>Y %<input id="pY" type="number" step="0.1" value="${l.y}"></label><label>Width %<input id="pW" type="number" step="0.1" value="${l.w}"></label><label>Height %<input id="pH" type="number" step="0.1" value="${l.h}"></label></div><div class="actions"><button class="action" id="pSave">Save changes</button><button class="secondary" id="pBack">Send backward</button><button class="secondary" id="pFront">Bring forward</button></div></div>`;
  $('#pSave').onclick=async()=>{const nc={...c,color:$('#pColor').value,background:$('#pBg').value,font_size:+$('#pFont').value};if($('#pText'))nc.text=$('#pText').value;await api('/api/layers/'+l.id,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({name:$('#pName').value,x:+$('#pX').value,y:+$('#pY').value,w:+$('#pW').value,h:+$('#pH').value,opacity:+$('#pOpacity').value,config:nc})});showToast('Layer saved');openLayout(currentLayout)};
  $('#pBack').onclick=async()=>{await api('/api/layers/'+l.id,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({z:Math.max(1,l.z-1)})});openLayout(currentLayout)};$('#pFront').onclick=async()=>{await api('/api/layers/'+l.id,{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({z:l.z+1})});openLayout(currentLayout)};
}
const _renderLayersV3=renderLayers;renderLayers=function(){_renderLayersV3();drawProps();$$('.layer').forEach((el,i)=>{el.style.cursor='pointer';el.onclick=e=>{if(e.target.closest('button'))return;const rev=[...layers].reverse();selectedLayer=rev[i]?.id;renderCanvas();renderLayers()}})};
const _renderCanvasV3=renderCanvas;renderCanvas=function(){_renderCanvasV3();document.querySelectorAll('#canvas .widget').forEach((el,i)=>{const vis=layers.filter(x=>x.visible);const l=vis[i];if(!l)return;const c=cfgOf(l);el.style.opacity=l.opacity;el.style.color=c.color||'#fff';el.style.background=c.background||'rgba(35,22,45,.9)';const label=el.querySelector('strong');if(label&&['text','countdown'].includes(l.type)&&c.text)label.textContent=c.text})};

// Rebuild Schedules as profiles containing multiple time blocks.
$('#newSchedule').onclick=()=>modal('New schedule','<label>Schedule name<input name="name" required placeholder="Kitchen Weekday"></label><button class="action">Create schedule</button>',async f=>{await api('/api/schedules',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({name:f.get('name')})});loadSchedulesV3()});
async function loadSchedulesV3(){const all=await api('/api/schedules');const root=$('#scheduleList');root.innerHTML=all.length?'':'<div class="empty">No schedules yet.</div>';for(const s of all){const blocks=await api(`/api/schedules/${s.id}/blocks`);const card=document.createElement('div');card.style.cssText='padding:14px 0;border-bottom:1px solid var(--border)';card.innerHTML=`<div class="top"><div><strong>${esc(s.name)}</strong><div class="muted">${blocks.length} time block${blocks.length===1?'':'s'}</div></div><div class="actions"><button class="secondary" data-add-block="${s.id}">+ Time block</button><button class="danger" data-sdel="${s.id}">Delete schedule</button></div></div><div>${blocks.length?blocks.map(b=>`<div class="row"><div><strong>${esc(b.start_time)}–${esc(b.end_time)}</strong><div class="muted">${esc(b.action)} ${esc(b.target||'')}</div></div><button class="danger" data-bdel="${b.id}">×</button></div>`).join(''):'<div class="muted">No time blocks yet.</div>'}</div>`;root.appendChild(card)}
  $$('[data-add-block]').forEach(b=>b.onclick=()=>modal('Add time block','<div class="two"><label>Start<input type="time" name="start" required></label><label>End<input type="time" name="end" required></label></div><label>Action<select name="action"><option value="layout">Switch layout</option><option value="screen_on">Screen on</option><option value="screen_off">Screen off</option><option value="dim">Dim</option><option value="normal">Normal brightness</option></select></label><label>Target / value<input name="target" placeholder="Layout ID or brightness"></label><button class="action">Add block</button>',async f=>{await api(`/api/schedules/${b.dataset.addBlock}/blocks`,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({start_time:f.get('start'),end_time:f.get('end'),action:f.get('action'),target:f.get('target')||''})});loadSchedulesV3()}));
  $$('[data-bdel]').forEach(b=>b.onclick=async()=>{await api('/api/schedule-blocks/'+b.dataset.bdel,{method:'DELETE'});loadSchedulesV3()});$$('[data-sdel]').forEach(b=>b.onclick=async()=>{if(confirm('Delete schedule and its assignment?')){await api('/api/schedules/'+b.dataset.sdel,{method:'DELETE'});loadSchedulesV3()}})}
const _goV3=go;go=function(p){_goV3(p);if(p==='schedules')setTimeout(loadSchedulesV3,50)};
'''


@app.get('/admin-v2.js')
def admin_js_v30():
    js=(v24.v23.v22.v21.v2.JS_FILE.read_text()+v24.v23.v22.v21.ROTATION_PATCH+v24.v23.SCREEN_ON_PATCH+v24.SCHEDULE_ASSIGNMENT_PATCH+ADMIN_PATCH)
    return Response(js,media_type='application/javascript')
