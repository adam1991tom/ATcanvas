from fastapi import HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from . import v23

app = v23.app
v23.v22.v21.v2.APP_VERSION = '0.2.4'
v23.v22.v21.v2.main.APP_VERSION = '0.2.4'

class DisplaySchedulePatch(BaseModel):
    schedule_id: int | None = None

# Add schedule assignment to existing databases without losing data.
@app.on_event('startup')
def init_v24():
    with v23.v22.v21.v2.db() as c:
        cols = {r['name'] for r in c.execute('PRAGMA table_info(displays)').fetchall()}
        if 'schedule_id' not in cols:
            c.execute('ALTER TABLE displays ADD COLUMN schedule_id INTEGER')

@app.patch('/api/displays/{display_id}/schedule')
def set_display_schedule(display_id: int, body: DisplaySchedulePatch):
    with v23.v22.v21.v2.db() as c:
        if body.schedule_id is not None:
            s = c.execute('SELECT id FROM schedules WHERE id=?', (body.schedule_id,)).fetchone()
            if not s:
                raise HTTPException(404, 'Schedule not found')
        cur = c.execute('UPDATE displays SET schedule_id=? WHERE id=?', (body.schedule_id, display_id))
        if cur.rowcount == 0:
            raise HTTPException(404, 'Display not found')
    return {'ok': True, 'schedule_id': body.schedule_id}

# Replace display list so it includes schedule metadata.
app.router.routes[:] = [
    r for r in app.router.routes
    if not (getattr(r, 'path', None) == '/api/displays' and 'GET' in getattr(r, 'methods', set()))
]

@app.get('/api/displays')
def displays_v24():
    import time
    now = int(time.time())
    with v23.v22.v21.v2.db() as c:
        rows = c.execute('''
            SELECT d.*, s.name AS schedule_name
            FROM displays d
            LEFT JOIN schedules s ON s.id=d.schedule_id
            ORDER BY d.name
        ''').fetchall()
        return [dict(r) | {'online': now - r['last_seen'] < 60} for r in rows]

# Replace heartbeat so display clients receive their assigned schedule too.
app.router.routes[:] = [
    r for r in app.router.routes
    if not (getattr(r, 'path', None) == '/api/display/heartbeat' and 'POST' in getattr(r, 'methods', set()))
]

@app.post('/api/display/heartbeat')
def display_heartbeat_v24(body: v23.v22.v21.v2.main.Heartbeat):
    import time
    now = int(time.time())
    with v23.v22.v21.v2.db() as c:
        row = c.execute('''
            SELECT d.*, s.name AS schedule_name
            FROM displays d
            LEFT JOIN schedules s ON s.id=d.schedule_id
            WHERE d.token=?
        ''', (body.token,)).fetchone()
        if not row:
            raise HTTPException(401, 'Unknown display token')
        c.execute(
            'UPDATE displays SET last_seen=?,client_version=?,resolution=? WHERE token=?',
            (now, body.client_version, body.resolution, body.token),
        )
        return {
            'ok': True,
            'display': row['name'],
            'layout': row['current_layout'],
            'brightness': row['brightness'],
            'orientation': row['orientation'] or 'landscape',
            'schedule_id': row['schedule_id'],
            'schedule_name': row['schedule_name'],
            'command': row['desired_command'],
        }

# Replace the admin route so pairing uses Schedule instead of Room.
app.router.routes[:] = [
    r for r in app.router.routes
    if not (
        (getattr(r, 'path', None) == '/' and 'GET' in getattr(r, 'methods', set()))
        or (getattr(r, 'path', None) == '/admin-v2.js' and 'GET' in getattr(r, 'methods', set()))
    )
]

@app.get('/', response_class=HTMLResponse)
def admin_v24():
    html = v23.v22.v21.v2.UI_FILE.read_text()
    html = html.replace('__VERSION__', '0.2.4')
    html = html.replace('/assets/atcanvas-logo.webp', v23.LOGO_DATA)
    html = html.replace('<input id="pairRoom" placeholder="Room">', '<select id="pairSchedule"><option value="">No schedule</option></select>')
    return html

