from fastapi.responses import Response
from . import v401

app = v401.app
BASE = v401.v40.BASE

# Keep the Google callback compatibility layer from v401 and replace only
# the admin JavaScript route to append the Designer v2 canvas enhancements.
app.router.routes[:] = [
    r for r in app.router.routes
    if not (getattr(r, 'path', None) == '/admin-v2.js' and 'GET' in getattr(r, 'methods', set()))
]

@app.get('/admin-v2.js')
def admin_v402_js():
    base = v401.v40.admin_v40_js().body.decode('utf-8')
    canvas = BASE.UI_FILE.with_name('designer_v2_canvas_patch.js').read_text()
    return Response(base + '\n' + canvas, media_type='application/javascript')
