import json
import time
from fastapi import HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel
from . import v407, v40, v403, v2

app = v407.app
DB = v407.DB
BASE = v407.BASE
VERSION = '0.5.0'
BASE.APP_VERSION = VERSION
BASE.main.APP_VERSION = VERSION


# v2.py's add_layer() rejects any widget type outside a fixed allowlist that predates
# the 'todo' widget - override it with the same behaviour plus 'todo' included.
_LAYER_NAMES = {'clock': 'Clock', 'text': 'Text', 'calendar': 'Calendar', 'photos': 'Photos',
                'weather': 'Weather', 'countdown': 'Countdown', 'media': 'Media', 'todo': 'To-Do'}
app.router.routes[:] = [r for r in app.router.routes if not (
    getattr(r, 'path', None) == '/api/layouts/{layout_id}/layers' and 'POST' in getattr(r, 'methods', set())
)]


@app.post('/api/layouts/{layout_id}/layers')
def add_layer_v408(layout_id: int, body: v2.LayerCreate):
    if body.type not in _LAYER_NAMES:
        raise HTTPException(400, 'Unsupported widget')
    with DB() as c:
        z = c.execute('SELECT COALESCE(MAX(z),0)+1 n FROM layers WHERE layout_id=?', (layout_id,)).fetchone()['n']
        cur = c.execute('INSERT INTO layers(layout_id,name,type,z) VALUES(?,?,?,?)', (layout_id, _LAYER_NAMES[body.type], body.type, z))
        c.execute('UPDATE layouts SET updated_at=? WHERE id=?', (int(time.time()), layout_id))
        return {'id': cur.lastrowid}


