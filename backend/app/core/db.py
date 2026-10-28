from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@event.listens_for(engine, "connect")
def _enable_sqlite_fk(dbapi_conn, _record):
    if settings.database_url.startswith("sqlite"):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")


def init_db() -> None:
    from app import models  # noqa: F401  (register tables)

    from app.core import migrate

    migrate.backup_before_new_tables(engine, set(Base.metadata.tables))
    Base.metadata.create_all(engine)
    migrate.upgrade(engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