SCHEDULE_ASSIGNMENT_PATCH = r'''

// AT Canvas v0.2.4 per-display schedule assignment
async function refreshPairScheduleOptions(){
  const select=$('#pairSchedule'); if(!select) return;
  const schedules=await api('/api/schedules');
  const current=select.value;
  select.innerHTML='<option value="">No schedule</option>'+schedules.map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join('');
  select.value=current;
}

// Replace pairing handler so the selected schedule is assigned after claim.
$('#pairForm').onsubmit=async e=>{
  e.preventDefault();
  const m=$('#pairMsg'); m.hidden=false;
  try{
    const claim=await api('/api/pair/claim',{
      method:'POST',headers:{'content-type':'application/json'},
      body:JSON.stringify({code:$('#pairCode').value,name:$('#pairName').value,room:null})
    });
    const scheduleId=$('#pairSchedule')?.value;
    if(scheduleId){
      await api(`/api/displays/${claim.display_id}/schedule`,{
        method:'PATCH',headers:{'content-type':'application/json'},
        body:JSON.stringify({schedule_id:Number(scheduleId)})
      });
    }
    m.textContent='Display paired.';
    e.target.reset();
    await refreshPairScheduleOptions();
    loadDisplays();
  }catch(x){m.textContent=x.message}
};

async function enhanceDisplaySchedules(){
  let displays=[], schedules=[];
  try{[displays,schedules]=await Promise.all([api('/api/displays'),api('/api/schedules')])}catch{return}
  for(const target of ['#dashDisplays','#displayManager']){
    const root=$(target); if(!root) continue;
    root.querySelectorAll('.display').forEach(row=>{
      const any=row.querySelector('[data-id]'); if(!any) return;
      const id=Number(any.dataset.id);
      const d=displays.find(x=>x.id===id); if(!d) return;
      const info=row.querySelector('.muted');
      if(info){
        const base=`${esc(d.resolution||'unknown')} · ${esc(d.current_layout||'Unassigned')}`;
        info.innerHTML=`${base} · Schedule: <strong>${esc(d.schedule_name||'None')}</strong> · ${orientationLabel[d.orientation||'landscape']}`;
      }
      const actions=row.querySelector('.actions'); if(!actions) return;
      let sel=actions.querySelector('[data-schedule-select]');
      if(!sel){
        sel=document.createElement('select');
        sel.dataset.scheduleSelect=id;
        sel.style.width='auto';
        sel.style.minWidth='170px';
        actions.prepend(sel);
        sel.onchange=async()=>{
          await api(`/api/displays/${id}/schedule`,{
            method:'PATCH',headers:{'content-type':'application/json'},
            body:JSON.stringify({schedule_id:sel.value?Number(sel.value):null})
          });
          await loadDisplays();
          enhanceDisplaySchedules();
        };
      }
      sel.innerHTML='<option value="">No schedule</option>'+schedules.map(s=>`<option value="${s.id}">${esc(s.name)}</option>`).join('');
      sel.value=d.schedule_id??'';
    });
  }
}

const _goV24=go;
go=function(p){
  _goV24(p);
  if(p==='dashboard'||p==='displays'){
    setTimeout(()=>{refreshPairScheduleOptions();enhanceDisplaySchedules()},100);
  }
};

setTimeout(()=>{refreshPairScheduleOptions();enhanceDisplaySchedules()},300);
setInterval(enhanceDisplaySchedules,2500);
'''

@app.get('/admin-v2.js')
def admin_v24_js():
    js = (
        v23.v22.v21.v2.JS_FILE.read_text()
        + v23.v22.v21.ROTATION_PATCH
        + v23.SCREEN_ON_PATCH
        + SCHEDULE_ASSIGNMENT_PATCH
    )
    return Response(js, media_type='application/javascript')
