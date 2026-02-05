"""Database connection and session management."""

from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from contextlib import contextmanager

from .config import get_settings, DATA_DIR


Base = declarative_base()


def get_engine():
    """Create database engine."""
    settings = get_settings()
    db_url = settings.database_url

    # Handle relative SQLite paths
    if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////"):
        # Relative path - make it relative to project root
        db_path = db_url.replace("sqlite:///", "")
        full_path = DATA_DIR.parent / db_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        db_url = f"sqlite:///{full_path}"

    return create_engine(
        db_url,
        echo=False,  # Set to True for SQL debugging
        connect_args={"check_same_thread": False} if "sqlite" in db_url else {}
    )


def get_session_factory():
    """Create session factory."""
    engine = get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


@contextmanager
def get_db_session() -> Session:
    """Context manager for database sessions."""
    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db():
    """Initialize the database (create all tables)."""
    # Import models to register them with Base
    from .models import lead, outreach, activity

    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    print(f"Database initialized at: {engine.url}")


def reset_db():
    """Reset the database (drop and recreate all tables)."""
    from .models import lead, outreach, activity

    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("Database reset complete.")
