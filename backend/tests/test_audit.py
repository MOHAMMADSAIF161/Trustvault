
from app.database import SessionLocal
from app.audit import log_audit_event, verify_audit_chain
from app.models import AuditLog


def test_audit_event_is_saved_to_database():
    db = SessionLocal()

    try:
        # Add a first event if the audit table is empty.
        previous = (
            db.query(AuditLog)
            .order_by(AuditLog.id.desc())
            .first()
        )

        first_event_hash = previous.event_hash if previous else None

        event = log_audit_event(
            db=db,
            action="test.audit",
            result="success",
            reason="Hash chain verification test",
            details={"test": True},
        )

        saved = db.query(AuditLog).filter(
            AuditLog.id == event.id
        ).first()

        assert saved is not None
        assert saved.action == "test.audit"
        assert saved.event_hash

        # The new event must link to the preceding event, if one exists.
        assert saved.previous_hash == first_event_hash

        # Confirm the complete audit chain remains valid.
        assert verify_audit_chain(db) is True

    finally:
        db.close()
