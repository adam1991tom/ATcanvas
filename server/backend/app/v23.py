import base64
from fastapi.responses import HTMLResponse, Response
from . import v22

app = v22.app
v22.v21.v2.APP_VERSION = '0.2.3'
v22.v21.v2.main.APP_VERSION = '0.2.3'

LOGO_DATA = 'data:image/webp;base64,' + base64.b64encode(v22.LOGO_FILE.read_bytes()).decode('ascii')

# Replace admin, pairing and JS routes with v0.2.3 versions.
app.router.routes[:] = [
    r for r in app.router.routes
    if not (
        (getattr(r, 'path', None) == '/' and 'GET' in getattr(r, 'methods', set()))
        or (getattr(r, 'path', None) == '/pair' and 'GET' in getattr(r, 'methods', set()))
        or (getattr(r, 'path', None) == '/admin-v2.js' and 'GET' in getattr(r, 'methods', set()))
    )
]

@app.get('/', response_class=HTMLResponse)
def admin_v23():
    html = v22.v21.v2.UI_FILE.read_text()
    html = html.replace('__VERSION__', '0.2.3')
    html = html.replace('/assets/atcanvas-logo.webp', LOGO_DATA)
    return html

@app.get('/pair', response_class=HTMLResponse)
def pairing_v23():
    return v22.PAIR_HTML.replace('/assets/atcanvas-logo.webp', LOGO_DATA)

SCREEN_ON_PATCH = r'''

// AT Canvas v0.2.3 screen power controls
function enhanceScreenPower(){
  for(const target of ['#dashDisplays','#displayManager']){
    const root=$(target); if(!root) continue;
    root.querySelectorAll('.display').forEach(row=>{
      const any=row.querySelector('[data-id]'); if(!any) return;
      const id=Number(any.dataset.id);
      const actions=row.querySelector('.actions'); if(!actions) return;
      const off=actions.querySelector('[data-cmd="screen_off"]');
      if(off) off.textContent='Screen Off';
      if(!actions.querySelector('[data-screen-on]')){
        const on=document.createElement('button');
        on.className='secondary';
        on.type='button';
        on.dataset.screenOn=id;
        on.textContent='Screen On';
        on.onclick=async()=>{
          await api(`/api/displays/${id}/command/screen_on`,{method:'POST'});
          on.textContent='Queued ✓';
          setTimeout(()=>on.textContent='Screen On',1800);
        };
        if(off) off.after(on); else actions.prepend(on);
      }
    });
  }
}

// Add Screen On as a scheduling action too.
const _newScheduleClick=$('#newSchedule').onclick;
$('#newSchedule').onclick=()=>modal('New schedule','<label>Name<input name="name" required></label><div class="two"><label>Start<input type="time" name="start" required></label><label>End<input type="time" name="end" required></label></div><label>Action<select name="action"><option value="layout">Switch layout</option><option value="screen_off">Screen off</option><option value="screen_on">Screen on</option><option value="dim">Dim</option></select></label><label>Target<input name="target"></label><button class="action">Save</button>',async f=>{await api('/api/schedules',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({name:f.get('name'),start_time:f.get('start'),end_time:f.get('end'),action:f.get('action'),target:f.get('target')})});loadSchedules()});

setTimeout(enhanceScreenPower,300);
setInterval(enhanceScreenPower,1200);
'''

@app.get('/admin-v2.js')
def admin_v23_js():
    js = v22.v21.v2.JS_FILE.read_text() + v22.v21.ROTATION_PATCH + SCREEN_ON_PATCH
    return Response(js, media_type='application/javascript')
