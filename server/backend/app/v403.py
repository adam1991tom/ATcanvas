import calendar as pycalendar
import html
import json
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from . import v402

app = v402.app
v40 = v402.v401.v40
DB = v40.DB


def _cfg(row):
    try:
        return json.loads(row['config'] or '{}')
    except Exception:
        return {}


def _layer(layer_id: int, expected: str | None = None):
    with DB() as c:
        row = c.execute('SELECT * FROM layers WHERE id=?', (layer_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Layer not found')
    if expected and row['type'] != expected:
        raise HTTPException(400, f'Layer is not a {expected} widget')
    return row, _cfg(row)


def _safe_int(v, default, lo, hi):
    try:
        return max(lo, min(hi, int(v)))
    except Exception:
        return default


def _google_events_for_ids(ids, days=14, limit=20):
    token = v40._access_token()
    if not ids:
        return []
    days = _safe_int(days, 14, 1, 90)
    limit = _safe_int(limit, 20, 1, 100)
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    events = []
    for cid in ids:
        q = urllib.parse.urlencode({
            'timeMin': now.isoformat().replace('+00:00', 'Z'),
            'timeMax': end.isoformat().replace('+00:00', 'Z'),
            'singleEvents': 'true',
            'orderBy': 'startTime',
            'maxResults': limit,
        })
        url = v40.CALENDAR_API + '/calendars/' + urllib.parse.quote(cid, safe='') + '/events?' + q
        data = v40._json_request(url, token=token)
        for e in data.get('items', []):
            start = e.get('start', {})
            finish = e.get('end', {})
            events.append({
                'id': e.get('id'),
                'summary': e.get('summary') or '(No title)',
                'start': start.get('dateTime') or start.get('date'),
                'end': finish.get('dateTime') or finish.get('date'),
                'all_day': 'date' in start,
                'location': e.get('location', ''),
                'calendar_id': cid,
                'calendar_name': data.get('summary') or cid,
            })
    events.sort(key=lambda e: e.get('start') or '')
    return events[:limit]


@app.get('/api/widget/calendar/{layer_id}')
def calendar_widget_data(layer_id: int):
    _, cfg = _layer(layer_id, 'calendar')
    ids = cfg.get('calendar_ids') or v40._selected_ids()
    events = _google_events_for_ids(ids, cfg.get('days', 14), cfg.get('limit', 8))
    colors = {}
    try:
        token = v40._access_token()
        data = v40._json_request(v40.CALENDAR_API + '/users/me/calendarList?' + urllib.parse.urlencode({'maxResults': 250}), token=token)
        for cal in data.get('items', []):
            colors[cal.get('id')] = cal.get('backgroundColor') or '#7b2cff'
    except Exception:
        pass
    for e in events:
        e['color'] = colors.get(e['calendar_id'], '#7b2cff')
    return {
        'view': cfg.get('view', 'agenda'),
        'time_format': cfg.get('time_format', '24'),
        'show_time': cfg.get('show_time', True),
        'show_end': cfg.get('show_end', True),
        'show_location': cfg.get('show_location', True),
        'show_calendar': cfg.get('show_calendar', True),
        'events': events,
    }


def _http_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'AT-Canvas/0.4'})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.load(r)
    except Exception as exc:
        raise HTTPException(502, f'Weather service error: {exc}')


