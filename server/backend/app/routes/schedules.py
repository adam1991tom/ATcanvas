import time
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import db as dbmod

router = APIRouter()

ALLOWED_ACTIONS = {'layout', 'screen_off', 'screen_on', 'dim'}


class ScheduleCreate(BaseModel):
    name: str


class BlockCreate(BaseModel):
    start_time: str
    end_time: str
    action: str = 'layout'
    target: str = ''


class BlockPatch(BaseModel):
    start_time: str | None = None
    end_time: str | None = None
    action: str | None = None
    target: str | None = None


@router.get('/api/schedules')
def list_schedules():
    with dbmod.get_db() as c:
        rows = c.execute('SELECT * FROM schedules ORDER BY name').fetchall()
    return [dict(r) for r in rows]


@router.post('/api/schedules')
def create_schedule(body: ScheduleCreate):
    with dbmod.get_db() as c:
        cur = c.execute('INSERT INTO schedules(name,created_at) VALUES(?,?)', (body.name.strip(), int(time.time())))
    return {'id': cur.lastrowid}


@router.delete('/api/schedules/{schedule_id}')
def delete_schedule(schedule_id: int):
    with dbmod.get_db() as c:
        c.execute('DELETE FROM schedules WHERE id=?', (schedule_id,))
    return {'deleted': True}


@router.get('/api/schedules/{schedule_id}/blocks')
def list_blocks(schedule_id: int):
    with dbmod.get_db() as c:
        rows = c.execute('SELECT * FROM schedule_blocks WHERE schedule_id=? ORDER BY start_time', (schedule_id,)).fetchall()
    return [dict(r) for r in rows]


@router.post('/api/schedules/{schedule_id}/blocks')
def add_block(schedule_id: int, body: BlockCreate):
    if body.action not in ALLOWED_ACTIONS:
        raise HTTPException(400, f'action must be one of {ALLOWED_ACTIONS}')
    with dbmod.get_db() as c:
        sched = c.execute('SELECT id FROM schedules WHERE id=?', (schedule_id,)).fetchone()
        if not sched:
            raise HTTPException(404, 'Schedule not found')
        cur = c.execute(
            'INSERT INTO schedule_blocks(schedule_id,start_time,end_time,action,target) VALUES(?,?,?,?,?)',
            (schedule_id, body.start_time, body.end_time, body.action, body.target),
        )
    return {'id': cur.lastrowid}


@router.patch('/api/schedule-blocks/{block_id}')
def patch_block(block_id: int, body: BlockPatch):
    vals = body.model_dump(exclude_unset=True)
    if not vals:
        return {'updated': False}
    if 'action' in vals and vals['action'] not in ALLOWED_ACTIONS:
        raise HTTPException(400, f'action must be one of {ALLOWED_ACTIONS}')
    with dbmod.get_db() as c:
        cur = c.execute('UPDATE schedule_blocks SET ' + ','.join(f'{k}=?' for k in vals) + ' WHERE id=?', (*vals.values(), block_id))
        if cur.rowcount == 0:
            raise HTTPException(404, 'Block not found')
    return {'updated': True}


@router.delete('/api/schedule-blocks/{block_id}')
def delete_block(block_id: int):
    with dbmod.get_db() as c:
        c.execute('DELETE FROM schedule_blocks WHERE id=?', (block_id,))
    return {'deleted': True}


def _time_in_range(start, end, current):
    if start <= end:
        return start <= current < end
    return current >= start or current < end


def active_block(c, schedule_id):
    """Used by routes/displays.py to decide what a display should show right now.
    No day-of-week filtering yet - a block applies at that time every day."""
    if not schedule_id:
        return None
    now = datetime.now().strftime('%H:%M')
    blocks = c.execute('SELECT * FROM schedule_blocks WHERE schedule_id=?', (schedule_id,)).fetchall()
    for b in blocks:
        if _time_in_range(b['start_time'], b['end_time'], now):
            return dict(b)
    return None


@router.get('/api/schedules/{schedule_id}/now')
def schedule_now(schedule_id: int):
    with dbmod.get_db() as c:
        block = active_block(c, schedule_id)
    return {'active_block': block}
