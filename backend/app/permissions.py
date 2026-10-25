
from enum import Enum

from sqlalchemy.orm import Session

from app.audit import log_audit_event
from app.models import User, UserRole, Document, DocumentGrant


class Action(str, Enum):
    VIEW = "view"
    DOWNLOAD = "download"
    EDIT = "edit"
    DELETE = "delete"
    SHARE = "share"


def can_access(
    db: Session,
    user: User,
    document: Document,
    action: Action | str,
    ip_address: str | None = None,
) -> bool:
    """Check role and document permissions, then audit the decision."""

    requested_action = (
        action.value if isinstance(action, Action) else str(action)
    )

    allowed_actions = {item.value for item in Action}
    allowed = False
    reason = None

    if requested_action not in allowed_actions:
        reason = "invalid_action"
    elif not user.is_active:
        reason = "inactive_user"
    elif document.deleted_at is not None:
        reason = "document_deleted"
    elif user.role == UserRole.ADMIN:
        # Admins manage the platform, not private documents by default.
        reason = "admin_document_access_not_granted"
    elif document.owner_id == user.id:
        allowed = True
        reason = "document_owner"
    elif user.role == UserRole.VIEWER and requested_action in {
        Action.EDIT.value,
        Action.DELETE.value,
        Action.SHARE.value,
    }:
        reason = "viewer_read_only"
    else:
        grant = (
            db.query(DocumentGrant)
            .filter(
                DocumentGrant.document_id == document.id,
                DocumentGrant.user_id == user.id,
            )
            .first()
        )

        permissions = (grant.permissions or []) if grant else []

        if requested_action in permissions:
            allowed = True
            reason = "explicit_grant"
        else:
            reason = "missing_permission"

    log_audit_event(
        db=db,
        action=f"document.{requested_action}",
        result="allowed" if allowed else "denied",
        actor_user_id=user.id,
        document_id=document.id,
        reason=reason,
        ip_address=ip_address,
        details={"requested_action": requested_action},
    )

    return allowed
