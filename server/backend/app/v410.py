from fastapi.responses import Response
from . import v409

app = v409.app
DB = v409.DB
BASE = v409.BASE
VERSION = '0.6.0'
BASE.APP_VERSION = VERSION
BASE.main.APP_VERSION = VERSION

app.router.routes[:] = [r for r in app.router.routes if not (getattr(r, 'path', None) == '/admin-v2.js' and 'GET' in getattr(r, 'methods', set()))]


@app.get('/admin-v2.js')
def admin_v410_js():
    base = v409.admin_v409_js().body.decode('utf-8')
    patch = BASE.UI_FILE.with_name('live_preview_patch.js').read_text()
    return Response(base + '\n' + patch, media_type='application/javascript')
