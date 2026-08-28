from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..dashboard import get_dashboard_summary
from ..database import get_db
from ..schemas import (
    ActivityEventRead,
    DashboardSummaryRead,
    DueSoonRead,
    LocationCountRead,
    ProjectSummaryRead,
)
from .alerts import equipment_to_overdue_read, equipment_to_wear_limit_read, part_to_low_stock_read

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummaryRead)
def get_summary(db: Session = Depends(get_db)):
    summary = get_dashboard_summary(db)
    return DashboardSummaryRead(
        overdue_equipment=[equipment_to_overdue_read(e) for e in summary.overdue_equipment],
        low_stock_parts=[part_to_low_stock_read(p) for p in summary.low_stock_parts],
        discard_recommended=[equipment_to_wear_limit_read(e) for e in summary.discard_recommended],
        active_projects=[ProjectSummaryRead(**p.__dict__) for p in summary.active_projects],
        equipment_by_location=[
            LocationCountRead(location=l.location, count=l.count) for l in summary.equipment_by_location
        ],
        due_soon=[
            DueSoonRead(
                loan_id=d.loan_id,
                equipment_id=d.equipment_id,
                equipment_name=d.equipment_name,
                project_name=d.project_name,
                expected_return_at=d.expected_return_at,
                is_overdue_for_return=d.is_overdue_for_return,
            )
            for d in summary.due_soon
        ],
        recent_activity=[ActivityEventRead.from_orm_event(e) for e in summary.recent_activity],
    )
