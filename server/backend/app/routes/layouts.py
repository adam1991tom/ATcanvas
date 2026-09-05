import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import db as dbmod

router = APIRouter()


class LayoutCreate(BaseModel):
    name: str
    width: int = 1920
    height: int = 1080


class LayoutPatch(BaseModel):
    name: str | None = None
    width: int | None = None
    height: int | None = None
    background: str | None = None


class LayoutDuplicate(BaseModel):
    name: str
    width: int | None = None
    height: int | None = None


class LayerCreate(BaseModel):
    type: str
    name: str | None = None


class LayerPatch(BaseModel):
    x: float | None = None
    y: float | None = None
    w: float | None = None
    h: float | None = None
    z: int | None = None
    visible: bool | None = None
    locked: bool | None = None
    name: str | None = None
    config: dict | None = None


@router.get('/api/layouts')
def list_layouts():
    with dbmod.get_db() as c:
        rows = c.execute('SELECT * FROM layouts ORDER BY name').fetchall()
    return [dict(r) for r in rows]


@router.post('/api/layouts')
def create_layout(body: LayoutCreate):
    now = int(time.time())
    with dbmod.get_db() as c:
        try:
            cur = c.execute(
                'INSERT INTO layouts(name,width,height,created_at,updated_at) VALUES(?,?,?,?,?)',
                (body.name.strip(), body.width, body.height, now, now),
            )
        except Exception:
            raise HTTPException(400, 'A layout with that name already exists')
    return {'id': cur.lastrowid}


@router.post('/api/layouts/{layout_id}/duplicate')
def duplicate_layout(layout_id: int, body: LayoutDuplicate):
    """Copy a layout's widgets into a new layout - typically used to start a
    portrait (or otherwise differently-shaped) version of an existing design
    without rebuilding every widget from scratch. Block positions carry over
    as percentages of the *old* canvas shape, so they'll usually need
    rearranging/resizing in the designer to look right on the new canvas -
    this just gives you a running start instead of a blank layout."""
    now = int(time.time())
    with dbmod.get_db() as c:
        src = c.execute('SELECT * FROM layouts WHERE id=?', (layout_id,)).fetchone()
        if not src:
            raise HTTPException(404, 'Layout not found')
        width = body.width or src['width']
        height = body.height or src['height']
        try:
            cur = c.execute(
                'INSERT INTO layouts(name,width,height,background,created_at,updated_at) VALUES(?,?,?,?,?,?)',
                (body.name.strip(), width, height, src['background'], now, now),
            )
        except Exception:
            raise HTTPException(400, 'A layout with that name already exists')
        new_id = cur.lastrowid
        layers = c.execute('SELECT * FROM layers WHERE layout_id=? ORDER BY z', (layout_id,)).fetchall()
        for l in layers:
            c.execute(
                'INSERT INTO layers(layout_id,name,type,x,y,w,h,z,visible,locked,opacity,config) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                (new_id, l['name'], l['type'], l['x'], l['y'], l['w'], l['h'], l['z'], l['visible'], l['locked'], l['opacity'], l['config']),
            )
    return {'id': new_id}


@router.patch('/api/layouts/{layout_id}')
def patch_layout(layout_id: int, body: LayoutPatch):
    vals = body.model_dump(exclude_unset=True)
    if not vals:
        return {'updated': False}
    vals['updated_at'] = int(time.time())
    with dbmod.get_db() as c:
        try:
            cur = c.execute('UPDATE layouts SET ' + ','.join(f'{k}=?' for k in vals) + ' WHERE id=?', (*vals.values(), layout_id))
        except Exception:
            raise HTTPException(400, 'A layout with that name already exists')
        if cur.rowcount == 0:
            raise HTTPException(404, 'Layout not found')
    return {'updated': True}


@router.delete('/api/layouts/{layout_id}')
def delete_layout(layout_id: int):
    with dbmod.get_db() as c:
        c.execute('DELETE FROM layouts WHERE id=?', (layout_id,))
    return {'deleted': True}


@router.get('/api/layouts/{layout_id}/layers')
def list_layers(layout_id: int):
    with dbmod.get_db() as c:
        rows = c.execute('SELECT * FROM layers WHERE layout_id=? ORDER BY z', (layout_id,)).fetchall()
    return [dict(r) for r in rows]


@router.post('/api/layouts/{layout_id}/layers')
def add_layer(layout_id: int, body: LayerCreate):
    kind = body.type.strip()
    if not kind:
        raise HTTPException(400, 'Widget type is required')
    with dbmod.get_db() as c:
        layout = c.execute('SELECT id FROM layouts WHERE id=?', (layout_id,)).fetchone()
        if not layout:
            raise HTTPException(404, 'Layout not found')
        z = c.execute('SELECT COALESCE(MAX(z),0)+1 n FROM layers WHERE layout_id=?', (layout_id,)).fetchone()['n']
        name = body.name or kind.capitalize()
        cur = c.execute('INSERT INTO layers(layout_id,name,type,z) VALUES(?,?,?,?)', (layout_id, name, kind, z))
        c.execute('UPDATE layouts SET updated_at=? WHERE id=?', (int(time.time()), layout_id))
    return {'id': cur.lastrowid}


@router.patch('/api/layers/{layer_id}')
def patch_layer(layer_id: int, body: LayerPatch):
    vals = body.model_dump(exclude_unset=True)
    if not vals:
        return {'updated': False}
    if 'config' in vals:
        import json
        vals['config'] = json.dumps(vals['config'])
    if 'visible' in vals:
        vals['visible'] = int(bool(vals['visible']))
    if 'locked' in vals:
        vals['locked'] = int(bool(vals['locked']))
    with dbmod.get_db() as c:
        cur = c.execute('UPDATE layers SET ' + ','.join(f'{k}=?' for k in vals) + ' WHERE id=?', (*vals.values(), layer_id))
        if cur.rowcount == 0:
            raise HTTPException(404, 'Layer not found')
    return {'updated': True}


@router.delete('/api/layers/{layer_id}')
def delete_layer(layer_id: int):
    with dbmod.get_db() as c:
        c.execute('DELETE FROM layers WHERE id=?', (layer_id,))
    return {'deleted': True}
