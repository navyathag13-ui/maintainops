import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from .database import Base, engine
from .logic import (
    DuplicatePartInRequestError,
    EmployeeNotFoundError,
    EquipmentAlreadyCheckedOutError,
    EquipmentNotFoundError,
    InsufficientStockError,
    InvalidQuantityError,
    LoanAlreadyReturnedError,
    LoanNotFoundError,
    PartNotFoundError,
    ProjectNotFoundError,
)
from .routers import (
    activity,
    alerts,
    dashboard,
    employees,
    equipment,
    equipment_loans,
    maintenance_logs,
    parts,
    projects,
    reports,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # No migration tool at this project's scale -- create_all is idempotent
    # and enough for a small internal tool. Swap for Alembic if this grows.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="MaintainOps API",
    description="Equipment maintenance tracking and spare-parts inventory.",
    version="1.0.0",
    lifespan=lifespan,
)

allowed_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(EquipmentNotFoundError)
async def equipment_not_found_handler(request: Request, exc: EquipmentNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(PartNotFoundError)
async def part_not_found_handler(request: Request, exc: PartNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(InsufficientStockError)
async def insufficient_stock_handler(request: Request, exc: InsufficientStockError):
    return JSONResponse(
        status_code=400,
        content={
            "detail": str(exc),
            "shortfalls": [
                {"part_id": s.part_id, "requested": s.requested, "available": s.available}
                for s in exc.shortfalls
            ],
        },
    )


@app.exception_handler(InvalidQuantityError)
async def invalid_quantity_handler(request: Request, exc: InvalidQuantityError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(DuplicatePartInRequestError)
async def duplicate_part_handler(request: Request, exc: DuplicatePartInRequestError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(LoanNotFoundError)
async def loan_not_found_handler(request: Request, exc: LoanNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ProjectNotFoundError)
async def project_not_found_handler(request: Request, exc: ProjectNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(EmployeeNotFoundError)
async def employee_not_found_handler(request: Request, exc: EmployeeNotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


# 409 Conflict, not 400: the request itself is well-formed, it's the
# equipment/loan's current state that makes it invalid right now.
@app.exception_handler(EquipmentAlreadyCheckedOutError)
async def equipment_already_checked_out_handler(request: Request, exc: EquipmentAlreadyCheckedOutError):
    return JSONResponse(
        status_code=409,
        content={"detail": str(exc), "active_loan_id": exc.active_loan_id},
    )


@app.exception_handler(LoanAlreadyReturnedError)
async def loan_already_returned_handler(request: Request, exc: LoanAlreadyReturnedError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


# Catches what the typed logic.py exceptions above don't: a duplicate SKU,
# or deleting a part that still has maintenance history referencing it.
# Without this, either surfaces as a raw 500 with a stack trace -- the
# thing this app's error handling is otherwise careful to never do.
@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={
            "detail": "This request conflicts with existing data (e.g. a duplicate value, "
            "or a record that's still referenced elsewhere)."
        },
    )


app.include_router(equipment.router)
app.include_router(equipment_loans.router)
app.include_router(parts.router)
app.include_router(maintenance_logs.router)
app.include_router(alerts.router)
app.include_router(reports.router)
app.include_router(projects.router)
app.include_router(employees.router)
app.include_router(activity.router)
app.include_router(dashboard.router)


@app.get("/health")
def health():
    return {"status": "ok"}
