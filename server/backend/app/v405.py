import json
import urllib.parse
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, Response
from . import v404

app = v404.app
DB = v404.DB
v40 = v404.v40
BASE = v404.BASE


def _cfg(row):
    try:
        return json.loads(row['config'] or '{}')
    except Exception:
        return {}


def _event_range(ids, start, end, limit=500):
    token=v40._access_token(); out=[]
    for cid in ids:
        q=urllib.parse.urlencode({
            'timeMin':start.astimezone(timezone.utc).isoformat().replace('+00:00','Z'),
            'timeMax':end.astimezone(timezone.utc).isoformat().replace('+00:00','Z'),
            'singleEvents':'true','orderBy':'startTime','maxResults':limit,
        })
        data=v40._json_request(v40.CALENDAR_API+'/calendars/'+urllib.parse.quote(cid,safe='')+'/events?'+q,token=token)
        for e in data.get('items',[]):
            s=e.get('start',{}); f=e.get('end',{})
            out.append({'id':e.get('id'),'summary':e.get('summary') or '(No title)','start':s.get('dateTime') or s.get('date'),'end':f.get('dateTime') or f.get('date'),'all_day':'date' in s,'location':e.get('location',''),'calendar_id':cid,'calendar_name':data.get('summary') or cid})
    out.sort(key=lambda e:e.get('start') or '')
    return out


def _layer_row(layer_id:int):
    with DB() as c:
        row=c.execute('SELECT * FROM layers WHERE id=?',(layer_id,)).fetchone()
    if not row: raise HTTPException(404,'Layer not found')
    if row['type']!='calendar': raise HTTPException(400,'Layer is not a calendar widget')
    return row


