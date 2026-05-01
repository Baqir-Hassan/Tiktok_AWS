from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


settings = get_settings()


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, future=True, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models import credit_adjustment, job, job_log, user, video  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_user_auth_columns()


def _ensure_user_auth_columns() -> None:
    inspector = inspect(engine)
    existing_columns = {column["name"] for column in inspector.get_columns("users")}
    statements: list[str] = []

    if "email_verified" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT 0")
    if "verification_token_hash" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN verification_token_hash VARCHAR(255)")
    if "verification_token_expires_at" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN verification_token_expires_at DATETIME")
    if "verification_sent_at" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN verification_sent_at DATETIME")
    if "is_admin" not in existing_columns:
        statements.append("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
