
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import AuditLog


def log_audit_event(
    db: Session,
    action: str,
    result: str,
    actor_user_id: int | None = None,
    document_id: int | None = None,
    reason: str | None = None,
    ip_address: str | None = None,
    details: dict | None = None,
) -> AuditLog:
    """Append an audit event with a SHA-256 hash-chain link."""

    if result not in {"allowed", "denied", "success", "failure"}:
        raise ValueError("Unsupported audit result.")

    previous = (
        db.query(AuditLog)
        .order_by(AuditLog.id.desc())
        .first()
    )

    previous_hash = previous.event_hash if previous else None
    occurred_at = datetime.now(timezone.utc)
    event_details = details or {}

    # Canonical serialization makes the hash reproducible.
    payload = {
        "occurred_at": occurred_at.isoformat(),
        "actor_user_id": actor_user_id,
        "document_id": document_id,
        "action": action,
        "result": result,
        "reason": reason,
        "ip_address": ip_address,
        "details": event_details,
        "previous_hash": previous_hash,
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    event_hash = hashlib.sha256(
        ((previous_hash or "") + serialized).encode("utf-8")
    ).hexdigest()

    event = AuditLog(
        occurred_at=occurred_at,
        actor_user_id=actor_user_id,
        document_id=document_id,
        action=action,
        result=result,
        reason=reason,
        ip_address=ip_address,
        details=event_details,
        previous_hash=previous_hash,
        event_hash=event_hash,
    )

    try:
        db.add(event)
        db.commit()
        db.refresh(event)
    except Exception:
        db.rollback()
        raise

    return event

def verify_audit_chain(db: Session) -> bool:
    """Return True if every audit event and hash-chain link is valid."""

    events = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
    previous_hash = None

    for event in events:
        payload = {
            "occurred_at": event.occurred_at.isoformat(),
            "actor_user_id": event.actor_user_id,
            "document_id": event.document_id,
            "action": event.action,
            "result": event.result,
            "reason": event.reason,
            "ip_address": event.ip_address,
            "details": event.details or {},
            "previous_hash": event.previous_hash,
        }

        if event.previous_hash != previous_hash:
            return False

        serialized = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        expected_hash = hashlib.sha256(
            ((previous_hash or "") + serialized).encode("utf-8")
        ).hexdigest()

        if event.event_hash != expected_hash:
            return False

        previous_hash = event.event_hash

    return True

def verify_audit_chain_details(db: Session) -> dict:
    """Verify the audit chain and report the first invalid event."""

    events = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
    previous_hash = None

    for event in events:
        if event.previous_hash != previous_hash:
            return {
                "valid": False,
                "first_broken_event_id": event.id,
                "reason": "Previous hash does not match.",
            }

        payload = {
            "occurred_at": event.occurred_at.isoformat(),
            "actor_user_id": event.actor_user_id,
            "document_id": event.document_id,
            "action": event.action,
            "result": event.result,
            "reason": event.reason,
            "ip_address": event.ip_address,
            "details": event.details or {},
            "previous_hash": event.previous_hash,
        }

        serialized = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

        expected_hash = hashlib.sha256(
            ((previous_hash or "") + serialized).encode("utf-8")
        ).hexdigest()

        if event.event_hash != expected_hash:
            return {
                "valid": False,
                "first_broken_event_id": event.id,
                "reason": "Event hash does not match.",
            }

        previous_hash = event.event_hash

    return {
        "valid": True,
        "first_broken_event_id": None,
        "reason": None,
    }
