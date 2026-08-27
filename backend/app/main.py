import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import Base, engine
from .logic import (
    DuplicatePartInRequestError,
    EquipmentNotFoundError,
    InsufficientStockError,
    InvalidQuantityError,
    PartNotFoundError,
)
from .routers import alerts, equipment, maintenance_logs, parts


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


app.include_router(equipment.router)
app.include_router(parts.router)
app.include_router(maintenance_logs.router)
app.include_router(alerts.router)


@app.get("/health")
def health():
    return {"status": "ok"}
