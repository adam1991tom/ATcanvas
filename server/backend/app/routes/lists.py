import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import db as dbmod

router = APIRouter()


class ListCreate(BaseModel):
    type: str = 'generic'
    name: str


@router.get('/api/lists')
def get_lists(type: str | None = None):
    with dbmod.get_db() as c:
        if type:
            rows = c.execute('SELECT * FROM lists WHERE type=? ORDER BY name', (type,)).fetchall()
        else:
            rows = c.execute('SELECT * FROM lists ORDER BY name').fetchall()
    return [dict(r) for r in rows]


@router.post('/api/lists')
def create_list(body: ListCreate):
    kind = body.type if body.type in ('chore', 'shopping', 'generic') else 'generic'
    with dbmod.get_db() as c:
        cur = c.execute('INSERT INTO lists(type,name,created_at) VALUES(?,?,?)', (kind, body.name.strip(), int(time.time())))
    return {'id': cur.lastrowid}


@router.delete('/api/lists/{list_id}')
def delete_list(list_id: int):
    with dbmod.get_db() as c:
        c.execute('DELETE FROM lists WHERE id=?', (list_id,))
    return {'deleted': True}


class ItemCreate(BaseModel):
    text: str
    assignee_id: int | None = None
    points: int = 0


class ItemPatch(BaseModel):
    text: str | None = None
    done: bool | None = None
    assignee_id: int | None = None
    points: int | None = None


def _item_dict(r):
    d = dict(r)
    d['done'] = bool(d['done'])
    return d


@router.get('/api/lists/{list_id}/items')
def list_items(list_id: int):
    with dbmod.get_db() as c:
        rows = c.execute(
            """SELECT li.*, p.name AS assignee_name, p.color AS assignee_color FROM list_items li
               LEFT JOIN people p ON p.id = li.assignee_id
               WHERE li.list_id=? ORDER BY li.done ASC, li.position ASC, li.id ASC""",
            (list_id,),
        ).fetchall()
    return [_item_dict(r) for r in rows]


@router.post('/api/lists/{list_id}/items')
def add_item(list_id: int, body: ItemCreate):
    text = body.text.strip()
    if not text:
        raise HTTPException(400, 'Item text is required')
    with dbmod.get_db() as c:
        lst = c.execute('SELECT id FROM lists WHERE id=?', (list_id,)).fetchone()
        if not lst:
            raise HTTPException(404, 'List not found')
        pos = c.execute('SELECT COALESCE(MAX(position),0)+1 AS p FROM list_items WHERE list_id=?', (list_id,)).fetchone()['p']
        cur = c.execute(
            'INSERT INTO list_items(list_id,text,assignee_id,points,position,created_at) VALUES(?,?,?,?,?,?)',
            (list_id, text, body.assignee_id, body.points, pos, int(time.time())),
        )
    return {'id': cur.lastrowid}


@router.patch('/api/list-items/{item_id}')
def patch_item(item_id: int, body: ItemPatch):
    vals = body.model_dump(exclude_unset=True)
    if not vals:
        return {'updated': False}
    if 'done' in vals:
        vals['done'] = int(bool(vals['done']))
    if 'text' in vals and vals['text'] is not None:
        vals['text'] = vals['text'].strip()
    with dbmod.get_db() as c:
        cur = c.execute('UPDATE list_items SET ' + ','.join(f'{k}=?' for k in vals) + ' WHERE id=?', (*vals.values(), item_id))
        if cur.rowcount == 0:
            raise HTTPException(404, 'Item not found')
    return {'updated': True}


@router.get('/api/widget/list/{layer_id}')
def widget_list_data(layer_id: int):
    import json
    with dbmod.get_db() as c:
        layer = c.execute('SELECT * FROM layers WHERE id=?', (layer_id,)).fetchone()
        if not layer:
            raise HTTPException(404, 'Layer not found')
        if layer['type'] != 'list':
            raise HTTPException(400, 'Layer is not a list widget')
        try:
            cfg = json.loads(layer['config'] or '{}')
        except Exception:
            cfg = {}
        list_id = cfg.get('list_id')
        if not list_id:
            raise HTTPException(400, "Pick a list in this widget's settings")
        lst = c.execute('SELECT * FROM lists WHERE id=?', (list_id,)).fetchone()
        if not lst:
            raise HTTPException(404, 'List not found')
        show_done = bool(cfg.get('show_done', True))
        rows = c.execute(
            """SELECT li.*, p.name AS assignee_name, p.color AS assignee_color FROM list_items li
               LEFT JOIN people p ON p.id = li.assignee_id
               WHERE li.list_id=? ORDER BY li.done ASC, li.position ASC, li.id ASC""",
            (list_id,),
        ).fetchall()
    items = [_item_dict(r) for r in rows if show_done or not r['done']]
    return {'title': cfg.get('title') or lst['name'], 'list_type': lst['type'], 'items': items}


@router.post('/api/list-items/{item_id}/toggle')
def toggle_item(item_id: int):
    """Public (see auth.py) - the one write a kiosk display is allowed to make,
    same trust model as physically ticking a paper chore chart on the wall.
    Deliberately narrower than a generic PATCH: this can only flip `done`."""
    with dbmod.get_db() as c:
        row = c.execute('SELECT done FROM list_items WHERE id=?', (item_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Item not found')
        new_done = 0 if row['done'] else 1
        c.execute('UPDATE list_items SET done=? WHERE id=?', (new_done, item_id))
    return {'done': bool(new_done)}


@router.delete('/api/list-items/{item_id}')
def delete_item(item_id: int):
    with dbmod.get_db() as c:
        c.execute('DELETE FROM list_items WHERE id=?', (item_id,))
    return {'deleted': True}
