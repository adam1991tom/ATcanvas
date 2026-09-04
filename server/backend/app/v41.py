from fastapi.responses import Response
from . import v40

app = v40.app
BASE = v40.BASE

# Replace only the admin JavaScript route so Designer v2 canvas enhancements
# remain isolated from the Google/backend work in v40.
app.router.routes[:] = [
    r for r in app.router.routes
    if not (getattr(r, 'path', None) == '/admin-v2.js' and 'GET' in getattr(r, 'methods', set()))
]

@app.get('/admin-v2.js')
def admin_v41_js():
    base = v40.admin_v40_js().body.decode('utf-8')
    canvas = BASE.UI_FILE.with_name('designer_v2_canvas_patch.js').read_text()
    return Response(base + '\n' + canvas, media_type='application/javascript')
