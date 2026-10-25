
import hashlib
import json

from app.database import SessionLocal
from app.models import AuditLog


def calculate_event_hash(event: AuditLog) -> str:
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

    return hashlib.sha256(
        ((event.previous_hash or "") + serialized).encode("utf-8")
    ).hexdigest()


def verify_audit_chain() -> bool:
    db = SessionLocal()

    try:
        events = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
        expected_previous_hash = None

        for event in events:
            if event.previous_hash != expected_previous_hash:
                print(f"CHAIN BROKEN at audit event ID {event.id}: previous hash mismatch")
                return False

            expected_hash = calculate_event_hash(event)

            if event.event_hash != expected_hash:
                print(f"CHAIN BROKEN at audit event ID {event.id}: event hash mismatch")
                return False

            expected_previous_hash = event.event_hash

        print(f"Audit chain verified: {len(events)} event(s).")
        return True
    finally:
        db.close()


if __name__ == "__main__":
    if not verify_audit_chain():
        raise SystemExit(1)
