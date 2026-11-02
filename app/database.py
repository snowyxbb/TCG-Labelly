from collections.abc import Generator
from pathlib import Path
from typing import Annotated

from alembic import command
from alembic.config import Config
from fastapi import Depends
from sqlmodel import Session, create_engine

from app import models  # noqa: F401 -- importing models registers their tables on SQLModel.metadata

DB_FILE = Path("labelly.db")

engine = create_engine(
    f"sqlite:///{DB_FILE}",
    connect_args={"check_same_thread": False},  # FastAPI serves requests from different threads
)


def run_migrations() -> None:
    """Bring the database to the latest schema (applies pending migrations)."""
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    command.upgrade(config, "head")


def get_session() -> Generator[Session]:
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
