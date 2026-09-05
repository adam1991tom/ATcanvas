import time

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import db as dbmod

router = APIRouter()


class PersonCreate(BaseModel):
    name: str
    color: str = '#6aa7ff'
    avatar: str = ''


class PersonPatch(BaseModel):
    name: str | None = None
    color: str | None = None
    avatar: str | None = None


def _points_balance(c, person_id):
    earned = c.execute(
        """SELECT COALESCE(SUM(li.points),0) AS n FROM list_items li
           JOIN lists l ON l.id = li.list_id
           WHERE li.assignee_id=? AND li.done=1 AND l.type='chore'""",
        (person_id,),
    ).fetchone()['n']
    spent = c.execute(
        """SELECT COALESCE(SUM(r.point_cost),0) AS n FROM redemptions rd
           JOIN rewards r ON r.id = rd.reward_id
           WHERE rd.person_id=?""",
        (person_id,),
    ).fetchone()['n']
    return earned - spent


@router.get('/api/people')
def list_people():
    with dbmod.get_db() as c:
        rows = c.execute('SELECT * FROM people ORDER BY name').fetchall()
        out = []
        for r in rows:
            item = dict(r)
            item['points'] = _points_balance(c, r['id'])
            out.append(item)
    return out


@router.post('/api/people')
def create_person(body: PersonCreate):
    with dbmod.get_db() as c:
        cur = c.execute('INSERT INTO people(name,color,avatar,created_at) VALUES(?,?,?,?)',
                         (body.name.strip(), body.color, body.avatar, int(time.time())))
    return {'id': cur.lastrowid}


@router.patch('/api/people/{person_id}')
def patch_person(person_id: int, body: PersonPatch):
    vals = body.model_dump(exclude_unset=True)
    if not vals:
        return {'updated': False}
    with dbmod.get_db() as c:
        cur = c.execute('UPDATE people SET ' + ','.join(f'{k}=?' for k in vals) + ' WHERE id=?', (*vals.values(), person_id))
        if cur.rowcount == 0:
            raise HTTPException(404, 'Person not found')
    return {'updated': True}


@router.delete('/api/people/{person_id}')
def delete_person(person_id: int):
    with dbmod.get_db() as c:
        c.execute('DELETE FROM people WHERE id=?', (person_id,))
    return {'deleted': True}


class RewardCreate(BaseModel):
    name: str
    point_cost: int = 0


@router.get('/api/rewards')
def list_rewards():
    with dbmod.get_db() as c:
        rows = c.execute('SELECT * FROM rewards ORDER BY point_cost').fetchall()
    return [dict(r) for r in rows]


@router.post('/api/rewards')
def create_reward(body: RewardCreate):
    with dbmod.get_db() as c:
        cur = c.execute('INSERT INTO rewards(name,point_cost,created_at) VALUES(?,?,?)',
                         (body.name.strip(), body.point_cost, int(time.time())))
    return {'id': cur.lastrowid}


@router.delete('/api/rewards/{reward_id}')
def delete_reward(reward_id: int):
    with dbmod.get_db() as c:
        c.execute('DELETE FROM rewards WHERE id=?', (reward_id,))
    return {'deleted': True}


class RedeemBody(BaseModel):
    person_id: int


@router.post('/api/rewards/{reward_id}/redeem')
def redeem_reward(reward_id: int, body: RedeemBody):
    with dbmod.get_db() as c:
        reward = c.execute('SELECT * FROM rewards WHERE id=?', (reward_id,)).fetchone()
        if not reward:
            raise HTTPException(404, 'Reward not found')
        person = c.execute('SELECT * FROM people WHERE id=?', (body.person_id,)).fetchone()
        if not person:
            raise HTTPException(404, 'Person not found')
        balance = _points_balance(c, body.person_id)
        if balance < reward['point_cost']:
            raise HTTPException(400, f"{person['name']} only has {balance} points, needs {reward['point_cost']}")
        c.execute('INSERT INTO redemptions(person_id,reward_id,redeemed_at) VALUES(?,?,?)',
                  (body.person_id, reward_id, int(time.time())))
    return {'redeemed': True}
