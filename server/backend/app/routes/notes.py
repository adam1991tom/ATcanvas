import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import db as dbmod

router = APIRouter()


class NoteCreate(BaseModel):
    text: str
    author: str = ''


@router.get('/api/notes')
def list_notes():
    with dbmod.get_db() as c:
        rows = c.execute('SELECT * FROM notes ORDER BY created_at DESC').fetchall()
    return [dict(r) for r in rows]


@router.post('/api/notes')
def create_note(body: NoteCreate):
    text = body.text.strip()
    if not text:
        raise HTTPException(400, 'Note text is required')
    with dbmod.get_db() as c:
        cur = c.execute('INSERT INTO notes(text,author,created_at) VALUES(?,?,?)', (text, body.author.strip(), int(time.time())))
    return {'id': cur.lastrowid}


@router.delete('/api/notes/{note_id}')
def delete_note(note_id: int):
    with dbmod.get_db() as c:
        c.execute('DELETE FROM notes WHERE id=?', (note_id,))
    return {'deleted': True}


@router.get('/api/widget/notes')
def widget_notes(limit: int = 10):
    with dbmod.get_db() as c:
        rows = c.execute('SELECT * FROM notes ORDER BY created_at DESC LIMIT ?', (max(1, min(50, limit)),)).fetchall()
    return [dict(r) for r in rows]
