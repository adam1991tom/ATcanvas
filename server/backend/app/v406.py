import json
import urllib.parse
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, Response
from . import v405

app=v405.app
DB=v405.DB
v40=v405.v40
BASE=v405.BASE


def _cfg(row):
    try:return json.loads(row['config'] or '{}')
    except Exception:return {}


def _http_json(url):
    return v405.v404.v403._http_json(url)


def _wx_text(code):
    try: c=int(code)
    except Exception: c=-1
    if c==0:return 'Clear sky'
    if c in (1,2):return 'Partly cloudy'
    if c==3:return 'Overcast'
    if c in (45,48):return 'Fog'
    if c in (51,53,55,56,57):return 'Drizzle'
    if c in (61,63,65,66,67):return 'Rain'
    if c in (71,73,75,77):return 'Snow'
    if c in (80,81,82):return 'Rain showers'
    if c in (85,86):return 'Snow showers'
    if c in (95,96,99):return 'Thunderstorm'
    return 'Weather'


def _wx_icon(code, is_day=True):
    try:c=int(code)
    except Exception:c=-1
    if c==0:return '☀️' if is_day else '🌙'
    if c in (1,2):return '🌤️' if is_day else '☁️'
    if c==3:return '☁️'
    if c in (45,48):return '🌫️'
    if c in (51,53,55,56,57):return '🌦️'
    if c in (61,63,65,66,67,80,81,82):return '🌧️'
    if c in (71,73,75,77,85,86):return '🌨️'
    if c in (95,96,99):return '⛈️'
    return '🌡️'


@app.get('/api/widget/weather-v2/{layer_id}')
def weather_v2_data(layer_id:int):
    with DB() as c:
        row=c.execute('SELECT * FROM layers WHERE id=?',(layer_id,)).fetchone()
    if not row: raise HTTPException(404,'Layer not found')
    if row['type']!='weather': raise HTTPException(400,'Layer is not a weather widget')
    cfg=_cfg(row); location=str(cfg.get('location') or '').strip()
    if not location: raise HTTPException(400,'Set a weather location in block settings')
    geo=_http_json('https://geocoding-api.open-meteo.com/v1/search?'+urllib.parse.urlencode({'name':location,'count':1,'language':'en','format':'json'}))
    hits=geo.get('results') or []
    if not hits: raise HTTPException(404,'Weather location not found')
    place=hits[0]
    fahrenheit=cfg.get('weather_units')=='f'
    params={
        'latitude':place['latitude'],'longitude':place['longitude'],'timezone':'auto',
        'current':'temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,pressure_msl,visibility,is_day',
        'daily':'weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max',
        'forecast_days':max(1,min(7,int(cfg.get('forecast_days',5) or 5))),
    }
    if fahrenheit: params['temperature_unit']='fahrenheit'
    wx=_http_json('https://api.open-meteo.com/v1/forecast?'+urllib.parse.urlencode(params))
    cur=wx.get('current') or {}; daily=wx.get('daily') or {}
    days=[]
    for i,d in enumerate(daily.get('time') or []):
        code=(daily.get('weather_code') or [None]*len(daily.get('time') or []))[i]
        days.append({'date':d,'code':code,'icon':_wx_icon(code,True),'condition':_wx_text(code),'max':(daily.get('temperature_2m_max') or [None])[i],'min':(daily.get('temperature_2m_min') or [None])[i],'rain':(daily.get('precipitation_probability_max') or [None])[i]})
    return {
        'place':', '.join(x for x in [place.get('name'),place.get('admin1')] if x),
        'current':cur,'icon':_wx_icon(cur.get('weather_code'),bool(cur.get('is_day',1))),'condition':_wx_text(cur.get('weather_code')),
        'days':days,'units':'°F' if fahrenheit else '°C',
        'options':{
            'mode':cfg.get('weather_mode','full'),'icon_size':cfg.get('icon_size','large'),'show_location':cfg.get('show_weather_location',True),
            'show_feels':cfg.get('show_feels',True),'show_rain_chance':cfg.get('show_rain_chance',True),'show_high_low':cfg.get('show_high_low',True),'show_condition':cfg.get('show_condition',True),
            'humidity':cfg.get('humidity',True),'wind':cfg.get('wind',True),'pressure':cfg.get('pressure',True),'visibility':cfg.get('visibility',True),'precip':cfg.get('precip',True),
            'forecast':cfg.get('forecast','daily')
        }
    }


