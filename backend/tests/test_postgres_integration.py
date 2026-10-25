
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def get_test_database_url():
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        pytest.skip("Set DATABASE_URL to run PostgreSQL integration tests.")

    url = make_url(database_url)

    if url.get_backend_name() != "postgresql":
        pytest.fail("Integration tests require PostgreSQL.")

    if url.database != "trustvault_test":
        pytest.fail("Integration tests must use trustvault_test.")

    return database_url


def test_postgres_test_database_connection():
    engine = create_engine(get_test_database_url())

    try:
        with engine.connect() as connection:
            database_name = connection.execute(
                text("SELECT current_database()")
            ).scalar_one()

        assert database_name == "trustvault_test"
    finally:
        engine.dispose()


def test_postgres_can_write_and_verify_audit_event():
    # Import application modules only after validating the test database URL.
    from app.database import SessionLocal
    from app.audit import log_audit_event, verify_audit_chain
    from app.models import AuditLog

    db = SessionLocal()

    try:
        event = log_audit_event(
            db=db,
            action="integration.test",
            result="success",
            reason="PostgreSQL integration test",
            details={"test": True},
        )

        saved = (
            db.query(AuditLog)
            .filter(AuditLog.id == event.id)
            .first()
        )

        assert saved is not None
        assert saved.action == "integration.test"
        assert saved.event_hash
        assert verify_audit_chain(db) is True
    finally:
        db.close()
