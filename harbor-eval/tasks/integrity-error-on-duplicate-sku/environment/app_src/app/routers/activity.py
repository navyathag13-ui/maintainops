from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ActivityEvent
from ..schemas import ActivityEventRead

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("", response_model=list[ActivityEventRead])
def list_activity(limit: int = Query(50, ge=1, le=500), db: Session = Depends(get_db)):
    events = (
        db.execute(select(ActivityEvent).order_by(ActivityEvent.occurred_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    return [ActivityEventRead.from_orm_event(e) for e in events]
