import mimetypes

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from . import db as dbmod
from . import auth
from .deps import STATIC_DIR, APP_VERSION
from .routes import admin, layouts, displays, weather

# The slim Python base image's mimetypes database doesn't know .webp - without
# this, StaticFiles serves it as text/plain and every browser refuses to render
# it as an image (shows the broken-image alt text instead of the logo).
mimetypes.add_type('image/webp', '.webp')

app = FastAPI(title='AT Canvas', version=APP_VERSION)

app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')

app.middleware('http')(auth.require_login)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(layouts.router)
app.include_router(displays.router)
app.include_router(weather.router)


@app.on_event('startup')
def startup():
    dbmod.init_db()
