from fastapi import HTTPException, Request
from . import v30

app = v30.app
DB = v30.DB
BASE = v30.BASE
VERSION = '0.3.1'
BASE.APP_VERSION = VERSION
BASE.main.APP_VERSION = VERSION

# Replace heartbeat so display clients receive an absolute renderer URL using
# compatibility field names understood by older/newer client builds.
app.router.routes[:] = [
    r for r in app.router.routes
    if not (getattr(r, 'path', None) == '/api/display/heartbeat' and 'POST' in getattr(r, 'methods', set()))
]

@app.post('/api/display/heartbeat')
def heartbeat_v31(body: BASE.main.Heartbeat, request: Request):
    import time
    now = int(time.time())
    with DB() as c:
        row = c.execute('''SELECT d.*,s.name schedule_name,l.name layout_name
                           FROM displays d
                           LEFT JOIN schedules s ON s.id=d.schedule_id
                           LEFT JOIN layouts l ON l.id=d.layout_id
                           WHERE d.token=?''', (body.token,)).fetchone()
        if not row:
            raise HTTPException(401, 'Unknown display token')
        c.execute('UPDATE displays SET last_seen=?,client_version=?,resolution=? WHERE token=?',
                  (now, body.client_version, body.resolution, body.token))
        block = v30._active_block(c, row['schedule_id'])
        base = str(request.base_url).rstrip('/')
        renderer_url = f"{base}/display/{row['token']}"
        return {
            'ok': True,
            'display': row['name'],
            'version': VERSION,
            'renderer_url': renderer_url,
            'render_url': renderer_url,
            'display_url': renderer_url,
            'url': renderer_url,
            'test_mode': bool(row['test_mode']),
            'layout_id': row['layout_id'],
            'layout': row['layout_name'] or row['current_layout'],
            'brightness': row['brightness'],
            'orientation': row['orientation'] or 'landscape',
            'schedule_id': row['schedule_id'],
            'schedule_name': row['schedule_name'],
            'scheduled_action': block,
            'command': row['desired_command'],
        }
