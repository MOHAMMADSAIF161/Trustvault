import json
import os
from app.models import AuditLog, Document, User
import httpx
from datetime import date, datetime, time, timedelta, timezone

from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.audit import log_audit_event, verify_audit_chain_details
from app.database import get_db
from app.dependencies import get_current_user
from app.models import AuditLog, Document, User, UserRole

router = APIRouter(prefix="/admin", tags=["Administration"])


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return current_user


def user_to_dict(user: User) -> dict:
    created_at = getattr(user, "created_at", None)

    return {
        "id": user.id,
        "email": user.email,
        "role": user.role.value,
        "is_active": user.is_active,
        "created_at": created_at.isoformat() if created_at else None,
    }


def document_to_dict(document: Document, owner: User) -> dict:
    return {
        "id": document.id,
        "name": document.original_filename,
        "owner_id": document.owner_id,
        "owner_email": owner.email,
        "size_bytes": document.size_bytes,
        "content_type": document.content_type,
        "created_at": (
            document.created_at.isoformat()
            if document.created_at
            else None
        ),
        "updated_at": (
            document.updated_at.isoformat()
            if document.updated_at
            else None
        ),
        "deleted_at": (
            document.deleted_at.isoformat()
            if document.deleted_at
            else None
        ),
    }


# ---------------------------------------------------------
# 1. MANAGE USERS
# ---------------------------------------------------------

@router.get("/users")
def list_users(
    search: str | None = Query(default=None, max_length=255),
    role: str | None = Query(default=None),
    active: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = db.query(User)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(User.email.ilike(term))

    if role:
        valid_roles = {item.value for item in UserRole}
        if role not in valid_roles:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid role. Choose from: {', '.join(sorted(valid_roles))}.",
            )
        query = query.filter(User.role == UserRole(role))

    if active is not None:
        query = query.filter(User.is_active == active)

    total = query.count()
    users = (
        query.order_by(User.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "users": [user_to_dict(user) for user in users],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.patch("/users/{user_id}/disable")
def disable_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == admin.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot disable your own account.",
        )

    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    if not user.is_active:
        raise HTTPException(
            status_code=409,
            detail="User is already disabled.",
        )

    user.is_active = False

    try:
        db.flush()
        log_audit_event(
            db=db,
            action="user.disable",
            result="success",
            actor_user_id=admin.id,
            reason="administrator_disabled_user",
            details={
                "target_user_id": user.id,
                "target_email": user.email,
            },
        )
        db.commit()
        db.refresh(user)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not disable account and record the audit event.",
        ) from exc

    return {
        "message": "User disabled successfully.",
        **user_to_dict(user),
    }


@router.patch("/users/{user_id}/enable")
def enable_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")

    if user.is_active:
        raise HTTPException(
            status_code=409,
            detail="User is already active.",
        )

    user.is_active = True

    try:
        db.flush()
        log_audit_event(
            db=db,
            action="user.enable",
            result="success",
            actor_user_id=admin.id,
            reason="administrator_enabled_user",
            details={
                "target_user_id": user.id,
                "target_email": user.email,
            },
        )
        db.commit()
        db.refresh(user)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not enable account and record the audit event.",
        ) from exc

    return {
        "message": "User enabled successfully.",
        "user": user_to_dict(user),
    }


# ---------------------------------------------------------
# 2. VIEW DOCUMENT METADATA
# ---------------------------------------------------------

