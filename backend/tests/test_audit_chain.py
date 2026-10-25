
import hashlib
import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.audit import verify_audit_chain, verify_audit_chain_details
from app.models import AuditLog


def test_empty_audit_chain_is_valid():
    db = MagicMock()
    db.query.return_value.order_by.return_value.all.return_value = []

    assert verify_audit_chain(db) is True


def test_tampered_audit_event_is_detected():
    event = MagicMock(spec=AuditLog)
    event.id = 1
    event.occurred_at = datetime.now(timezone.utc)
    event.actor_user_id = 1
    event.document_id = None
    event.action = "document.view"
    event.result = "success"
    event.reason = None
    event.ip_address = None
    event.details = {}
    event.previous_hash = None
    event.event_hash = "incorrect-hash"

    db = MagicMock()
    db.query.return_value.order_by.return_value.all.return_value = [event]

    assert verify_audit_chain(db) is False


def test_broken_previous_hash_is_detected():
    first = MagicMock(spec=AuditLog)
    first.id = 10
    first.occurred_at = datetime.now(timezone.utc)
    first.actor_user_id = 1
    first.document_id = None
    first.action = "login"
    first.result = "success"
    first.reason = None
    first.ip_address = None
    first.details = {}
    first.previous_hash = None

    # Give the first event a valid hash.
    first_payload = {
        "occurred_at": first.occurred_at.isoformat(),
        "actor_user_id": first.actor_user_id,
        "document_id": first.document_id,
        "action": first.action,
        "result": first.result,
        "reason": first.reason,
        "ip_address": first.ip_address,
        "details": first.details,
        "previous_hash": None,
    }

    first_serialized = json.dumps(
        first_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    first.event_hash = hashlib.sha256(
        first_serialized.encode("utf-8")
    ).hexdigest()

    # The second event deliberately points to the wrong previous hash.
    second = MagicMock(spec=AuditLog)
    second.id = 11
    second.occurred_at = datetime.now(timezone.utc)
    second.actor_user_id = 1
    second.document_id = None
    second.action = "document.view"
    second.result = "success"
    second.reason = None
    second.ip_address = None
    second.details = {}
    second.previous_hash = "wrong-previous-hash"
    second.event_hash = "b" * 64

    db = MagicMock()
    db.query.return_value.order_by.return_value.all.return_value = [
        first,
        second,
    ]

    result = verify_audit_chain_details(db)

    assert result["valid"] is False
    assert result["first_broken_event_id"] == 11
    assert result["reason"] == "Previous hash does not match."
