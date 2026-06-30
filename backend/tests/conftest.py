"""
Pytest configuration for backend tests.
Creates all tables before the test session begins so tests work
regardless of order.  The application no longer calls
``Base.metadata.create_all`` at import time (schema is owned by Alembic).
"""

from __future__ import annotations

import pytest

from app.db import Base, engine, SessionLocal
from app.models import Horse  # ensure all models are imported


@pytest.fixture(scope="session", autouse=True)
def create_test_db():
    """Create all tables once for the whole test session."""
    Base.metadata.create_all(bind=engine)
    # Ensure the seed horse (id=1) used by several tests exists
    db = SessionLocal()
    try:
        if not db.get(Horse, 1):
            db.add(Horse(id=1, name="Blaze"))
            db.commit()
    finally:
        db.close()
    yield
    # Tables are left intact so test runs can be inspected locally.
