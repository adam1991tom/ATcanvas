from fastapi import HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import time
from . import v2

app = v2.app
v2.APP_VERSION = '0.2.1'
v2.main.APP_VERSION = '0.2.1'

class OrientationPatch(BaseModel):
    orientation: str

VALID_ORIENTATIONS = {'landscape','portrait','landscape_flipped','portrait_flipped'}

# Replace routes that need v0.2.1 behavior.
app.router.routes[:] = [
    r for r in app.router.routes
    if not (
        (getattr(r, 'path', None) == '/api/display/heartbeat' and 'POST' in getattr(r, 'methods', set()))
        or (getattr(r, 'path', None) == '/admin-v2.js' and 'GET' in getattr(r, 'methods', set()))
    )
]

@app.post('/api/display/heartbeat')
def display_heartbeat_v21(body: v2.main.Heartbeat):
    now = int(time.time())
    with v2.db() as c:
        row = c.execute('SELECT * FROM displays WHERE token=?', (body.token,)).fetchone()
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
            'command': row['desired_command'],
        }

@app.patch('/api/displays/{display_id}/orientation')
def set_display_orientation(display_id: int, body: OrientationPatch):
    if body.orientation not in VALID_ORIENTATIONS:
        raise HTTPException(400, 'Unsupported orientation')
    with v2.db() as c:
        cur = c.execute('UPDATE displays SET orientation=? WHERE id=?', (body.orientation, display_id))
        if cur.rowcount == 0:
            raise HTTPException(404, 'Display not found')
    return {'ok': True, 'orientation': body.orientation}

@app.post('/api/layouts/{layout_id}/rotate')
def rotate_layout(layout_id: int):
    with v2.db() as c:
        row = c.execute('SELECT width,height FROM layouts WHERE id=?', (layout_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Layout not found')
        c.execute(
            'UPDATE layouts SET width=?,height=?,updated_at=? WHERE id=?',
            (row['height'], row['width'], int(time.time()), layout_id),
        )
    return {'ok': True, 'width': row['height'], 'height': row['width']}

ROTATION_PATCH = r'''

// AT Canvas v0.2.1 rotation controls
const _openLayoutV20 = openLayout;
openLayout = async function(id){
  await _openLayoutV20(id);
  const all = await api('/api/layouts');
  const layout = all.find(x => x.id === id);
  if(layout){
    $('#canvas').style.aspectRatio = `${layout.width}/${layout.height}`;
    $('#layoutInfo').textContent = `${layout.width}×${layout.height} · ${layout.width >= layout.height ? 'Landscape' : 'Portrait'}`;
  }
};

const rotateLayoutBtn=document.createElement('button');
rotateLayoutBtn.className='secondary';
rotateLayoutBtn.type='button';
rotateLayoutBtn.textContent='↻ Rotate layout';
rotateLayoutBtn.onclick=async()=>{
  if(!currentLayout) return alert('Select a layout first');
  const r=await api(`/api/layouts/${currentLayout}/rotate`,{method:'POST'});
  $('#canvas').style.aspectRatio=`${r.width}/${r.height}`;
  await loadLayouts();
};
$('#widgetBar').prepend(rotateLayoutBtn);

const orientationCycle={
  landscape:'portrait',
  portrait:'landscape_flipped',
  landscape_flipped:'portrait_flipped',
  portrait_flipped:'landscape'
};
const orientationLabel={
  landscape:'Landscape 0°',
  portrait:'Portrait 90°',
  landscape_flipped:'Landscape 180°',
  portrait_flipped:'Portrait 270°'
};

async function enhanceDisplayRotation(){
  let displays=[];
  try{displays=await api('/api/displays')}catch{return}
  for(const target of ['#dashDisplays','#displayManager']){
    const root=$(target); if(!root) continue;
    root.querySelectorAll('.display').forEach(row=>{
      const any=row.querySelector('[data-id]'); if(!any) return;
      const id=Number(any.dataset.id);
      const d=displays.find(x=>x.id===id); if(!d) return;
      const info=row.querySelector('.muted');
      if(info && !info.dataset.rotationAdded){
        info.textContent += ` · ${orientationLabel[d.orientation||'landscape']}`;
        info.dataset.rotationAdded='1';
      }
      const actions=row.querySelector('.actions');
      if(actions && !actions.querySelector('[data-rotate]')){
        const b=document.createElement('button');
        b.className='secondary'; b.type='button'; b.dataset.rotate=id;
        b.textContent='↻ Rotate 90°';
        b.onclick=async()=>{
          const current=d.orientation||'landscape';
          const next=orientationCycle[current]||'portrait';
          await api(`/api/displays/${id}/orientation`,{
            method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({orientation:next})
          });
          await loadDisplays();
          enhanceDisplayRotation();
        };
        actions.appendChild(b);
      }
    });
  }
}
setTimeout(enhanceDisplayRotation,300);
setInterval(enhanceDisplayRotation,2500);
'''

@app.get('/admin-v2.js')
def admin_v21_js():
    return Response(v2.JS_FILE.read_text() + ROTATION_PATCH, media_type='application/javascript')