@app.get('/api/widget/weather/{layer_id}')
def weather_widget_data(layer_id: int):
    _, cfg = _layer(layer_id, 'weather')
    location = str(cfg.get('location') or '').strip()
    if not location:
        raise HTTPException(400, 'Set a weather location in block settings')
    geo = _http_json('https://geocoding-api.open-meteo.com/v1/search?' + urllib.parse.urlencode({'name': location, 'count': 1, 'language': 'en', 'format': 'json'}))
    hits = geo.get('results') or []
    if not hits:
        raise HTTPException(404, 'Weather location not found')
    place = hits[0]
    params = {
        'latitude': place['latitude'], 'longitude': place['longitude'],
        'timezone': 'auto',
        'current': 'temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,pressure_msl,visibility',
        'daily': 'weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset,precipitation_probability_max',
        'forecast_days': _safe_int(cfg.get('forecast_days', 5), 5, 1, 7),
    }
    wx = _http_json('https://api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(params))
    return {
        'place': ', '.join(x for x in [place.get('name'), place.get('admin1')] if x),
        'current': wx.get('current') or {}, 'current_units': wx.get('current_units') or {},
        'daily': wx.get('daily') or {}, 'daily_units': wx.get('daily_units') or {},
        'options': {
            'current': cfg.get('current', True), 'sun': cfg.get('sun', True), 'humidity': cfg.get('humidity', True),
            'wind': cfg.get('wind', True), 'pressure': cfg.get('pressure', True), 'visibility': cfg.get('visibility', True),
            'precip': cfg.get('precip', True), 'forecast': cfg.get('forecast', 'daily'),
        }
    }


@app.get('/api/widget/photos/{layer_id}')
def photos_widget_data(layer_id: int):
    _, cfg = _layer(layer_id, 'photos')
    source = cfg.get('photo_source', 'media')
    if source == 'google':
        return {'source': 'google', 'ready': False, 'message': 'Google Photos connection is the next integration pass.', 'items': []}
    with DB() as c:
        rows = c.execute("SELECT id,name,mime FROM media WHERE mime LIKE 'image/%' ORDER BY created_at DESC").fetchall()
    return {
        'source': 'media', 'ready': True,
        'fit': cfg.get('fit', 'cover'), 'seconds': _safe_int(cfg.get('slideshow_seconds', 10), 10, 2, 3600),
        'transition': cfg.get('transition', 'fade'),
        'items': [{'id': r['id'], 'name': r['name'], 'url': f"/api/media/{r['id']}/file"} for r in rows],
    }


# Replace the renderer globally so browser displays and layout previews share the same functional widgets.
_BASE_RENDER = v40.v34.v33.v32.v31.v30.render_layout_html


def _style_for(l, cfg):
    color = cfg.get('color', '#ffffff')
    background = cfg.get('background', 'transparent')
    font = _safe_int(cfg.get('font_size', 32), 32, 8, 240)
    radius = _safe_int(cfg.get('radius', 0), 0, 0, 100)
    padding = _safe_int(cfg.get('padding', 12), 12, 0, 100)
    align = cfg.get('align', 'left') if cfg.get('align', 'left') in {'left','center','right'} else 'left'
    return f"left:{l['x']}%;top:{l['y']}%;width:{l['w']}%;height:{l['h']}%;z-index:{l['z']};opacity:{l['opacity']};color:{color};background:{background};font-size:{font}px;border-radius:{radius}px;padding:{padding}px;text-align:{align};"


def render_functional(layout, layers):
    parts=[]
    scripts=[]
    for l in layers:
        if not l['visible']:
            continue
        cfg=_cfg(l); typ=l['type']; lid=l['id']; content=''
        if typ=='clock':
            content=f'<div class="at-clock" id="clock-{lid}"></div>'
            fmt='12' if cfg.get('clock_format')=='12' else '24'; seconds=bool(cfg.get('seconds')); show_date=bool(cfg.get('show_date'))
            scripts.append(f"""(()=>{{const el=document.getElementById('clock-{lid}');function tick(){{const d=new Date();const t=d.toLocaleTimeString('en-GB',{{hour:'2-digit',minute:'2-digit',second:{str(seconds).lower()},hour12:{str(fmt=='12').lower()}}});const date={str(show_date).lower()}?'<div style=\"font-size:.45em;opacity:.75;margin-top:.2em\">'+d.toLocaleDateString('en-GB',{{weekday:'long',day:'numeric',month:'long',year:'numeric'}})+'</div>':'';el.innerHTML='<div>'+t+'</div>'+date}}tick();setInterval(tick,1000)}})();""")
        elif typ=='text':
            content=html.escape(str(cfg.get('text','Double-click/edit this text')))
        elif typ=='countdown':
            content=html.escape(str(cfg.get('text','Countdown')))
        elif typ=='media' and cfg.get('media_id'):
            mid=int(cfg['media_id']); content=f'<img src="/api/media/{mid}/file" style="width:100%;height:100%;object-fit:{html.escape(cfg.get("fit","cover"))}">'
        elif typ=='calendar':
            content=f'<div id="cal-{lid}" style="width:100%;height:100%;overflow:hidden">Loading calendar…</div>'
            scripts.append(f"""(async()=>{{const root=document.getElementById('cal-{lid}');try{{const r=await fetch('/api/widget/calendar/{lid}');const j=await r.json();if(!r.ok)throw Error(j.detail||'Calendar error');const esc=s=>String(s??'').replace(/[&<>]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));const dt=e=>{{const d=e.all_day?new Date(e.start+'T00:00:00'):new Date(e.start);return d}};const tm=e=>{{if(e.all_day)return 'All day';return dt(e).toLocaleTimeString('en-GB',{{hour:'2-digit',minute:'2-digit',hour12:j.time_format==='12'}})}};const card=e=>`<div style=\"border-left:5px solid ${{e.color}};padding:.45em .6em;margin:.25em 0;background:rgba(255,255,255,.05);border-radius:.3em\"><div style=\"font-weight:750\">${{esc(e.summary)}}</div><div style=\"font-size:.55em;opacity:.72\">${{j.show_time?tm(e)+' · ':''}}${{j.show_calendar?esc(e.calendar_name):''}}${{j.show_location&&e.location?' · '+esc(e.location):''}}</div></div>`;if(!j.events.length){{root.textContent='No upcoming events';return}}if(j.view==='next'){{root.innerHTML='<div style=\"opacity:.6;font-size:.55em\">NEXT EVENT</div>'+card(j.events[0]);return}}if(j.view==='compact'){{root.innerHTML=j.events.map(e=>`<div style=\"display:grid;grid-template-columns:4px 1fr auto;gap:.45em;align-items:center;padding:.25em 0\"><i style=\"height:100%;background:${{e.color}}\"></i><b>${{esc(e.summary)}}</b><span style=\"font-size:.55em;opacity:.7\">${{tm(e)}}</span></div>`).join('');return}}if(j.view==='today'){{const today=new Date().toDateString();const es=j.events.filter(e=>dt(e).toDateString()===today);root.innerHTML='<div style=\"font-weight:800;margin-bottom:.4em\">Today</div>'+(es.length?es.map(card).join(''):'No events today');return}}if(j.view==='week'){{const groups={{}};j.events.forEach(e=>{{const k=dt(e).toLocaleDateString('en-GB',{{weekday:'short',day:'numeric'}});(groups[k]??=[]).push(e)}});root.innerHTML='<div style=\"display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:.35em;height:100%\">'+Object.entries(groups).slice(0,7).map(([k,es])=>`<div style=\"min-width:0\"><b style=\"font-size:.55em\">${{k}}</b>${{es.map(card).join('')}}</div>`).join('')+'</div>';return}}if(j.view==='month'){{const groups={{}};j.events.forEach(e=>{{const k=dt(e).toLocaleDateString('en-GB',{{day:'numeric',month:'short'}});(groups[k]??=[]).push(e)}});root.innerHTML='<div style=\"display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.4em\">'+Object.entries(groups).map(([k,es])=>`<div style=\"border:1px solid rgba(255,255,255,.12);padding:.35em;border-radius:.3em\"><b style=\"font-size:.5em\">${{k}}</b>${{es.map(card).join('')}}</div>`).join('')+'</div>';return}}root.innerHTML=j.events.map(card).join('')}}catch(e){{root.textContent=e.message}}}})();""")
        elif typ=='weather':
            content=f'<div id="wx-{lid}" style="width:100%;height:100%;overflow:hidden">Loading weather…</div>'
            scripts.append(f"""(async()=>{{const root=document.getElementById('wx-{lid}');try{{const r=await fetch('/api/widget/weather/{lid}');const j=await r.json();if(!r.ok)throw Error(j.detail||'Weather error');const c=j.current||{{}},u=j.current_units||{{}},o=j.options||{{}};let h=`<div style=\"font-size:.55em;opacity:.7\">${{j.place}}</div><div style=\"font-size:1.8em;font-weight:850;line-height:1.1\">${{Math.round(c.temperature_2m??0)}}${{u.temperature_2m||'°C'}}</div>`;const info=[];if(o.humidity)info.push(`Humidity ${{c.relative_humidity_2m??'-'}}%`);if(o.wind)info.push(`Wind ${{c.wind_speed_10m??'-'}} ${{u.wind_speed_10m||''}}`);if(o.pressure)info.push(`Pressure ${{Math.round(c.pressure_msl??0)}} hPa`);if(o.visibility)info.push(`Visibility ${{Math.round((c.visibility??0)/1000)}} km`);if(o.precip)info.push(`Rain ${{c.precipitation??0}} ${{u.precipitation||'mm'}}`);h+=`<div style=\"font-size:.5em;opacity:.8;margin-top:.5em\">${{info.join(' · ')}}</div>`;if(o.forecast==='daily'&&j.daily?.time){{h+='<div style=\"display:grid;grid-template-columns:repeat('+Math.min(j.daily.time.length,7)+',1fr);gap:.3em;margin-top:.7em\">'+j.daily.time.map((d,i)=>`<div style=\"background:rgba(255,255,255,.06);border-radius:.35em;padding:.35em;text-align:center\"><b style=\"font-size:.5em\">${{new Date(d+'T12:00:00').toLocaleDateString('en-GB',{{weekday:'short'}})}}</b><div style=\"font-size:.62em\">${{Math.round(j.daily.temperature_2m_max[i])}}° / ${{Math.round(j.daily.temperature_2m_min[i])}}°</div></div>`).join('')+'</div>'}}root.innerHTML=h}}catch(e){{root.textContent=e.message}}}})();""")
        elif typ=='photos':
            content=f'<div id="photos-{lid}" style="width:100%;height:100%;overflow:hidden">Loading photos…</div>'
            scripts.append(f"""(async()=>{{const root=document.getElementById('photos-{lid}');try{{const r=await fetch('/api/widget/photos/{lid}');const j=await r.json();if(!r.ok)throw Error(j.detail||'Photos error');if(!j.ready){{root.textContent=j.message;return}}if(!j.items.length){{root.textContent='No image media uploaded';return}}let i=0;root.style.position='relative';const show=()=>{{const x=j.items[i%j.items.length];root.innerHTML=`<img src=\"${{x.url}}\" style=\"width:100%;height:100%;object-fit:${{j.fit||'cover'}};${{j.transition==='fade'?'animation:atfade .6s ease':''}}\">`;i++}};show();setInterval(show,(j.seconds||10)*1000)}}catch(e){{root.textContent=e.message}}}})();""")
        else:
            content=html.escape(str(l['name']))
        parts.append(f'<div class="layer {typ}" style="{_style_for(l,cfg)}">{content}</div>')
    script='<script>'+''.join(scripts)+'</script>' if scripts else ''
    return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>*{{box-sizing:border-box}}html,body{{margin:0;width:100%;height:100%;overflow:hidden;background:{layout['background']};font-family:Inter,system-ui,sans-serif}}.layer{{position:absolute;overflow:hidden}}@keyframes atfade{{from{{opacity:.25}}to{{opacity:1}}}}</style></head><body>{''.join(parts)}{script}</body></html>'''


# Every existing display path calls the v30 renderer by reference, so replace it there.
v40.v34.v33.v32.v31.v30.render_layout_html = render_functional


@app.get('/layout/{layout_id}/functional-preview', response_class=HTMLResponse)
def functional_preview(layout_id: int):
    with DB() as c:
        layout=c.execute('SELECT * FROM layouts WHERE id=?',(layout_id,)).fetchone()
        if not layout: raise HTTPException(404,'Layout not found')
        layers=c.execute('SELECT * FROM layers WHERE layout_id=? ORDER BY z',(layout_id,)).fetchall()
    return render_functional(layout,layers)