@app.get('/api/widget/calendar-v3/{layer_id}')
def calendar_v3_data(layer_id:int):
    row=_layer_row(layer_id); cfg=_cfg(row); ids=cfg.get('calendar_ids') or v40._selected_ids(); view=cfg.get('view','agenda'); now=datetime.now().astimezone()
    grid_range=cfg.get('grid_range','four_weeks'); future_only=cfg.get('future_only',True); highlight_today=cfg.get('highlight_today',True)

    if view=='month_grid':
        if grid_range=='full_month':
            start=now.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
            end=(start.replace(year=start.year+1,month=1) if start.month==12 else start.replace(month=start.month+1))
            # pad to whole Monday-Sunday weeks so the grid stays aligned
            grid_start=start-timedelta(days=start.weekday())
            last=end-timedelta(microseconds=1)
            grid_end=last+timedelta(days=(6-last.weekday())+1)
            rows=max(4, min(6, ((grid_end.date()-grid_start.date()).days)//7))
        else:
            grid_start=now.replace(hour=0,minute=0,second=0,microsecond=0)-timedelta(days=now.weekday())
            grid_end=grid_start+timedelta(days=28)
            rows=4
        events=_event_range(ids,grid_start,grid_end,500)
        if future_only:
            today=now.date()
            filtered=[]
            for e in events:
                try:
                    d=datetime.fromisoformat(e['start'].replace('Z','+00:00')).astimezone().date() if 'T' in e['start'] else datetime.fromisoformat(e['start']).date()
                except Exception:
                    filtered.append(e); continue
                if d>=today: filtered.append(e)
            events=filtered
    else:
        days=max(1,min(90,int(cfg.get('days',14) or 14))); grid_start=now; grid_end=now+timedelta(days=days); rows=0
        events=_event_range(ids,grid_start,grid_end,max(50,int(cfg.get('limit',8) or 8)))
        if view!='scroll_agenda': events=events[:max(1,min(100,int(cfg.get('limit',8) or 8)))]

    colors={}
    try:
        token=v40._access_token(); data=v40._json_request(v40.CALENDAR_API+'/users/me/calendarList?'+urllib.parse.urlencode({'maxResults':250}),token=token)
        for c in data.get('items',[]): colors[c.get('id')]=c.get('backgroundColor') or '#7b2cff'
    except Exception: pass
    for e in events: e['color']=colors.get(e['calendar_id'],'#7b2cff')

    return {
        'view':view,'time_format':cfg.get('time_format','24'),'show_time':cfg.get('show_time',True),'show_end':cfg.get('show_end',True),
        'show_location':cfg.get('show_location',True),'show_calendar':cfg.get('show_calendar',True),'events':events,
        'grid_range':grid_range,'future_only':future_only,'highlight_today':highlight_today,'grid_rows':rows,
        'grid_start':grid_start.isoformat(),'grid_end':grid_end.isoformat(),
        'title':('Next 4 Weeks' if view=='month_grid' and grid_range!='full_month' else now.strftime('%B %Y')),
    }


def _calendar_layer_html(l,cfg):
    lid=l['id']; style=v404.v403._style_for(l,cfg)
    content=f'<div id="calv3-{lid}" style="width:100%;height:100%;overflow:hidden">Loading calendar…</div>'
    script=f'''<script>(async()=>{{const root=document.getElementById('calv3-{lid}');try{{const r=await fetch('/api/widget/calendar-v3/{lid}');const j=await r.json();if(!r.ok)throw Error(j.detail||'Calendar error');const esc=s=>String(s??'').replace(/[&<>]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));const dt=e=>e.all_day?new Date(e.start+'T00:00:00'):new Date(e.start);const tm=e=>e.all_day?'All day':dt(e).toLocaleTimeString('en-GB',{{hour:'2-digit',minute:'2-digit',hour12:j.time_format==='12'}});const meta=e=>`${{j.show_time?tm(e):''}}${{j.show_calendar?(j.show_time?' · ':'')+esc(e.calendar_name):''}}${{j.show_location&&e.location?' · '+esc(e.location):''}}`;const card=e=>`<div style="border-left:4px solid ${{e.color}};background:rgba(255,255,255,.07);border-radius:8px;padding:8px 10px;margin:4px 0"><div style="font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${{esc(e.summary)}}</div><div style="font-size:.58em;opacity:.72;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${{meta(e)}}</div></div>`;
if(j.view==='month_grid'){{const start=new Date(j.grid_start);const today=new Date();today.setHours(0,0,0,0);const names=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];const by={{}};j.events.forEach(e=>{{const d=dt(e);d.setHours(0,0,0,0);const k=d.toISOString().slice(0,10);(by[k]??=[]).push(e)}});let h=`<div style="height:100%;display:grid;grid-template-rows:auto auto 1fr;gap:6px"><div style="font-weight:900;font-size:.8em">${{j.title}}</div><div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px;font-size:.46em;opacity:.7;text-align:center">${{names.map(n=>`<b>${{n}}</b>`).join('')}}</div><div style="display:grid;grid-template-columns:repeat(7,1fr);grid-template-rows:repeat(${{j.grid_rows||4}},1fr);gap:4px;min-height:0">`;for(let i=0;i<(j.grid_rows||4)*7;i++){{const d=new Date(start);d.setDate(start.getDate()+i);d.setHours(0,0,0,0);const key=d.toISOString().slice(0,10);const es=by[key]||[];const isToday=d.getTime()===today.getTime();const past=d<today;h+=`<div style="min-width:0;overflow:hidden;border:${{isToday&&j.highlight_today?'2px solid #c83cff':'1px solid rgba(255,255,255,.12)'}};background:${{isToday&&j.highlight_today?'rgba(177,0,255,.18)':past?'rgba(255,255,255,.018)':'rgba(255,255,255,.035)'}};border-radius:6px;padding:4px;${{past?'opacity:.55':''}}"><div style="font-size:.48em;font-weight:900;margin-bottom:3px">${{d.getDate()}}</div>${{es.slice(0,5).map(e=>`<div title="${{esc(e.summary)}}" style="font-size:.38em;line-height:1.25;margin:2px 0;padding:2px 3px;border-radius:3px;background:${{e.color}};color:white;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${{j.show_time&&!e.all_day?tm(e)+' ':''}}${{esc(e.summary)}}</div>`).join('')}}${{es.length>5?`<div style="font-size:.34em;opacity:.7">+${{es.length-5}} more</div>`:''}}</div>`}}h+='</div></div>';root.innerHTML=h;return}}
if(j.view==='scroll_agenda'){{const groups={{}};j.events.forEach(e=>{{const d=dt(e);const k=d.toLocaleDateString('en-GB',{{weekday:'long',day:'numeric',month:'short'}});(groups[k]??=[]).push(e)}});const body=Object.entries(groups).map(([k,es])=>`<section style="margin-bottom:10px"><div style="position:sticky;top:0;background:rgba(0,0,0,.45);backdrop-filter:blur(6px);padding:5px 2px;font-size:.6em;font-weight:900">${{k}}</div>${{es.map(card).join('')}}</section>`).join('');root.innerHTML=`<div class="at-scroll-inner" style="height:100%;overflow-y:auto;scrollbar-width:none">${{body}}</div>`;const box=root.querySelector('.at-scroll-inner');if(box&&box.scrollHeight>box.clientHeight){{let dir=1;setInterval(()=>{{box.scrollTop+=dir;if(box.scrollTop+box.clientHeight>=box.scrollHeight-2)dir=-1;if(box.scrollTop<=1)dir=1}},55)}}return}}
root.innerHTML=j.events.length?j.events.map(card).join(''):'No upcoming events';}}catch(e){{root.textContent=e.message}}}})();</script>'''
    return f'<div class="layer calendar" style="{style}">{content}</div>'+script


def render_v405(layout,layers):
    noncal=[l for l in layers if l['type']!='calendar']
    page=v404.v403.render_functional(layout,noncal)
    cal=''.join(_calendar_layer_html(l,_cfg(l)) for l in layers if l['type']=='calendar' and l['visible'])
    return page.replace('</body>',cal+'</body>')

v40.v34.v33.v32.v31.v30.render_layout_html=render_v405

app.router.routes[:]=[r for r in app.router.routes if not (getattr(r,'path',None)=='/admin-v2.js' and 'GET' in getattr(r,'methods',set()))]
@app.get('/admin-v2.js')
def admin_v405_js():
    base=v404.admin_v404_js().body.decode('utf-8')
    patch=BASE.UI_FILE.with_name('calendar_grid_options_patch.js').read_text()
    return Response(base+'\n'+patch,media_type='application/javascript')

@app.get('/layout/{layout_id}/calendar-v3-preview',response_class=HTMLResponse)
def calendar_v3_preview(layout_id:int):
    with DB() as c:
        layout=c.execute('SELECT * FROM layouts WHERE id=?',(layout_id,)).fetchone()
        if not layout: raise HTTPException(404,'Layout not found')
        layers=c.execute('SELECT * FROM layers WHERE layout_id=? ORDER BY z',(layout_id,)).fetchall()
    return render_v405(layout,layers)
