"""Display-page rendering. Widget types register themselves here with a plain
decorator instead of the old codebase's chain of modules each monkeypatching
the previous one's render function - adding a widget type later is just a new
@widget('name') function, nothing upstream needs to change."""
import html
import json

WIDGET_RENDERERS = {}


def widget(type_name):
    def deco(fn):
        WIDGET_RENDERERS[type_name] = fn
        return fn
    return deco


def layer_config(layer):
    try:
        return json.loads(layer['config'] or '{}')
    except Exception:
        return {}


def style_for(layer, config):
    color = config.get('color', '#ffffff')
    background = config.get('background', 'transparent')
    font = max(8, min(240, int(config.get('font_size', 32) or 32)))
    radius = max(0, min(100, int(config.get('radius', 0) or 0)))
    padding = max(0, min(100, int(config.get('padding', 12) or 12)))
    align = config.get('align', 'left')
    if align not in ('left', 'center', 'right'):
        align = 'left'
    return (
        f"left:{layer['x']}%;top:{layer['y']}%;width:{layer['w']}%;height:{layer['h']}%;"
        f"z-index:{layer['z']};opacity:{layer['opacity']};color:{color};background:{background};"
        f"font-size:{font}px;border-radius:{radius}px;padding:{padding}px;text-align:{align};"
    )


@widget('text')
def render_text(layer, config):
    content = html.escape(str(config.get('text', 'Double-click to edit this text')))
    return content, ''


@widget('list')
def render_list(layer, config):
    lid = layer['id']
    content = f'<div id="list-{lid}" style="width:100%;height:100%;overflow:auto">Loading…</div>'
    script = f"""(()=>{{const root=document.getElementById('list-{lid}');
const esc=s=>String(s??'').replace(/[&<>]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));
async function load(){{try{{
const r=await fetch('/api/widget/list/{lid}');const j=await r.json();
if(!r.ok)throw new Error(j.detail||'List error');
const isChore=j.list_type==='chore';
if(!j.items.length){{root.innerHTML=`<div style="font-weight:800;margin-bottom:.4em">${{esc(j.title)}}</div><div style="opacity:.6">Nothing here</div>`;return}}
root.innerHTML=`<div style="font-weight:800;margin-bottom:.5em">${{esc(j.title)}}</div>`+j.items.map(it=>`
<label style="display:flex;align-items:center;gap:.5em;padding:.3em 0;${{it.done?'opacity:.45;text-decoration:line-through':''}}">
<input type="checkbox" data-item="${{it.id}}" ${{it.done?'checked':''}} style="width:1.1em;height:1.1em;flex:none">
<span>${{esc(it.text)}}${{isChore&&it.assignee_name?` <span style="opacity:.7;font-size:.8em;color:${{it.assignee_color||'#6aa7ff'}}">&middot; ${{esc(it.assignee_name)}}</span>`:''}}${{isChore&&it.points?` <span style="opacity:.6;font-size:.75em">(+${{it.points}})</span>`:''}}</span>
</label>`).join('');
root.querySelectorAll('[data-item]').forEach(cb=>cb.onchange=async()=>{{await fetch('/api/list-items/'+cb.dataset.item+'/toggle',{{method:'POST'}});load()}});
}}catch(e){{root.textContent=e.message}}}}
load();setInterval(load,30000);
}})();"""
    return content, script


@widget('photos')
def render_photos(layer, config):
    lid = layer['id']
    seconds = int(config.get('seconds', 10) or 10)
    fit = config.get('fit', 'cover')
    content = f'<div id="photos-{lid}" style="width:100%;height:100%;overflow:hidden;position:relative">Loading photos…</div>'
    script = f"""(()=>{{const root=document.getElementById('photos-{lid}');
async function load(){{try{{
const r=await fetch('/api/widget/photos');const j=await r.json();
if(!j.items||!j.items.length){{root.textContent='No photos uploaded yet';return}}
let i=0;
const show=()=>{{const x=j.items[i%j.items.length];root.innerHTML=`<img src="${{x.url}}" style="width:100%;height:100%;object-fit:{fit};animation:atfade .6s ease">`;i++}};
show();setInterval(show,{max(2, seconds) * 1000});
}}catch(e){{root.textContent=e.message}}}}
load();
}})();"""
    return content, script


