from fastapi import HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from . import v408, v40

app = v408.app
DB = v408.DB
BASE = v408.BASE
VERSION = '0.5.0'
BASE.APP_VERSION = VERSION
BASE.main.APP_VERSION = VERSION

ALLOWED_EFFECTS = {'none', 'snow', 'rain', 'halloween', 'confetti', 'hearts', 'stars'}


@app.on_event('startup')
def init_v409():
    with DB() as c:
        cols = {r['name'] for r in c.execute('PRAGMA table_info(events)').fetchall()}
        if 'effect' not in cols:
            c.execute("ALTER TABLE events ADD COLUMN effect TEXT DEFAULT 'none'")


class EventEffectPatch(BaseModel):
    effect: str


@app.patch('/api/events/{event_id}/effect')
def set_event_effect(event_id: int, body: EventEffectPatch):
    effect = body.effect if body.effect in ALLOWED_EFFECTS else 'none'
    with DB() as c:
        cur = c.execute('UPDATE events SET effect=? WHERE id=?', (effect, event_id))
        if cur.rowcount == 0:
            raise HTTPException(404, 'Event not found')
    return {'effect': effect}


@app.get('/api/events/active')
def active_events():
    with DB() as c:
        rows = c.execute('''
            SELECT * FROM events
            WHERE effect IS NOT NULL AND effect != '' AND effect != 'none'
              AND start_date IS NOT NULL AND start_date != ''
              AND date('now','localtime') >= date(start_date)
              AND date('now','localtime') <= date(COALESCE(NULLIF(end_date,''), start_date))
            ORDER BY id
        ''').fetchall()
    return [dict(r) for r in rows]


def _cfg(l):
    import json
    try:
        return json.loads(l['config'] or '{}')
    except Exception:
        return {}


_PREV_RENDER = v40.v34.v33.v32.v31.v30.render_layout_html

