
import hashlib
import json

from app.database import SessionLocal
from app.models import AuditLog


def calculate_event_hash(event, previous_hash):
    payload = {
        "occurred_at": event.occurred_at.isoformat(),
        "actor_user_id": event.actor_user_id,
        "document_id": event.document_id,
        "action": event.action,
        "result": event.result,
        "reason": event.reason,
        "ip_address": event.ip_address,
        "details": event.details or {},
        "previous_hash": previous_hash,
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return hashlib.sha256(
        ((previous_hash or "") + serialized).encode("utf-8")
    ).hexdigest()


def verify_audit_chain():
    with SessionLocal() as db:
        events = db.query(AuditLog).order_by(AuditLog.id.asc()).all()

        if not events:
            print("No audit events found.")
            return

        previous_hash = None
        errors = []

        for event in events:
            if event.previous_hash != previous_hash:
                errors.append(
                    f"Event {event.id}: previous_hash does not match."
                )

            expected_hash = calculate_event_hash(event, previous_hash)

            if event.event_hash != expected_hash:
                errors.append(
                    f"Event {event.id}: event_hash does not match."
                )

            # Continue with the recorded hash to check the stored chain links.
            previous_hash = event.event_hash

        if errors:
            print("AUDIT CHAIN VERIFICATION FAILED")
            for error in errors:
                print("-", error)
        else:
            print(f"AUDIT CHAIN VERIFIED: {len(events)} events checked.")


if __name__ == "__main__":
    verify_audit_chain()
