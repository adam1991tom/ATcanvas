from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import db as dbmod

router = APIRouter()

SLOTS = ('breakfast', 'lunch', 'dinner')


class MealSet(BaseModel):
    date: str
    slot: str
    text: str


@router.get('/api/meals')
def get_meals(start: str | None = None, days: int = 7):
    days = max(1, min(31, days))
    if not start:
        start = date.today().isoformat()
    try:
        start_d = date.fromisoformat(start)
    except ValueError:
        raise HTTPException(400, 'start must be YYYY-MM-DD')
    end_d = start_d + timedelta(days=days - 1)
    with dbmod.get_db() as c:
        rows = c.execute(
            'SELECT * FROM meal_plan WHERE date>=? AND date<=? ORDER BY date',
            (start_d.isoformat(), end_d.isoformat()),
        ).fetchall()
    return [dict(r) for r in rows]


@router.post('/api/meals')
def set_meal(body: MealSet):
    if body.slot not in SLOTS:
        raise HTTPException(400, f'slot must be one of {SLOTS}')
    try:
        date.fromisoformat(body.date)
    except ValueError:
        raise HTTPException(400, 'date must be YYYY-MM-DD')
    with dbmod.get_db() as c:
        if body.text.strip():
            c.execute(
                'INSERT INTO meal_plan(date,slot,text) VALUES(?,?,?) '
                'ON CONFLICT(date,slot) DO UPDATE SET text=excluded.text',
                (body.date, body.slot, body.text.strip()),
            )
        else:
            c.execute('DELETE FROM meal_plan WHERE date=? AND slot=?', (body.date, body.slot))
    return {'saved': True}


@router.get('/api/widget/meals')
def widget_meals(days: int = 7):
    days = max(1, min(14, days))
    start_d = date.today()
    end_d = start_d + timedelta(days=days - 1)
    with dbmod.get_db() as c:
        rows = c.execute(
            'SELECT * FROM meal_plan WHERE date>=? AND date<=? ORDER BY date',
            (start_d.isoformat(), end_d.isoformat()),
        ).fetchall()
    by_date = {}
    for r in rows:
        by_date.setdefault(r['date'], {})[r['slot']] = r['text']
    days_out = []
    for i in range(days):
        d = (start_d + timedelta(days=i)).isoformat()
        days_out.append({'date': d, 'meals': by_date.get(d, {})})
    return {'days': days_out}
