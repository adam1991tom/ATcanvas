import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import db as dbmod

router = APIRouter()

ALLOWED_EFFECTS = {'none', 'snow', 'rain', 'halloween', 'confetti', 'hearts', 'stars'}


class EventCreate(BaseModel):
    name: str
    start_date: str | None = None
    end_date: str | None = None
    effect: str = 'none'


class EventPatch(BaseModel):
    name: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    effect: str | None = None


def _clean_effect(e):
    return e if e in ALLOWED_EFFECTS else 'none'


@router.get('/api/events')
def list_events():
    with dbmod.get_db() as c:
        rows = c.execute('SELECT * FROM events ORDER BY start_date').fetchall()
    return [dict(r) for r in rows]


@router.post('/api/events')
def create_event(body: EventCreate):
    with dbmod.get_db() as c:
        cur = c.execute(
            'INSERT INTO events(name,start_date,end_date,effect,created_at) VALUES(?,?,?,?,?)',
            (body.name.strip(), body.start_date, body.end_date, _clean_effect(body.effect), int(time.time())),
        )
    return {'id': cur.lastrowid}


@router.patch('/api/events/{event_id}')
def patch_event(event_id: int, body: EventPatch):
    vals = body.model_dump(exclude_unset=True)
    if not vals:
        return {'updated': False}
    if 'effect' in vals:
        vals['effect'] = _clean_effect(vals['effect'])
    with dbmod.get_db() as c:
        cur = c.execute('UPDATE events SET ' + ','.join(f'{k}=?' for k in vals) + ' WHERE id=?', (*vals.values(), event_id))
        if cur.rowcount == 0:
            raise HTTPException(404, 'Event not found')
    return {'updated': True}


@router.delete('/api/events/{event_id}')
def delete_event(event_id: int):
    with dbmod.get_db() as c:
        c.execute('DELETE FROM events WHERE id=?', (event_id,))
    return {'deleted': True}


@router.get('/api/widget/events-active')
def active_events():
    with dbmod.get_db() as c:
        rows = c.execute("""
            SELECT * FROM events
            WHERE effect IS NOT NULL AND effect != '' AND effect != 'none'
              AND start_date IS NOT NULL AND start_date != ''
              AND date('now','localtime') >= date(start_date)
              AND date('now','localtime') <= date(COALESCE(NULLIF(end_date,''), start_date))
            ORDER BY id
        """).fetchall()
    return [dict(r) for r in rows]