@widget('notes')
def render_notes(layer, config):
    lid = layer['id']
    limit = int(config.get('limit', 5) or 5)
    content = f'<div id="notes-{lid}" style="width:100%;height:100%;overflow:auto">Loading…</div>'
    script = f"""(()=>{{const root=document.getElementById('notes-{lid}');
const esc=s=>String(s??'').replace(/[&<>]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));
async function load(){{try{{
const r=await fetch('/api/widget/notes?limit={limit}');const j=await r.json();
if(!j.length){{root.innerHTML='<div style="opacity:.6">No notes yet</div>';return}}
root.innerHTML=j.map(n=>`<div style="padding:.4em .6em;margin:.25em 0;background:rgba(255,255,255,.06);border-radius:.3em"><div style="font-size:.65em">${{esc(n.text)}}</div>${{n.author?`<div style="font-size:.45em;opacity:.6;margin-top:.2em">- ${{esc(n.author)}}</div>`:''}}</div>`).join('');
}}catch(e){{root.textContent=e.message}}}}
load();setInterval(load,60000);
}})();"""
    return content, script


@widget('meals')
def render_meals(layer, config):
    lid = layer['id']
    days = int(config.get('days', 7) or 7)
    content = f'<div id="meals-{lid}" style="width:100%;height:100%;overflow:auto">Loading…</div>'
    script = f"""(()=>{{const root=document.getElementById('meals-{lid}');
const esc=s=>String(s??'').replace(/[&<>]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));
async function load(){{try{{
const r=await fetch('/api/widget/meals?days={days}');const j=await r.json();
root.innerHTML=`<div style="display:grid;grid-template-columns:repeat(${{j.days.length}},1fr);gap:.4em;height:100%">`+j.days.map(d=>{{
const dt=new Date(d.date+'T12:00:00');const label=dt.toLocaleDateString('en-GB',{{weekday:'short',day:'numeric'}});
const meals=Object.entries(d.meals||{{}}).map(([slot,text])=>`<div style="font-size:.45em;margin-top:.3em"><b>${{slot}}</b><div>${{esc(text)}}</div></div>`).join('')||'<div style="font-size:.45em;opacity:.5;margin-top:.3em">-</div>';
return `<div style="background:rgba(255,255,255,.05);border-radius:.3em;padding:.4em"><div style="font-size:.55em;font-weight:800">${{label}}</div>${{meals}}</div>`;
}}).join('')+'</div>';
}}catch(e){{root.textContent=e.message}}}}
load();setInterval(load,10*60*1000);
}})();"""
    return content, script


@widget('calendar')
def render_calendar(layer, config):
    lid = layer['id']
    days = int(config.get('days', 14) or 14)
    limit = int(config.get('limit', 12) or 12)
    content = f'<div id="cal-{lid}" style="width:100%;height:100%;overflow:hidden">Loading calendar…</div>'
    script = f"""(()=>{{const root=document.getElementById('cal-{lid}');
const esc=s=>String(s??'').replace(/[&<>]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));
async function load(){{try{{
const r=await fetch('/api/widget/calendar-events?days={days}&limit={limit}');const j=await r.json();
if(!r.ok)throw new Error(j.detail||'Calendar error');
if(!j.events||!j.events.length){{root.innerHTML=j.selected_calendars?'<div style="opacity:.6">No upcoming events</div>':'<div style="opacity:.6">Connect a calendar in Settings</div>';return}}
let lastDay='';
root.innerHTML=j.events.map(e=>{{
const d=e.all_day?new Date(e.start+'T00:00:00'):new Date(e.start);
const dayKey=d.toDateString();
const dayHeader=dayKey!==lastDay?(()=>{{lastDay=dayKey;return `<div style="font-size:.55em;font-weight:800;opacity:.7;margin:.5em 0 .2em">${{d.toLocaleDateString('en-GB',{{weekday:'long',day:'numeric',month:'long'}})}}</div>`}})():'';
const time=e.all_day?'All day':d.toLocaleTimeString('en-GB',{{hour:'2-digit',minute:'2-digit'}});
return dayHeader+`<div style="border-left:4px solid ${{e.color}};padding:.4em .6em;margin:.2em 0;background:rgba(255,255,255,.04);border-radius:.25em"><div style="font-weight:700;font-size:.62em">${{esc(e.summary)}}</div><div style="font-size:.5em;opacity:.7">${{time}}${{e.location?' · '+esc(e.location):''}}</div></div>`;
}}).join('');
}}catch(e){{root.textContent=e.message}}}}
load();setInterval(load,5*60*1000);
}})();"""
    return content, script