@app.on_event('startup')
def init_v408():
    with DB() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS todos(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT NOT NULL,
            done INTEGER DEFAULT 0,
            assignee TEXT DEFAULT '',
            points INTEGER DEFAULT 0,
            position INTEGER DEFAULT 0,
            created_at INTEGER
        );
        ''')


class TodoCreate(BaseModel):
    text: str
    assignee: str = ''
    points: int = 0


class TodoPatch(BaseModel):
    text: str | None = None
    done: bool | None = None
    assignee: str | None = None
    points: int | None = None


@app.get('/api/todos')
def list_todos():
    with DB() as c:
        rows = c.execute('SELECT * FROM todos ORDER BY done ASC, position ASC, id ASC').fetchall()
    return [dict(r) for r in rows]


@app.post('/api/todos')
def create_todo(body: TodoCreate):
    text = body.text.strip()
    if not text:
        raise HTTPException(400, 'To-do text is required')
    with DB() as c:
        pos = c.execute('SELECT COALESCE(MAX(position),0)+1 AS p FROM todos').fetchone()['p']
        cur = c.execute(
            'INSERT INTO todos(text,assignee,points,position,created_at) VALUES(?,?,?,?,?)',
            (text, body.assignee.strip(), body.points, pos, int(time.time())),
        )
    return {'id': cur.lastrowid}


@app.patch('/api/todos/{todo_id}')
def patch_todo(todo_id: int, body: TodoPatch):
    vals = body.model_dump(exclude_unset=True)
    if not vals:
        return {'updated': False}
    if 'done' in vals:
        vals['done'] = int(bool(vals['done']))
    if 'text' in vals and vals['text'] is not None:
        vals['text'] = vals['text'].strip()
    with DB() as c:
        cur = c.execute('UPDATE todos SET ' + ','.join(f'{k}=?' for k in vals) + ' WHERE id=?', (*vals.values(), todo_id))
        if cur.rowcount == 0:
            raise HTTPException(404, 'Todo not found')
    return {'updated': True}


@app.delete('/api/todos/{todo_id}')
def delete_todo(todo_id: int):
    with DB() as c:
        c.execute('DELETE FROM todos WHERE id=?', (todo_id,))
    return {'deleted': True}


def _cfg(l):
    try:
        return json.loads(l['config'] or '{}')
    except Exception:
        return {}


@app.get('/api/widget/todo/{layer_id}')
def todo_widget_data(layer_id: int):
    with DB() as c:
        layer = c.execute('SELECT * FROM layers WHERE id=?', (layer_id,)).fetchone()
        if not layer:
            raise HTTPException(404, 'Layer not found')
        if layer['type'] != 'todo':
            raise HTTPException(400, 'Layer is not a to-do widget')
        cfg = _cfg(layer)
        show_done = bool(cfg.get('show_done', True))
        rows = c.execute('SELECT * FROM todos ORDER BY done ASC, position ASC, id ASC').fetchall()
    items = [dict(r) for r in rows if show_done or not r['done']]
    return {'title': cfg.get('title') or 'To-Do', 'items': items}


_PREV_RENDER = v40.v34.v33.v32.v31.v30.render_layout_html


def _todo_widget_html(l):
    cfg = _cfg(l)
    lid = l['id']
    style = v403._style_for(l, cfg)
    content = f'<div id="todo-{lid}" style="width:100%;height:100%;overflow:auto">Loading…</div>'
    script = f'''<script>(()=>{{const root=document.getElementById('todo-{lid}');const esc=s=>String(s??'').replace(/[&<>]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));async function load(){{try{{const r=await fetch('/api/widget/todo/{lid}');const j=await r.json();if(!r.ok)throw Error(j.detail||'To-do error');if(!j.items.length){{root.innerHTML=`<div style="font-weight:800;margin-bottom:.4em">${{esc(j.title)}}</div><div style="opacity:.6">Nothing to do</div>`;return}}root.innerHTML=`<div style="font-weight:800;margin-bottom:.5em">${{esc(j.title)}}</div>`+j.items.map(t=>`<label style="display:flex;align-items:center;gap:.5em;padding:.3em 0;${{t.done?'opacity:.45;text-decoration:line-through':''}}"><input type="checkbox" data-todo="${{t.id}}" ${{t.done?'checked':''}} style="width:1.15em;height:1.15em;flex:none"><span>${{esc(t.text)}}${{t.assignee?` <span style="opacity:.6;font-size:.8em">&middot; ${{esc(t.assignee)}}</span>`:''}}</span></label>`).join('');root.querySelectorAll('[data-todo]').forEach(cb=>{{cb.onchange=async()=>{{await fetch('/api/todos/'+cb.dataset.todo,{{method:'PATCH',headers:{{'content-type':'application/json'}},body:JSON.stringify({{done:cb.checked}})}});load()}}}})}}catch(e){{root.textContent=e.message}}}}load();setInterval(load,30000)}})();</script>'''
    return f'<div class="layer todo" style="{style}">{content}</div>' + script


def render_v408(layout, layers):
    rest = [l for l in layers if l['type'] != 'todo']
    page = _PREV_RENDER(layout, rest)
    todo_html = ''.join(_todo_widget_html(l) for l in layers if l['type'] == 'todo' and l['visible'])
    return page.replace('</body>', todo_html + '</body>')


v40.v34.v33.v32.v31.v30.render_layout_html = render_v408


TODOS_SECTION = '''<section class="page" id="page-todos"><div class="top"><div><h1>To-Do</h1><div class="muted">A shared checklist shown on your displays - tap items directly on the screen to tick them off.</div></div><button class="action" id="newTodo">+ New item</button></div><div class="card"><label class="dv2-check" style="margin-bottom:14px;display:flex;align-items:center;gap:8px"><input type="checkbox" id="todoShowDone"> Show completed items</label><div id="todoList"></div></div></section>'''


def _insert_section(src):
    marker = '</main>'
    idx = src.find(marker)
    if idx < 0 or 'id="page-todos"' in src:
        return src
    return src[:idx] + TODOS_SECTION + src[idx:]


app.router.routes[:] = [r for r in app.router.routes if not (getattr(r, 'path', None) == '/' and 'GET' in getattr(r, 'methods', set()))]
app.router.routes[:] = [r for r in app.router.routes if not (getattr(r, 'path', None) == '/admin-v2.js' and 'GET' in getattr(r, 'methods', set()))]


@app.get('/', response_class=HTMLResponse)
def admin_v408():
    return _insert_section(v407.admin_v407())


@app.get('/admin-v2.js')
def admin_v408_js():
    base = v407.v406.admin_v406_js().body.decode('utf-8')
    patch = BASE.UI_FILE.with_name('todo_admin_patch.js').read_text()
    return Response(base + '\n' + patch, media_type='application/javascript')
