"""
Database session management.
"""
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.models import Base

# Get database URL from environment or default to SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./clinical_demo.db")

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize database by creating all tables and triggers."""
    Base.metadata.create_all(bind=engine)

    # Create triggers for auto-updating updated_at column
    # Only applicable for SQLite databases
    if "sqlite" in DATABASE_URL:
        from sqlalchemy import text

        tables = ["trials", "sites", "trial_sites", "protocol_versions", "audit_logs"]

        with engine.connect() as conn:
            for table in tables:
                # Drop trigger if it exists (for idempotency)
                conn.execute(text(f"DROP TRIGGER IF EXISTS update_{table}_timestamp"))

                # Create trigger to update updated_at on any UPDATE
                trigger_sql = f"""
                CREATE TRIGGER update_{table}_timestamp
                AFTER UPDATE ON {table}
                FOR EACH ROW
                BEGIN
                    UPDATE {table} SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
                END;
                """
                conn.execute(text(trigger_sql))

            conn.commit()


def get_session() -> Session:
    """Get a new database session. Caller is responsible for closing."""
    return SessionLocal()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Provide a transactional scope for database operations.

    Usage:
        with session_scope() as session:
            # perform database operations
            pass
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
