import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://maintainops:maintainops@localhost:5432/maintainops",
)

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    """Commit-on-success, rollback-on-exception. Routes just mutate objects
    via the ORM and let the request boundary decide the transaction outcome
    -- if a route (or a logic-layer function it calls) raises, nothing it
    touched gets persisted.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
