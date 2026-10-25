from datetime import datetime, timezone
import hashlib
import uuid
import zipfile
from io import BytesIO
from pathlib import PurePath
from urllib.parse import quote
from sqlalchemy import or_
import magic
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.responses import Response

from app.audit import log_audit_event
from app.database import get_db
from app.dependencies import get_current_user
from app.encryption import EncryptionError, decrypt_file, encrypt_file
from app.models import Document, DocumentGrant, User, UserRole
from app.permissions import Action, can_access
from app.storage import (
    delete_encrypted_file,
    read_encrypted_file,
    save_encrypted_file,
)

router = APIRouter(prefix="/documents", tags=["Documents"])

MAX_FILE_SIZE = 10 * 1024 * 1024

VALID_ACTIONS = {action.value for action in Action}

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".xlsx",
    ".png",
    ".jpg",
    ".jpeg",
    ".txt",
}


def request_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def get_document_or_404(db: Session, document_id: int) -> Document:
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.deleted_at.is_(None),
        )
        .first()
    )

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    return document


def validate_file_content(filename: str, content: bytes) -> str:
    """Validate the extension and actual content; return the stored MIME type."""
    extension = PurePath(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="File type is not allowed.",
        )

    detected_mime = magic.from_buffer(content[:8192], mime=True)

    if extension == ".pdf":
        valid = content.startswith(b"%PDF-") and detected_mime == "application/pdf"
        content_type = "application/pdf"

    elif extension in {".png", ".jpg", ".jpeg"}:
        if extension == ".png":
            valid = (
                content.startswith(b"\x89PNG\r\n\x1a\n")
                and detected_mime == "image/png"
            )
            content_type = "image/png"
        else:
            valid = (
                content.startswith(b"\xff\xd8\xff")
                and detected_mime == "image/jpeg"
            )
            content_type = "image/jpeg"

    elif extension in {".docx", ".xlsx"}:
        expected_member = (
            "word/document.xml"
            if extension == ".docx"
            else "xl/workbook.xml"
        )

        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                names = set(archive.namelist())
                valid = (
                    "[Content_Types].xml" in names
                    and expected_member in names
                    and detected_mime
                    in {"application/zip", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}
                )
        except (zipfile.BadZipFile, OSError):
            valid = False

        content_type = (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            if extension == ".docx"
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:  # .txt
        try:
            content.decode("utf-8")
            valid = detected_mime in {
                "text/plain",
                "application/x-empty",
                "inode/x-empty",
            }
        except UnicodeDecodeError:
            valid = False

        content_type = "text/plain"

    if not valid:
        raise HTTPException(
            status_code=400,
            detail="The file content does not match its extension or is invalid.",
        )

    return content_type


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_active or current_user.role != UserRole.OWNER:
        log_audit_event(
            db=db,
            action="document.upload",
            result="denied",
            actor_user_id=current_user.id,
            reason="owner_role_required",
            ip_address=request_ip(request),
        )
        raise HTTPException(
            status_code=403,
            detail="Only active owners can upload documents.",
        )

    original_filename = PurePath(file.filename or "").name

    if not original_filename or original_filename in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    # Read in chunks and stop as soon as the limit is exceeded.
    chunks = []
    total_size = 0

    try:
        while True:
            chunk = await file.read(1024 * 1024)

            if not chunk:
                break

            total_size += len(chunk)

            if total_size > MAX_FILE_SIZE:
                log_audit_event(
                    db=db,
                    action="document.upload",
                    result="denied",
                    actor_user_id=current_user.id,
                    reason="file_too_large",
                    ip_address=request_ip(request),
                    details={"filename": original_filename},
                )
                raise HTTPException(
                    status_code=413,
                    detail="Maximum file size is 10 MB.",
                )

            chunks.append(chunk)
    finally:
        await file.close()

    plaintext = b"".join(chunks)

    try:
        content_type = validate_file_content(original_filename, plaintext)
    except HTTPException as exc:
        log_audit_event(
            db=db,
            action="document.upload",
            result="denied",
            actor_user_id=current_user.id,
            reason="invalid_file",
            ip_address=request_ip(request),
            details={
                "filename": original_filename,
                "reason": str(exc.detail),
            },
        )
        raise

    encrypted = encrypt_file(plaintext)
    storage_key = f"{uuid.uuid4()}.enc"

    try:
        save_encrypted_file(storage_key, encrypted.ciphertext)

        document = Document(
            owner_id=current_user.id,
            original_filename=original_filename,
            storage_key=storage_key,
            content_type=content_type,
            size_bytes=len(plaintext),
            sha256=hashlib.sha256(plaintext).hexdigest(),
            wrapped_key=encrypted.wrapped_key,
        )

        db.add(document)
        db.commit()
        db.refresh(document)

    except Exception:
        db.rollback()
        try:
            delete_encrypted_file(storage_key)
        except OSError:
            pass
        raise

    log_audit_event(
        db=db,
        action="document.upload",
        result="success",
        actor_user_id=current_user.id,
        document_id=document.id,
        ip_address=request_ip(request),
        details={"size_bytes": len(plaintext), "content_type": content_type},
    )

    return {
        "message": "Document uploaded and encrypted successfully.",
        "document": {
            "id": document.id,
            "filename": document.original_filename,
            "content_type": document.content_type,
            "size_bytes": document.size_bytes,
            "sha256": document.sha256,
        },
    }


@router.get("")
def list_documents(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Document).filter(
        Document.deleted_at.is_(None)
    )

    # Owners can see only their own documents and documents
    # explicitly shared with them.
    if current_user.role == UserRole.OWNER:
        query = query.outerjoin(
            DocumentGrant,
            DocumentGrant.document_id == Document.id,
        ).filter(
            or_(
                Document.owner_id == current_user.id,
                DocumentGrant.user_id == current_user.id,
            )
        )

    else:
        # Other users can see only documents explicitly shared with them.
        query = query.join(
            DocumentGrant,
            DocumentGrant.document_id == Document.id,
        ).filter(
            DocumentGrant.user_id == current_user.id
        )

    documents = (
        query
        .distinct()
        .order_by(Document.id.desc())
        .all()
    )

    visible = []

    for document in documents:
        if can_access(
            db,
            current_user,
            document,
            Action.VIEW,
            request_ip(request),
        ):
            if document.owner_id == current_user.id:
                granted_permissions = ["view", "download"]
            else:
                grant = (
                    db.query(DocumentGrant)
                    .filter(
                        DocumentGrant.document_id == document.id,
                        DocumentGrant.user_id == current_user.id,
                    )
                    .first()
                )
                granted_permissions = list(grant.permissions or []) if grant else []

            visible.append(
                {
                    "id": document.id,
                    "filename": document.original_filename,
                    "content_type": document.content_type,
                    "size_bytes": document.size_bytes,
                    "created_at": document.created_at,
                    "permissions": granted_permissions,
                }
            )

    return {"documents": visible}


@router.get("/{document_id}")
def get_document_metadata(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_document_or_404(db, document_id)

    if not can_access(
        db, current_user, document, Action.VIEW, request_ip(request)
    ):
        raise HTTPException(status_code=404, detail="Document not found.")

    return {
        "id": document.id,
        "filename": document.original_filename,
        "content_type": document.content_type,
        "size_bytes": document.size_bytes,
        "sha256": document.sha256,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
    }


@router.get("/{document_id}/view")
def view_document(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a safe browser-previewable file only when VIEW permission is granted."""
    document = get_document_or_404(db, document_id)

    if not can_access(
        db, current_user, document, Action.VIEW, request_ip(request)
    ):
        raise HTTPException(status_code=404, detail="Document not found.")

    # Only serve formats that browsers can render without opening arbitrary active content.
    safe_preview_types = {
        "application/pdf",
        "image/png",
        "image/jpeg",
        "text/plain",
    }
    if document.content_type not in safe_preview_types:
        raise HTTPException(
            status_code=415,
            detail="In-app preview currently supports PDF, PNG, JPEG, and TXT files only.",
        )

    if not document.wrapped_key:
        raise HTTPException(
            status_code=500,
            detail="Document encryption metadata is missing.",
        )

    try:
        ciphertext = read_encrypted_file(document.storage_key)
        plaintext = decrypt_file(ciphertext, document.wrapped_key)
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Encrypted document file is missing from storage.",
        )
    except (EncryptionError, ValueError):
        raise HTTPException(status_code=500, detail="Document could not be decrypted.")

    actual_hash = hashlib.sha256(plaintext).hexdigest()
    if actual_hash != document.sha256:
        raise HTTPException(status_code=500, detail="Document integrity check failed.")

    log_audit_event(
        db=db,
        action="document.view",
        result="success",
        actor_user_id=current_user.id,
        document_id=document.id,
        ip_address=request_ip(request),
    )

    safe_filename = quote(document.original_filename, safe="")
    return Response(
        content=plaintext,
        media_type=document.content_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{safe_filename}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_document_or_404(db, document_id)

    if not can_access(
        db, current_user, document, Action.DOWNLOAD, request_ip(request)
    ):
        raise HTTPException(status_code=404, detail="Document not found.")

    if not document.wrapped_key:
        log_audit_event(
            db=db,
            action="document.download",
            result="failure",
            actor_user_id=current_user.id,
            document_id=document.id,
            reason="missing_wrapped_key",
            ip_address=request_ip(request),
        )
        raise HTTPException(
            status_code=500,
            detail="Document encryption metadata is missing.",
        )

    try:
        ciphertext = read_encrypted_file(document.storage_key)
        plaintext = decrypt_file(ciphertext, document.wrapped_key)
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail="Encrypted document file is missing from storage.",
        )
    except (EncryptionError, ValueError):
        log_audit_event(
            db=db,
            action="document.download",
            result="failure",
            actor_user_id=current_user.id,
            document_id=document.id,
            reason="decryption_failed",
            ip_address=request_ip(request),
        )
        raise HTTPException(
            status_code=500,
            detail="Document could not be decrypted.",
        )

    actual_hash = hashlib.sha256(plaintext).hexdigest()

    if actual_hash != document.sha256:
        log_audit_event(
            db=db,
            action="document.download",
            result="failure",
            actor_user_id=current_user.id,
            document_id=document.id,
            reason="integrity_check_failed",
            ip_address=request_ip(request),
        )
        raise HTTPException(
            status_code=500,
            detail="Document integrity check failed.",
        )

    log_audit_event(
        db=db,
        action="document.download",
        result="success",
        actor_user_id=current_user.id,
        document_id=document.id,
        ip_address=request_ip(request),
    )

    safe_filename = quote(document.original_filename, safe="")
    return Response(
        content=plaintext,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"download\"; "
                f"filename*=UTF-8''{safe_filename}"
            ),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


class GrantRequest(BaseModel):
    user_id: int
    permissions: list[str] = Field(min_length=1)


@router.post("/{document_id}/grants", status_code=status.HTTP_201_CREATED)
def grant_document_permissions(
    document_id: int,
    payload: GrantRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_document_or_404(db, document_id)

    if document.owner_id != current_user.id:
        log_audit_event(
            db=db,
            action="document.grant",
            result="denied",
            actor_user_id=current_user.id,
            document_id=document.id,
            reason="owner_only",
            ip_address=request_ip(request),
        )
        raise HTTPException(status_code=404, detail="Document not found.")

    if len(set(payload.permissions)) != len(payload.permissions) or not set(
        payload.permissions
    ).issubset(VALID_ACTIONS):
        raise HTTPException(
            status_code=400,
            detail=f"Permissions must be selected from {sorted(VALID_ACTIONS)}.",
        )

    target_user = db.query(User).filter(User.id == payload.user_id).first()

    if (
        target_user is None
        or not target_user.is_active
        or target_user.id == current_user.id
    ):
        raise HTTPException(
            status_code=400,
            detail="Target user is invalid, inactive, or is the document owner.",
        )

    grant = (
        db.query(DocumentGrant)
        .filter(
            DocumentGrant.document_id == document.id,
            DocumentGrant.user_id == target_user.id,
        )
        .first()
    )

    if grant is None:
        grant = DocumentGrant(
            document_id=document.id,
            user_id=target_user.id,
            permissions=payload.permissions,
            granted_by=current_user.id,
        )
        db.add(grant)
    else:
        grant.permissions = payload.permissions
        grant.granted_by = current_user.id

    db.commit()
    db.refresh(grant)

    log_audit_event(
        db=db,
        action="document.grant",
        result="success",
        actor_user_id=current_user.id,
        document_id=document.id,
        ip_address=request_ip(request),
        details={
            "target_user_id": target_user.id,
            "permissions": payload.permissions,
        },
    )

    return {
        "message": "Permissions saved.",
        "document_id": document.id,
        "user_id": target_user.id,
        "permissions": grant.permissions,
    }


@router.delete("/{document_id}/grants/{user_id}")
def revoke_document_permissions(
    document_id: int,
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_document_or_404(db, document_id)

    if document.owner_id != current_user.id:
        log_audit_event(
            db=db,
            action="document.revoke",
            result="denied",
            actor_user_id=current_user.id,
            document_id=document.id,
            reason="owner_only",
            ip_address=request_ip(request),
        )
        raise HTTPException(status_code=404, detail="Document not found.")

    grant = (
        db.query(DocumentGrant)
        .filter(
            DocumentGrant.document_id == document.id,
            DocumentGrant.user_id == user_id,
        )
        .first()
    )

    if grant is None:
        log_audit_event(
            db=db,
            action="document.revoke",
            result="denied",
            actor_user_id=current_user.id,
            document_id=document.id,
            reason="grant_not_found",
            ip_address=request_ip(request),
            details={"target_user_id": user_id},
        )
        raise HTTPException(status_code=404, detail="Permission grant not found.")

    db.delete(grant)
    db.commit()

    log_audit_event(
        db=db,
        action="document.revoke",
        result="success",
        actor_user_id=current_user.id,
        document_id=document.id,
        ip_address=request_ip(request),
        details={"target_user_id": user_id},
    )

    return {"message": "Permissions revoked."}

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_document_or_404(db, document_id)

    # Only the document owner can delete it.
    if document.owner_id != current_user.id:
        log_audit_event(
            db=db,
            action="document.delete",
            result="denied",
            actor_user_id=current_user.id,
            document_id=document.id,
            reason="owner_only",
            ip_address=request_ip(request),
        )
        raise HTTPException(status_code=404, detail="Document not found.")

    # Preserve the storage key before updating the record.
    storage_key = document.storage_key
    document.deleted_at = datetime.now(timezone.utc)
    document.wrapped_key = None

    # Commit the soft deletion before deleting the physical file.
    try:
        db.commit()
    except Exception:
        db.rollback()
        try:
            log_audit_event(
                db=db,
                action="document.delete",
                result="failure",
                actor_user_id=current_user.id,
                document_id=document.id,
                reason="database_update_failed",
                ip_address=request_ip(request),
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail="Document deletion could not be completed.",
        )

    # The document is now inaccessible, even if storage cleanup fails.
    try:
        delete_encrypted_file(storage_key)
    except (OSError, ValueError):
        try:
            log_audit_event(
                db=db,
                action="document.delete",
                result="failure",
                actor_user_id=current_user.id,
                document_id=document.id,
                reason="storage_cleanup_failed",
                ip_address=request_ip(request),
            )
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail="Document was disabled, but storage cleanup failed.",
        )

    log_audit_event(
        db=db,
        action="document.delete",
        result="success",
        actor_user_id=current_user.id,
        document_id=document.id,
        ip_address=request_ip(request),
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.put("/{document_id}/edit")
async def edit_document(
    document_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    document = get_document_or_404(db, document_id)

    if not can_access(
        db, current_user, document, Action.EDIT, request_ip(request)
    ):
        raise HTTPException(status_code=404, detail="Document not found.")

    original_filename = PurePath(file.filename or "").name
    if not original_filename or original_filename in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    chunks = []
    total_size = 0

    try:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break

            total_size += len(chunk)
            if total_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=413,
                    detail="Maximum file size is 10 MB.",
                )

            chunks.append(chunk)
    finally:
        await file.close()

    plaintext = b"".join(chunks)

    try:
        content_type = validate_file_content(original_filename, plaintext)
    except HTTPException as exc:
        log_audit_event(
            db=db,
            action="document.edit",
            result="denied",
            actor_user_id=current_user.id,
            document_id=document.id,
            reason="invalid_file",
            ip_address=request_ip(request),
        )
        raise exc

    encrypted = encrypt_file(plaintext)
    new_storage_key = f"{uuid.uuid4()}.enc"
    old_storage_key = document.storage_key

    try:
        save_encrypted_file(new_storage_key, encrypted.ciphertext)

        document.original_filename = original_filename
        document.storage_key = new_storage_key
        document.content_type = content_type
        document.size_bytes = len(plaintext)
        document.sha256 = hashlib.sha256(plaintext).hexdigest()
        document.wrapped_key = encrypted.wrapped_key

        db.commit()
        db.refresh(document)

    except Exception:
        db.rollback()
        try:
            delete_encrypted_file(new_storage_key)
        except (OSError, ValueError):
            pass
        raise

    # The database now points to the new encrypted file.
    # Failure to remove the old file must not undo the successful edit.
    try:
        delete_encrypted_file(old_storage_key)
    except (OSError, ValueError):
        log_audit_event(
            db=db,
            action="document.edit",
            result="failure",
            actor_user_id=current_user.id,
            document_id=document.id,
            reason="old_file_cleanup_failed",
            ip_address=request_ip(request),
        )

    log_audit_event(
        db=db,
        action="document.edit",
        result="success",
        actor_user_id=current_user.id,
        document_id=document.id,
        ip_address=request_ip(request),
        details={
            "size_bytes": len(plaintext),
            "content_type": content_type,
        },
    )

    return {
        "message": "Document updated successfully.",
        "document": {
            "id": document.id,
            "filename": document.original_filename,
            "content_type": document.content_type,
            "size_bytes": document.size_bytes,
            "sha256": document.sha256,
        },
    }
