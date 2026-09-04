import secrets
import time

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from .. import db as dbmod
from .. import render as renderer
from ..deps import templates

router = APIRouter()


class DisplayCreate(BaseModel):
    name: str
    layout_id: int | None = None


class DisplayPatch(BaseModel):
    name: str | None = None
    layout_id: int | None = None
    test_mode: bool | None = None


@router.get('/api/displays')
def list_displays(request: Request):
    base = str(request.base_url).rstrip('/')
    with dbmod.get_db() as c:
        rows = c.execute(
            'SELECT d.*, l.name AS layout_name FROM displays d LEFT JOIN layouts l ON l.id=d.layout_id ORDER BY d.name'
        ).fetchall()
    out = []
    for r in rows:
        item = dict(r)
        item['url'] = f"{base}/display/{item['token']}"
        out.append(item)
    return out


@router.post('/api/displays')
def create_display(body: DisplayCreate, request: Request):
    token = secrets.token_urlsafe(12)
    now = int(time.time())
    with dbmod.get_db() as c:
        cur = c.execute(
            'INSERT INTO displays(name,token,layout_id,test_mode,created_at) VALUES(?,?,?,?,?)',
            (body.name.strip(), token, body.layout_id, 0 if body.layout_id else 1, now),
        )
    base = str(request.base_url).rstrip('/')
    return {'id': cur.lastrowid, 'token': token, 'url': f'{base}/display/{token}'}


@router.patch('/api/displays/{display_id}')
def patch_display(display_id: int, body: DisplayPatch):
    vals = body.model_dump(exclude_unset=True)
    if not vals:
        return {'updated': False}
    if 'test_mode' in vals:
        vals['test_mode'] = int(bool(vals['test_mode']))
    with dbmod.get_db() as c:
        cur = c.execute('UPDATE displays SET ' + ','.join(f'{k}=?' for k in vals) + ' WHERE id=?', (*vals.values(), display_id))
        if cur.rowcount == 0:
            raise HTTPException(404, 'Display not found')
    return {'updated': True}


@router.delete('/api/displays/{display_id}')
def delete_display(display_id: int):
    with dbmod.get_db() as c:
        c.execute('DELETE FROM displays WHERE id=?', (display_id,))
    return {'deleted': True}


def _auto_reload(page: str, seconds: int) -> str:
    return page.replace('</body>', f'<script>setTimeout(()=>location.reload(),{seconds * 1000})</script></body>')


@router.get('/display/{token}', response_class=HTMLResponse)
def display_page(token: str):
    with dbmod.get_db() as c:
        d = c.execute('SELECT * FROM displays WHERE token=?', (token,)).fetchone()
        if not d:
            raise HTTPException(404, 'Display URL not found')
        if d['test_mode'] or not d['layout_id']:
            page = templates.get_template('test_screen.html').render(name=d['name'])
            return _auto_reload(page, 15)
        layout = c.execute('SELECT * FROM layouts WHERE id=?', (d['layout_id'],)).fetchone()
        if not layout:
            page = templates.get_template('test_screen.html').render(name='LAYOUT NOT FOUND')
            return _auto_reload(page, 15)
        layers = c.execute('SELECT * FROM layers WHERE layout_id=? ORDER BY z', (layout['id'],)).fetchall()
    page = renderer.render_layout(layout, layers, templates)
    return _auto_reload(page, 180)


@router.get('/display/test', response_class=HTMLResponse)
def display_test_page():
    page = templates.get_template('test_screen.html').render(name='Test Screen')
    return _auto_reload(page, 30)


@router.get('/layout/{layout_id}/preview', response_class=HTMLResponse)
def layout_preview(layout_id: int):
    with dbmod.get_db() as c:
        layout = c.execute('SELECT * FROM layouts WHERE id=?', (layout_id,)).fetchone()
        if not layout:
            raise HTTPException(404, 'Layout not found')
        layers = c.execute('SELECT * FROM layers WHERE layout_id=? ORDER BY z', (layout_id,)).fetchall()
    # No periodic reload here (unlike the real display page) - every widget already
    # self-refreshes its own data on its own interval, and the designer's outer JS
    # re-sets this iframe's src whenever something is actually edited. A reload loop
    # here just caused a visible blank flash every few seconds in the live preview.
    return renderer.render_layout(layout, layers, templates)
