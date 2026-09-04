from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..deps import templates, APP_VERSION

router = APIRouter()


@router.get('/', response_class=HTMLResponse)
def admin_shell(request: Request):
    return templates.TemplateResponse(request, 'admin.html', {'version': APP_VERSION})


@router.get('/api/health')
def health():
    return {'ok': True, 'version': APP_VERSION}
