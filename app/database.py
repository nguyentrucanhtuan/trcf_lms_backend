from collections.abc import Generator
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy import event
from sqlmodel import Session, create_engine

BACKEND_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BACKEND_DIR / "lms.db"
SQLITE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLITE_URL,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _enable_sqlite_fk(dbapi_conn, _record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def run_migrations() -> None:
    """Apply pending Alembic migrations. Called on app startup."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
