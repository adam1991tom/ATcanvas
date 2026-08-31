from fastapi.responses import HTMLResponse
from . import v40

app = v40.app


# v0.4.0 configured Google OAuth clients to use /api/google/callback,
# while the original handler was accidentally registered at
# /api/google/oauth/callback. Keep both URLs valid so existing OAuth
# configuration continues to work without requiring users to edit Google.
@app.get('/api/google/callback', response_class=HTMLResponse)
def google_oauth_callback_compat(code: str = '', state: str = '', error: str = ''):
    return v40.google_oauth_callback(code=code, state=state, error=error)