@widget('weather')
def render_weather(layer, config):
    lid = layer['id']
    content = f'<div id="wx-{lid}" style="width:100%;height:100%;overflow:hidden">Loading weather…</div>'
    script = f"""(()=>{{const root=document.getElementById('wx-{lid}');
async function load(){{try{{
const r=await fetch('/api/widget/weather/{lid}');const j=await r.json();
if(!r.ok)throw new Error(j.detail||'Weather error');
const days=(j.days||[]).slice(0,5).map(d=>`<div style="text-align:center;background:rgba(255,255,255,.06);border-radius:.4em;padding:.3em"><div style="font-size:.5em;font-weight:700">${{new Date(d.date+'T12:00:00').toLocaleDateString('en-GB',{{weekday:'short'}})}}</div><div style="font-size:1em">${{d.icon}}</div><div style="font-size:.5em">${{Math.round(d.max)}}° <span style="opacity:.6">${{Math.round(d.min)}}°</span></div></div>`).join('');
root.innerHTML=`<div style="font-size:.55em;opacity:.75">${{j.place}}</div><div style="display:flex;align-items:center;gap:.3em"><div style="font-size:1.6em">${{j.icon}}</div><div style="font-size:1.8em;font-weight:800">${{Math.round(j.temp)}}${{j.units}}</div></div><div style="font-size:.6em;opacity:.85;margin-bottom:.5em">${{j.condition}} · Feels ${{Math.round(j.feels_like)}}${{j.units}}</div><div style="display:grid;grid-template-columns:repeat(${{Math.min((j.days||[]).length,5)||1}},1fr);gap:.3em">${{days}}</div>`;
}}catch(e){{root.textContent=e.message}}}}
load();setInterval(load,15*60*1000);
}})();"""
    return content, script


@widget('clock')
def render_clock(layer, config):
    lid = layer['id']
    fmt12 = config.get('clock_format') == '12'
    seconds = bool(config.get('seconds'))
    show_date = bool(config.get('show_date'))
    content = f'<div class="at-clock" id="clock-{lid}"></div>'
    script = f"""(()=>{{const el=document.getElementById('clock-{lid}');function tick(){{
const d=new Date();
const opts={{hour:'2-digit',minute:'2-digit',hour12:{str(fmt12).lower()}}};
if({str(seconds).lower()})opts.second='2-digit';
const t=d.toLocaleTimeString('en-GB',opts);
const date={str(show_date).lower()}?'<div style="font-size:.45em;opacity:.75;margin-top:.2em">'+d.toLocaleDateString('en-GB',{{weekday:'long',day:'numeric',month:'long',year:'numeric'}})+'</div>':'';
el.innerHTML='<div>'+t+'</div>'+date}}tick();setInterval(tick,1000)}})();"""
    return content, script


def render_layer_html(layer):
    if not layer['visible']:
        return ''
    config = layer_config(layer)
    renderer = WIDGET_RENDERERS.get(layer['type'])
    if renderer:
        content, script = renderer(layer, config)
    else:
        content, script = html.escape(str(layer['name'])), ''
    wrapped = f'<div class="layer {html.escape(layer["type"])}" style="{style_for(layer, config)}">{content}</div>'
    if script:
        wrapped += f'<script>{script}</script>'
    return wrapped


FX_SCRIPT_TEMPLATE = '''<script>
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
      const er = await fetch('/api/widget/events-active');
      const events = await er.json();
      if (Array.isArray(events) && events.length && events[0].effect && events[0].effect!=='none'){ start(events[0].effect); return; }
    }catch(e){}
    if (EFFECT_LAYER_ID){
      try{
        const wr = await fetch('/api/widget/weather/'+EFFECT_LAYER_ID);
        const wj = await wr.json();
        if (wr.ok){ start(wmoToEffect(wj.code, wj.is_day!==0)); return; }
      }catch(e){}
    }
    stop();
  }
  decide();
  setInterval(decide, 10*60*1000);
})();
</script>'''


def render_layout(layout, layers, templates):
    widgets_html = ''.join(render_layer_html(l) for l in layers)
    effect_layer = next((l for l in layers if l['type'] == 'weather' and layer_config(l).get('fullscreen_effect')), None)
    fx_script = FX_SCRIPT_TEMPLATE % {'layer_id': (effect_layer['id'] if effect_layer else 'null')}
    widgets_html += fx_script
    return templates.get_template('display_page.html').render(layout=layout, widgets_html=widgets_html)