def _weather_html(l,cfg):
    lid=l['id']; style=v405.v404.v403._style_for(l,cfg)
    content=f'<div id="wx2-{lid}" style="width:100%;height:100%;overflow:hidden">Loading weather…</div>'
    script=f'''<script>(async()=>{{const root=document.getElementById('wx2-{lid}');try{{const r=await fetch('/api/widget/weather-v2/{lid}');const j=await r.json();if(!r.ok)throw Error(j.detail||'Weather error');const o=j.options||{{}},c=j.current||{{}};const f=n=>n==null?'–':Math.round(n);const sz=o.icon_size==='small'?'.95em':o.icon_size==='medium'?'1.35em':'2em';const details=[];if(o.show_feels)details.push(`Feels ${{f(c.apparent_temperature)}}${{j.units}}`);if(o.humidity)details.push(`💧 ${{f(c.relative_humidity_2m)}}%`);if(o.wind)details.push(`💨 ${{f(c.wind_speed_10m)}} km/h`);if(o.pressure)details.push(`◉ ${{f(c.pressure_msl)}} hPa`);if(o.visibility)details.push(`👁 ${{f((c.visibility||0)/1000)}} km`);if(o.precip)details.push(`🌧 ${{c.precipitation??0}} mm`);const forecast=(j.days||[]).map((d,i)=>`<div style="min-width:0;text-align:center;padding:.35em .2em;border-radius:.5em;background:rgba(255,255,255,.055)"><div style="font-size:.5em;font-weight:800">${{new Date(d.date+'T12:00:00').toLocaleDateString('en-GB',{{weekday:'short'}})}}</div><div style="font-size:1em;line-height:1.15">${{d.icon}}</div>${{o.show_high_low?`<div style="font-size:.48em;font-weight:700">${{f(d.max)}}° <span style="opacity:.6">${{f(d.min)}}°</span></div>`:''}}${{o.show_rain_chance&&d.rain!=null?`<div style="font-size:.38em;opacity:.65">💧 ${{f(d.rain)}}%</div>`:''}}</div>`).join('');if(o.mode==='strip'){{root.innerHTML=`<div style="height:100%;display:grid;grid-template-columns:auto 1fr;gap:.7em;align-items:center"><div><div style="font-size:${{sz}};line-height:1">${{j.icon}}</div><div style="font-size:.95em;font-weight:900">${{f(c.temperature_2m)}}${{j.units}}</div></div><div style="display:grid;grid-template-columns:repeat(${{Math.max(1,j.days.length)}},1fr);gap:.3em;min-width:0">${{forecast}}</div></div>`;return}}if(o.mode==='current'){{root.innerHTML=`<div style="height:100%;display:flex;align-items:center;gap:.7em"><div style="font-size:${{sz}}">${{j.icon}}</div><div><div style="font-size:1.7em;font-weight:900;line-height:1">${{f(c.temperature_2m)}}${{j.units}}</div>${{o.show_condition?`<div style="font-size:.58em;font-weight:700">${{j.condition}}</div>`:''}}${{o.show_location?`<div style="font-size:.42em;opacity:.65">${{j.place}}</div>`:''}}<div style="font-size:.38em;opacity:.68;margin-top:.3em">${{details.join(' · ')}}</div></div></div>`;return}}root.innerHTML=`<div style="height:100%;display:grid;grid-template-rows:auto auto 1fr;gap:.5em"><div style="display:flex;align-items:center;gap:.6em"><div style="font-size:${{sz}};line-height:1">${{j.icon}}</div><div><div style="font-size:1.7em;font-weight:900;line-height:1">${{f(c.temperature_2m)}}${{j.units}}</div>${{o.show_condition?`<div style="font-size:.58em;font-weight:800">${{j.condition}}</div>`:''}}${{o.show_location?`<div style="font-size:.42em;opacity:.65">${{j.place}}</div>`:''}}</div></div><div style="font-size:.4em;opacity:.7;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${{details.join(' · ')}}</div>${{o.forecast==='daily'?`<div style="display:grid;grid-template-columns:repeat(${{Math.max(1,j.days.length)}},1fr);gap:.35em;min-height:0">${{forecast}}</div>`:''}}</div>`;}}catch(e){{root.textContent=e.message}}}})();</script>'''
    return f'<div class="layer weather" style="{style}">{content}</div>'+script


def render_v406(layout,layers):
    rest=[l for l in layers if l['type']!='weather']
    page=v405.render_v405(layout,rest)
    wx=''.join(_weather_html(l,_cfg(l)) for l in layers if l['type']=='weather' and l['visible'])
    return page.replace('</body>',wx+'</body>')

v40.v34.v33.v32.v31.v30.render_layout_html=render_v406

app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path',None)=='/admin-v2.js' and 'GET' in getattr(r,'methods',set()))]
@app.get('/admin-v2.js')
def admin_v406_js():
    base=v405.admin_v405_js().body.decode('utf-8')
    patch=BASE.UI_FILE.with_name('weather_options_patch.js').read_text()
    return Response(base+'\n'+patch,media_type='application/javascript')

@app.get('/layout/{layout_id}/weather-preview',response_class=HTMLResponse)
def weather_preview(layout_id:int):
    with DB() as c:
        layout=c.execute('SELECT * FROM layouts WHERE id=?',(layout_id,)).fetchone()
        if not layout: raise HTTPException(404,'Layout not found')
        layers=c.execute('SELECT * FROM layers WHERE layout_id=? ORDER BY z',(layout_id,)).fetchall()
    return render_v406(layout,layers)
