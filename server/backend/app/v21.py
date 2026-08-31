from fastapi import HTTPException
from pydantic import BaseModel
import time
from . import v2

app = v2.app
v2.APP_VERSION = '0.2.1'
v2.main.APP_VERSION = '0.2.1'

class OrientationPatch(BaseModel):
    orientation: str

VALID_ORIENTATIONS = {'landscape','portrait','landscape_flipped','portrait_flipped'}

# Replace the original heartbeat route so displays receive orientation as part of config.
app.router.routes[:] = [
    r for r in app.router.routes
    if not (getattr(r, 'path', None) == '/api/display/heartbeat' and 'POST' in getattr(r, 'methods', set()))
]

@app.post('/api/display/heartbeat')
def display_heartbeat_v21(body: v2.main.Heartbeat):
    now = int(time.time())
    with v2.db() as c:
        row = c.execute('SELECT * FROM displays WHERE token=?', (body.token,)).fetchone()
        if not row:
            raise HTTPException(401, 'Unknown display token')
        c.execute(
            'UPDATE displays SET last_seen=?,client_version=?,resolution=? WHERE token=?',
            (now, body.client_version, body.resolution, body.token),
        )
        return {
            'ok': True,
            'display': row['name'],
            'layout': row['current_layout'],
            'brightness': row['brightness'],
            'orientation': row['orientation'] or 'landscape',
            'command': row['desired_command'],
        }

@app.patch('/api/displays/{display_id}/orientation')
def set_display_orientation(display_id: int, body: OrientationPatch):
    if body.orientation not in VALID_ORIENTATIONS:
        raise HTTPException(400, 'Unsupported orientation')
    with v2.db() as c:
        cur = c.execute('UPDATE displays SET orientation=? WHERE id=?', (body.orientation, display_id))
        if cur.rowcount == 0:
            raise HTTPException(404, 'Display not found')
    return {'ok': True, 'orientation': body.orientation}

@app.post('/api/layouts/{layout_id}/rotate')
def rotate_layout(layout_id: int):
    with v2.db() as c:
        row = c.execute('SELECT width,height FROM layouts WHERE id=?', (layout_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Layout not found')
        c.execute(
            'UPDATE layouts SET width=?,height=?,updated_at=? WHERE id=?',
            (row['height'], row['width'], int(time.time()), layout_id),
        )
    return {'ok': True, 'width': row['height'], 'height': row['width']}
