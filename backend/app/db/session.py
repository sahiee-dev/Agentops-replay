from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

try:
    from backend.app.config import settings
except ImportError:
    from app.config import settings

# Database URL — sourced from settings.database_url per TRD §4.2
DATABASE_URL = settings.database_url

# SQLite doesn't support pool_size/max_overflow/pool_recycle
_is_sqlite = DATABASE_URL.startswith("sqlite")

_engine_kwargs: dict = {"pool_pre_ping": True}
if not _is_sqlite:
    _engine_kwargs.update(pool_recycle=300, pool_size=10, max_overflow=20)
else:
    from sqlalchemy.pool import StaticPool
    _engine_kwargs.update(
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

engine = create_engine(DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base with proper typing."""

    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