_FX_SCRIPT_TEMPLATE = '''<script>
(function(){
  const EFFECT_LAYER_ID = %(layer_id)s;
  function wmoToEffect(code, isDay){
    code = Number(code);
    if ([95,96,99].includes(code)) return 'thunder';
    if ([71,73,75,77,85,86].includes(code)) return 'snow';
    if ([51,53,55,56,57,61,63,65,66,67,80,81,82].includes(code)) return 'rain';
    if ([45,48].includes(code)) return 'fog';
    if (code===0) return isDay ? 'none' : 'stars';
    return 'none';
  }
  let canvas, ctx, particles=[], raf=null, currentType='none', flashT=0;
  function ensureCanvas(){
    if (canvas) return;
    canvas=document.createElement('canvas');
    canvas.id='at-fx-canvas';
    canvas.style.cssText='position:fixed;inset:0;z-index:2147483000;pointer-events:none';
    document.body.appendChild(canvas);
    ctx=canvas.getContext('2d');
    resize(); addEventListener('resize',resize);
  }
  function resize(){ if(!canvas) return; canvas.width=innerWidth; canvas.height=innerHeight; }
  function isRainLike(t){ return t==='rain' || t==='thunder'; }
  function spawn(type){
    const w=innerWidth,h=innerHeight;
    if (type==='snow') return {x:Math.random()*w,y:-10,vy:.5+Math.random()*1.2,vx:(Math.random()-.5)*.6,r:2+Math.random()*3,a:.5+Math.random()*.5};
    if (isRainLike(type)) return {x:Math.random()*w,y:-10,vy:6+Math.random()*4,vx:-1,len:14+Math.random()*10,a:.35+Math.random()*.3};
    if (type==='stars') return {x:Math.random()*w,y:Math.random()*h*.7,r:.5+Math.random()*1.5,a:Math.random(),tw:.02+Math.random()*.03,phase:Math.random()*6.28};
    if (type==='fog') return {x:Math.random()*w,y:Math.random()*h,vx:.15+Math.random()*.2,r:80+Math.random()*160,a:.03+Math.random()*.05};
    if (type==='confetti') return {x:Math.random()*w,y:-10,vy:2+Math.random()*2,vx:(Math.random()-.5)*2,rot:Math.random()*6.28,vr:(Math.random()-.5)*.2,color:['#ff5e7e','#ffd166','#06d6a0','#4d96ff','#c77dff'][Math.floor(Math.random()*5)],size:5+Math.random()*4};
    if (type==='hearts') return {x:Math.random()*w,y:h+10,vy:-(.6+Math.random()*1),vx:(Math.random()-.5)*.5,size:14+Math.random()*14,a:.5+Math.random()*.5};
    if (type==='halloween') return {x:Math.random()*w,y:h*.12+Math.random()*h*.5,vx:(Math.random()<.5?-1:1)*(.6+Math.random()*.8),vy:(Math.random()-.5)*.2,size:16+Math.random()*10};
    return null;
  }
  function draw(type){
    ctx.clearRect(0,0,canvas.width,canvas.height);
    particles.forEach(p=>{
      if (type==='snow'){ ctx.globalAlpha=p.a; ctx.fillStyle='#fff'; ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,6.28); ctx.fill(); }
      else if (isRainLike(type)){ ctx.globalAlpha=p.a; ctx.strokeStyle='#9fc4ff'; ctx.lineWidth=1.4; ctx.beginPath(); ctx.moveTo(p.x,p.y); ctx.lineTo(p.x+p.vx*2,p.y+p.len); ctx.stroke(); }
      else if (type==='stars'){ ctx.globalAlpha=Math.abs(Math.sin(p.phase)); ctx.fillStyle='#fff'; ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,6.28); ctx.fill(); }
      else if (type==='fog'){ ctx.globalAlpha=p.a; ctx.fillStyle='#cfd8e3'; ctx.beginPath(); ctx.ellipse(p.x,p.y,p.r,p.r*.4,0,0,6.28); ctx.fill(); }
      else if (type==='confetti'){ ctx.globalAlpha=.9; ctx.save(); ctx.translate(p.x,p.y); ctx.rotate(p.rot); ctx.fillStyle=p.color; ctx.fillRect(-p.size/2,-p.size/2,p.size,p.size*.5); ctx.restore(); }
      else if (type==='hearts'){ ctx.globalAlpha=p.a; ctx.font=p.size+'px sans-serif'; ctx.fillText('\\u2764\\uFE0F',p.x,p.y); }
      else if (type==='halloween'){ ctx.globalAlpha=.85; ctx.font=p.size+'px sans-serif'; ctx.fillText('\\u{1F987}',p.x,p.y); }
    });
    if (type==='thunder' && flashT>0){ ctx.globalAlpha=Math.min(.55,flashT/6); ctx.fillStyle='#fff'; ctx.fillRect(0,0,canvas.width,canvas.height); flashT--; }
    ctx.globalAlpha=1;
  }
  function step(type){
    const w=innerWidth,h=innerHeight;
    particles.forEach(p=>{
      if (type==='snow'){ p.y+=p.vy; p.x+=p.vx; if(p.y>h+10){p.y=-10;p.x=Math.random()*w;} }
      else if (isRainLike(type)){ p.y+=p.vy; p.x+=p.vx; if(p.y>h+10){p.y=-10;p.x=Math.random()*w;} }
      else if (type==='stars'){ p.phase+=p.tw; }
      else if (type==='fog'){ p.x+=p.vx; if(p.x-p.r>w) p.x=-p.r; }
      else if (type==='confetti'){ p.y+=p.vy; p.x+=p.vx; p.rot+=p.vr; if(p.y>h+10){ Object.assign(p, spawn('confetti')); p.y=-10; } }
      else if (type==='hearts'){ p.y+=p.vy; p.x+=p.vx; if(p.y<-20){ Object.assign(p, spawn('hearts')); p.y=h+10; } }
      else if (type==='halloween'){ p.x+=p.vx; if(p.x<-30||p.x>w+30){ Object.assign(p, spawn('halloween')); p.x = p.vx>0?-30:w+30; } }
    });
    if (type==='thunder' && Math.random()<0.006) flashT=6;
    draw(type);
    raf=requestAnimationFrame(()=>step(type));
  }
  const COUNTS={snow:80,rain:120,thunder:110,stars:120,fog:6,confetti:100,hearts:24,halloween:8};
  function start(type){
    if (!type || type==='none'){ stop(); return; }
    if (type===currentType) return;
    stop();
    currentType=type;
    ensureCanvas();
    particles=Array.from({length:COUNTS[type]||40},()=>spawn(type)).filter(Boolean);
    step(type);
  }
  function stop(){
    if (raf) cancelAnimationFrame(raf);
    raf=null; currentType='none'; particles=[];
    if (canvas && ctx) ctx.clearRect(0,0,canvas.width,canvas.height);
  }
  async function decide(){
    try{
      const er = await fetch('/api/events/active');
      const events = await er.json();
      if (Array.isArray(events) && events.length && events[0].effect && events[0].effect!=='none'){ start(events[0].effect); return; }
    }catch(e){}
    if (EFFECT_LAYER_ID){
      try{
        const wr = await fetch('/api/widget/weather-v2/'+EFFECT_LAYER_ID);
        const wj = await wr.json();
        if (wr.ok){ start(wmoToEffect(wj.current && wj.current.weather_code, wj.current ? wj.current.is_day!==0 : true)); return; }
      }catch(e){}
    }
    stop();
  }
  decide();
  setInterval(decide, 10*60*1000);
})();
</script>'''


def render_v409(layout, layers):
    page = _PREV_RENDER(layout, layers)
    effect_layer = next((l for l in layers if l['type'] == 'weather' and _cfg(l).get('fullscreen_effect')), None)
    script = _FX_SCRIPT_TEMPLATE % {'layer_id': (effect_layer['id'] if effect_layer else 'null')}
    return page.replace('</body>', script + '</body>')


v40.v34.v33.v32.v31.v30.render_layout_html = render_v409


app.router.routes[:] = [r for r in app.router.routes if not (getattr(r, 'path', None) == '/admin-v2.js' and 'GET' in getattr(r, 'methods', set()))]


@app.get('/admin-v2.js')
def admin_v409_js():
    base = v408.admin_v408_js().body.decode('utf-8')
    patch = BASE.UI_FILE.with_name('fx_admin_patch.js').read_text()
    return Response(base + '\n' + patch, media_type='application/javascript')
