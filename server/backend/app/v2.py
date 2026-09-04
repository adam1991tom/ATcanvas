from fastapi import HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from pathlib import Path
import json, os, secrets, shutil, sqlite3, time, urllib.request
from . import main

app = main.app
APP_VERSION = os.getenv('AT_CANVAS_VERSION', '0.2.0')
main.APP_VERSION = APP_VERSION
DB_PATH = os.getenv('AT_CANVAS_DB', '/data/at-canvas.db')
MEDIA_DIR = Path(os.getenv('AT_CANVAS_MEDIA', '/data/media'))
UI_FILE = Path(__file__).with_name('admin_v2.html')
JS_FILE = Path(__file__).with_name('admin_v2.js')

def db():
    c=sqlite3.connect(DB_PATH); c.row_factory=sqlite3.Row; return c

@app.on_event('startup')
def init_v2():
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS layouts(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL UNIQUE,width INTEGER DEFAULT 1920,height INTEGER DEFAULT 1080,background TEXT DEFAULT '#101318',created_at INTEGER,updated_at INTEGER);
        CREATE TABLE IF NOT EXISTS layers(id INTEGER PRIMARY KEY AUTOINCREMENT,layout_id INTEGER NOT NULL,name TEXT NOT NULL,type TEXT NOT NULL,x REAL DEFAULT 5,y REAL DEFAULT 5,w REAL DEFAULT 30,h REAL DEFAULT 20,z INTEGER DEFAULT 1,visible INTEGER DEFAULT 1,locked INTEGER DEFAULT 0,opacity REAL DEFAULT 1,config TEXT DEFAULT '{}');
        CREATE TABLE IF NOT EXISTS media(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,filename TEXT NOT NULL,mime TEXT,size INTEGER,created_at INTEGER);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,start_date TEXT,end_date TEXT,notes TEXT DEFAULT '',created_at INTEGER);
        CREATE TABLE IF NOT EXISTS schedules(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,start_time TEXT,end_time TEXT,action TEXT,target TEXT,created_at INTEGER);
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        ''')

class LayoutCreate(BaseModel):
    name:str
    width:int=1920
    height:int=1080
class LayerCreate(BaseModel):
    type:str
class LayerPatch(BaseModel):
    x:float|None=None
    y:float|None=None
    w:float|None=None
    h:float|None=None
    visible:bool|None=None
    locked:bool|None=None
    name:str|None=None
class EventCreate(BaseModel):
    name:str
    start_date:str|None=None
    end_date:str|None=None
    notes:str=''
class ScheduleCreate(BaseModel):
    name:str
    start_time:str
    end_time:str
    action:str='layout'
    target:str=''
class SettingsPatch(BaseModel):
    values:dict[str,str]

@app.get('/api/layouts')
def layouts():
    with db() as c:return [dict(r) for r in c.execute('SELECT * FROM layouts ORDER BY updated_at DESC').fetchall()]

@app.post('/api/layouts')
def add_layout(body:LayoutCreate):
    if not body.name.strip():raise HTTPException(400,'Name is required')
    now=int(time.time())
    try:
        with db() as c:
            cur=c.execute('INSERT INTO layouts(name,width,height,created_at,updated_at) VALUES(?,?,?,?,?)',(body.name.strip(),body.width,body.height,now,now))
            return {'id':cur.lastrowid}
    except sqlite3.IntegrityError:raise HTTPException(400,'Layout name already exists')

@app.delete('/api/layouts/{layout_id}')
def del_layout(layout_id:int):
    with db() as c:
        c.execute('DELETE FROM layers WHERE layout_id=?',(layout_id,))
        c.execute('DELETE FROM layouts WHERE id=?',(layout_id,))
    return {'deleted':True}

@app.get('/api/layouts/{layout_id}/layers')
def layers(layout_id:int):
    with db() as c:return [dict(r) for r in c.execute('SELECT * FROM layers WHERE layout_id=? ORDER BY z',(layout_id,)).fetchall()]

@app.post('/api/layouts/{layout_id}/layers')
def add_layer(layout_id:int,body:LayerCreate):
    names={'clock':'Clock','text':'Text','calendar':'Calendar','photos':'Photos','weather':'Weather','countdown':'Countdown','media':'Media'}
    if body.type not in names:raise HTTPException(400,'Unsupported widget')
    with db() as c:
        z=c.execute('SELECT COALESCE(MAX(z),0)+1 n FROM layers WHERE layout_id=?',(layout_id,)).fetchone()['n']
        cur=c.execute('INSERT INTO layers(layout_id,name,type,z) VALUES(?,?,?,?)',(layout_id,names[body.type],body.type,z))
        c.execute('UPDATE layouts SET updated_at=? WHERE id=?',(int(time.time()),layout_id))
        return {'id':cur.lastrowid}

@app.patch('/api/layers/{layer_id}')
def edit_layer(layer_id:int,body:LayerPatch):
    vals=body.model_dump(exclude_none=True)
    for k in ('visible','locked'):
        if k in vals:vals[k]=1 if vals[k] else 0
    if not vals:return {'ok':True}
    with db() as c:c.execute('UPDATE layers SET '+','.join(f'{k}=?' for k in vals)+' WHERE id=?',(*vals.values(),layer_id))
    return {'ok':True}

@app.delete('/api/layers/{layer_id}')
def del_layer(layer_id:int):
    with db() as c:c.execute('DELETE FROM layers WHERE id=?',(layer_id,))
    return {'deleted':True}

@app.get('/api/media')
def media():
    with db() as c:return [dict(r) for r in c.execute('SELECT * FROM media ORDER BY created_at DESC').fetchall()]

@app.post('/api/media')
async def upload_media(file:UploadFile=File(...)):
    if not file.filename:raise HTTPException(400,'No file selected')
    ext=Path(file.filename).suffix.lower()
    if ext not in {'.jpg','.jpeg','.png','.gif','.webp','.mp4','.webm'}:raise HTTPException(400,'Unsupported file type')
    filename=secrets.token_hex(10)+ext
    dest=MEDIA_DIR/filename
    with dest.open('wb') as f:shutil.copyfileobj(file.file,f)
    with db() as c:
        cur=c.execute('INSERT INTO media(name,filename,mime,size,created_at) VALUES(?,?,?,?,?)',(file.filename,filename,file.content_type,dest.stat().st_size,int(time.time())))
        return {'id':cur.lastrowid}

@app.get('/api/media/{media_id}/file')
def media_file(media_id:int):
    with db() as c:r=c.execute('SELECT * FROM media WHERE id=?',(media_id,)).fetchone()
    if not r:raise HTTPException(404,'Not found')
    return FileResponse(MEDIA_DIR/r['filename'],media_type=r['mime'] or 'application/octet-stream')

@app.delete('/api/media/{media_id}')
def del_media(media_id:int):
    with db() as c:
        r=c.execute('SELECT * FROM media WHERE id=?',(media_id,)).fetchone()
        c.execute('DELETE FROM media WHERE id=?',(media_id,))
    if r:(MEDIA_DIR/r['filename']).unlink(missing_ok=True)
    return {'deleted':True}

@app.get('/api/events')
def events():
    with db() as c:return [dict(r) for r in c.execute('SELECT * FROM events ORDER BY start_date').fetchall()]
@app.post('/api/events')
def add_event(body:EventCreate):
    with db() as c:
        cur=c.execute('INSERT INTO events(name,start_date,end_date,notes,created_at) VALUES(?,?,?,?,?)',(body.name,body.start_date,body.end_date,body.notes,int(time.time())))
        return {'id':cur.lastrowid}
@app.delete('/api/events/{event_id}')
def del_event(event_id:int):
    with db() as c:c.execute('DELETE FROM events WHERE id=?',(event_id,))
    return {'deleted':True}

@app.get('/api/schedules')
def schedules():
    with db() as c:return [dict(r) for r in c.execute('SELECT * FROM schedules ORDER BY start_time').fetchall()]
@app.post('/api/schedules')
def add_schedule(body:ScheduleCreate):
    with db() as c:
        cur=c.execute('INSERT INTO schedules(name,start_time,end_time,action,target,created_at) VALUES(?,?,?,?,?,?)',(body.name,body.start_time,body.end_time,body.action,body.target,int(time.time())))
        return {'id':cur.lastrowid}
@app.delete('/api/schedules/{schedule_id}')
def del_schedule(schedule_id:int):
    with db() as c:c.execute('DELETE FROM schedules WHERE id=?',(schedule_id,))
    return {'deleted':True}

_SENSITIVE_SETTING_MARKERS = ('secret', 'token', 'password')
@app.get('/api/settings')
def settings():
    with db() as c:
        rows = c.execute('SELECT * FROM settings').fetchall()
    return {r['key']: r['value'] for r in rows if not any(m in r['key'].lower() for m in _SENSITIVE_SETTING_MARKERS)}
@app.patch('/api/settings')
def save_settings(body:SettingsPatch):
    with db() as c:
        for k,v in body.values.items():c.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(k,v))
    return {'saved':True}

@app.get('/api/updates/check')
def update_check():
    try:
        req=urllib.request.Request('https://api.github.com/repos/adam1991tom/ATcanvas/commits/main',headers={'User-Agent':'AT-Canvas'})
        with urllib.request.urlopen(req,timeout=5) as r:d=json.load(r)
        return {'ok':True,'commit':d['sha'][:7],'message':d['commit']['message'].split('\n')[0]}
    except Exception as e:return {'ok':False,'error':str(e)}

app.router.routes[:] = [r for r in app.router.routes if not (getattr(r,'path',None)=='/' and 'GET' in getattr(r,'methods',set()))]
@app.get('/',response_class=HTMLResponse)
def admin_v2():
    return UI_FILE.read_text().replace('__VERSION__',APP_VERSION)

@app.get('/admin-v2.js')
def admin_v2_js():
    return FileResponse(JS_FILE,media_type='application/javascript')