@router.get("/documents")
def list_all_documents(
    search: str | None = Query(default=None, max_length=255),
    owner: str | None = Query(default=None, max_length=255),
    category: str | None = Query(default=None, max_length=127),
    include_deleted: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    query = (
        db.query(Document, User)
        .join(User, Document.owner_id == User.id)
    )

    if not include_deleted:
        query = query.filter(Document.deleted_at.is_(None))

    if search and search.strip():
        query = query.filter(
            Document.original_filename.ilike(
                f"%{search.strip()}%"
            )
        )

    if owner and owner.strip():
        query = query.filter(
            User.email.ilike(f"%{owner.strip()}%")
        )

    if category and category.strip():
        query = query.filter(
            Document.content_type.ilike(f"%{category.strip()}%")
        )

    total = query.count()

    rows = (
        query.order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "documents": [
            document_to_dict(document, owner_user)
            for document, owner_user in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ---------------------------------------------------------
# 3. DELETE ANY DOCUMENT (SOFT DELETE)
# ---------------------------------------------------------

@router.delete("/documents/{document_id}")
def delete_document(
    document_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.deleted_at.is_(None),
        )
        .first()
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found or already deleted.",
        )

    deleted_at = datetime.now(timezone.utc)
    document.deleted_at = deleted_at

    try:
        db.flush()
        log_audit_event(
            db=db,
            action="document.delete",
            result="success",
            actor_user_id=admin.id,
            reason="administrator_deleted_document",
            details={
                "document_id": document.id,
                "document_name": document.original_filename,
                "owner_id": document.owner_id,
                "size_bytes": document.size_bytes,
                "deletion_type": "soft_delete",
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not delete document and record the audit event.",
        ) from exc

    return {
        "message": "Document deleted successfully.",
        "document_id": document_id,
        "deleted_at": deleted_at.isoformat(),
        "deletion_type": "soft_delete",
    }


# ---------------------------------------------------------
# 4. ADMIN DASHBOARD AND FILTERED ACTIVITY
# ---------------------------------------------------------

@router.get("/dashboard")
def get_admin_dashboard(
    search_name: str | None = Query(default=None, max_length=255),
    owner: str | None = Query(default=None, max_length=255),
    category: str | None = Query(default=None, max_length=127),
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=100, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=422,
            detail="date_from must be on or before date_to.",
        )

    total_documents = (
        db.query(func.count(Document.id))
        .filter(Document.deleted_at.is_(None))
        .scalar()
        or 0
    )

    total_users = db.query(func.count(User.id)).scalar() or 0

    active_users = (
        db.query(func.count(User.id))
        .filter(User.is_active.is_(True))
        .scalar()
        or 0
    )

    disabled_users = (
        db.query(func.count(User.id))
        .filter(User.is_active.is_(False))
        .scalar()
        or 0
    )

    recent_activities = db.query(func.count(AuditLog.id)).scalar() or 0

    permission_changes = (
        db.query(func.count(AuditLog.id))
        .filter(
            AuditLog.action.in_(
                [
                    "document.grant",
                    "document.revoke",
                    "user.disable",
                    "user.enable",
                ]
            )
        )
        .scalar()
        or 0
    )

    denied_actions = (
        db.query(func.count(AuditLog.id))
        .filter(
            func.lower(AuditLog.result).in_(
                ["denied", "blocked", "failure", "failed"]
            )
        )
        .scalar()
        or 0
    )

    query = (
        db.query(AuditLog, Document, User)
        .outerjoin(Document, AuditLog.document_id == Document.id)
        .outerjoin(User, Document.owner_id == User.id)
    )

    if search_name and search_name.strip():
        query = query.filter(
            Document.original_filename.ilike(
                f"%{search_name.strip()}%"
            )
        )

    if owner and owner.strip():
        query = query.filter(
            User.email.ilike(f"%{owner.strip()}%")
        )

    if category and category.strip():
        query = query.filter(
            Document.content_type.ilike(f"%{category.strip()}%")
        )

    if date_from:
        start = datetime.combine(
            date_from, time.min, tzinfo=timezone.utc
        )
        query = query.filter(AuditLog.occurred_at >= start)

    if date_to:
        next_day = date_to + timedelta(days=1)
        end = datetime.combine(
            next_day, time.min, tzinfo=timezone.utc
        )
        query = query.filter(AuditLog.occurred_at < end)

    total_filtered = query.count()

    rows = (
        query.order_by(AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    events = []

    for event, document, document_owner in rows:
        events.append(
            {
                "id": event.id,
                "occurred_at": (
                    event.occurred_at.isoformat()
                    if event.occurred_at
                    else None
                ),
                "actor_user_id": event.actor_user_id,
                "document_id": event.document_id,
                "action": event.action,
                "result": event.result,
                "reason": event.reason,
                "ip_address": event.ip_address,
                "details": event.details,
                "event_hash": event.event_hash,
                "document_name": (
                    document.original_filename if document else None
                ),
                "owner_email": (
                    document_owner.email if document_owner else None
                ),
                "category": (
                    document.content_type if document else None
                ),
            }
        )

    return {
        "summary": {
            "total_users": total_users,
            "active_users": active_users,
            "disabled_users": disabled_users,
            "total_documents": total_documents,
            "recent_activities": recent_activities,
            "permission_changes": permission_changes,
            "denied_actions": denied_actions,
        },
        "events": events,
        "total_filtered": total_filtered,
        "limit": limit,
        "offset": offset,
    }


# ---------------------------------------------------------
# 5. AUDIT LOGS
# ---------------------------------------------------------

@router.get("/audit")
def get_audit_logs(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    logs = (
        db.query(AuditLog)
        .order_by(AuditLog.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    return {
        "events": [
            {
                "id": event.id,
                "occurred_at": (
                    event.occurred_at.isoformat()
                    if event.occurred_at
                    else None
                ),
                "actor_user_id": event.actor_user_id,
                "document_id": event.document_id,
                "action": event.action,
                "result": event.result,
                "reason": event.reason,
                "ip_address": event.ip_address,
                "details": event.details,
                "event_hash": event.event_hash,
            }
            for event in logs
        ],
        "limit": limit,
        "offset": offset,
    }


# ---------------------------------------------------------
# 6. VERIFY AUDIT HASH CHAIN
# ---------------------------------------------------------

@router.get("/audit/verify")
def verify_audit_logs(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        return verify_audit_chain_details(db)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Audit verification failed. Check server logs.",
        ) from exc

class DashboardAssistantRequest(BaseModel):
    question: str = Field(min_length=2, max_length=500)


@router.post("/assistant")
def dashboard_assistant(
    payload: DashboardAssistantRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Answer questions using TrustVault admin dashboard data only."""

    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="Enter a question.")

    # Calculate facts directly from the database.
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_users = (
        db.query(func.count(User.id))
        .filter(User.is_active.is_(True))
        .scalar() or 0
    )
    disabled_users = (
        db.query(func.count(User.id))
        .filter(User.is_active.is_(False))
        .scalar() or 0
    )
    active_documents = (
        db.query(func.count(Document.id))
        .filter(Document.deleted_at.is_(None))
        .scalar() or 0
    )
    deleted_documents = (
        db.query(func.count(Document.id))
        .filter(Document.deleted_at.is_not(None))
        .scalar() or 0
    )
    total_events = db.query(func.count(AuditLog.id)).scalar() or 0

    recent = (
        db.query(AuditLog)
        .order_by(AuditLog.id.desc())
        .limit(15)
        .all()
    )

    recent_events = [
        {
            "time": event.occurred_at.isoformat()
            if event.occurred_at else None,
            "action": event.action,
            "result": event.result,
            "reason": event.reason,
            "document_id": event.document_id,
            "actor_user_id": event.actor_user_id,
            "details": event.details,
        }
        for event in recent
    ]

    dashboard_data = {
        "total_users": total_users,
        "active_users": active_users,
        "disabled_users": disabled_users,
        "active_documents": active_documents,
        "soft_deleted_documents": deleted_documents,
        "total_audit_events": total_events,
        "latest_audit_events": recent_events,
    }

    prompt = f"""

You are TrustVault's friendly Admin Dashboard assistant.

Talk naturally, politely, and conversationally.
Understand casual wording, greetings, and spelling mistakes.
Answer questions about dashboard statistics, users, documents,
and recent activities using the supplied live data.

Explain things in simple language. Be concise but helpful.
For greetings, respond warmly.
If asked something unrelated to TrustVault, gently guide the
conversation back to dashboard information.
Never invent facts or claim to perform actions.

Dashboard data:
{json.dumps(dashboard_data, ensure_ascii=False, default=str)}

Admin's message:
{question}

Your friendly response:

"""

    try:
        response = httpx.post(
            os.getenv(
                "OLLAMA_URL",
                "http://127.0.0.1:11434/api/generate",
            ),
            json={
                "model": os.getenv(
                    "OLLAMA_MODEL",
                    "llama3.2:latest",
                ),
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1},
            },
            timeout=60.0,
        )
        response.raise_for_status()
        answer = response.json().get("response", "").strip()

        if not answer:
            raise ValueError("Ollama returned an empty answer.")

        return {"answer": answer}

    except (httpx.HTTPError, ValueError, KeyError) as exc:
        print(f"TrustVault assistant error: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=503,
            detail=(
                "AI assistant is temporarily unavailable. "
                "Please check the backend terminal."
            ),
        ) from exc
