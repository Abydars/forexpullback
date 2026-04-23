from fastapi import APIRouter
from app.db.session import AsyncSessionLocal
from app.db.models import Session
from sqlalchemy import select

router = APIRouter(prefix="/api/sessions")

@router.get("")
async def get_sessions():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Session))
        return [{"id": s.id, "name": s.name, "start_time": s.start_time, "end_time": s.end_time, "timezone": s.tz, "days_mask": s.days_mask, "enabled": s.enabled} for s in result.scalars().all()]

@router.put("")
async def sync_sessions(sessions: list[dict]):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Session))
        existing = {s.id: s for s in result.scalars().all()}
        
        keep_ids = [s['id'] for s in sessions if s['id'] is not None]
        
        for e_id, e in existing.items():
            if e_id not in keep_ids:
                await db.delete(e)
                
        for s in sessions:
            if s['id'] is None:
                new_s = Session(name=s['name'], start_time=s['start_time'], end_time=s['end_time'], tz=s['timezone'], days_mask=s['days_mask'], enabled=s['enabled'])
                db.add(new_s)
            else:
                e = existing.get(s['id'])
                if e:
                    e.name = s['name']
                    e.start_time = s['start_time']
                    e.end_time = s['end_time']
                    e.tz = s['timezone']
                    e.days_mask = s['days_mask']
                    e.enabled = s['enabled']
        await db.commit()
    return {"status": "ok"}
