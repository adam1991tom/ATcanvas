import secrets
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse

from .. import db as dbmod

router = APIRouter()

ALLOWED_MIME_PREFIXES = ('image/', 'video/mp4', 'video/webm')
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200MB, generous for a home photo/video slideshow


@router.get('/api/media')
def list_media():
    with dbmod.get_db() as c:
        rows = c.execute('SELECT * FROM media ORDER BY created_at DESC').fetchall()
    return [dict(r) for r in rows]


@router.post('/api/media')
async def upload_media(file: UploadFile = File(...)):
    mime = file.content_type or ''
    if not any(mime.startswith(p) for p in ALLOWED_MIME_PREFIXES):
        raise HTTPException(400, 'Only images and MP4/WebM video are supported')
    dbmod.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or '').suffix or ''
    stored_name = secrets.token_hex(16) + ext
    dest = dbmod.MEDIA_DIR / stored_name
    size = 0
    with open(dest, 'wb') as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(400, 'File too large (200MB limit)')
            out.write(chunk)
    with dbmod.get_db() as c:
        cur = c.execute(
            'INSERT INTO media(name,filename,mime,size,created_at) VALUES(?,?,?,?,?)',
            (file.filename or stored_name, stored_name, mime, size, int(time.time())),
        )
    return {'id': cur.lastrowid}


@router.delete('/api/media/{media_id}')
def delete_media(media_id: int):
    with dbmod.get_db() as c:
        row = c.execute('SELECT filename FROM media WHERE id=?', (media_id,)).fetchone()
        c.execute('DELETE FROM media WHERE id=?', (media_id,))
    if row:
        (dbmod.MEDIA_DIR / row['filename']).unlink(missing_ok=True)
    return {'deleted': True}


@router.get('/api/widget/photos')
def widget_photos():
    with dbmod.get_db() as c:
        rows = c.execute("SELECT id,name,mime FROM media WHERE mime LIKE 'image/%' ORDER BY created_at DESC").fetchall()
    return {'items': [{'id': r['id'], 'name': r['name'], 'url': f"/api/widget/media/{r['id']}/file"} for r in rows]}


@router.get('/api/widget/media/{media_id}/file')
def media_file(media_id: int):
    with dbmod.get_db() as c:
        row = c.execute('SELECT * FROM media WHERE id=?', (media_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Media not found')
    path = dbmod.MEDIA_DIR / row['filename']
    if not path.exists():
        raise HTTPException(404, 'File missing on disk')
    return FileResponse(path, media_type=row['mime'])
