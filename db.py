# /db.py
from contextlib import contextmanager
from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session

DB_PATH = Path("data/tracker.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def create_db_and_tables() -> None:
    # Ensure all model classes are registered with SQLModel.metadata
    # BEFORE create_all runs.
    from models import (  # noqa: F401
        Player,
        PlayerAlias,
        DiceSet,
        Game,
        GamePlayer,
        Roll,
        FinalScore,
    )
    SQLModel.metadata.create_all(engine)


@contextmanager
def get_session():
    with Session(engine) as session:
        yield session
