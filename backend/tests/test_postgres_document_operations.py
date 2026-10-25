
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.models import User, UserRole, Document, DocumentGrant


def test_postgres_document_and_permission_operations():
    db = SessionLocal()
    owner = None
    viewer = None
    document = None

    try:
        # Safety check before writing anything.
        database_name = db.execute(
            text("SELECT current_database()")
        ).scalar_one()

        assert database_name == "trustvault_test", (
            "Refusing to write outside trustvault_test."
        )

        unique_id = uuid4().hex

        # Create two real PostgreSQL users.
        owner = User(
            email=f"pg-owner-{unique_id}@test.local",
            password_hash="integration-test-hash",
            role=UserRole.OWNER,
            is_active=True,
        )
        viewer = User(
            email=f"pg-viewer-{unique_id}@test.local",
            password_hash="integration-test-hash",
            role=UserRole.VIEWER,
            is_active=True,
        )

        db.add_all([owner, viewer])
        db.flush()

        # Create a document owned by the first user.
        document = Document(
            owner_id=owner.id,
            original_filename="integration-test.txt",
            storage_key=f"{unique_id}.enc",
            content_type="text/plain",
            size_bytes=12,
            sha256="a" * 64,
            wrapped_key="integration-test-wrapped-key",
        )

        db.add(document)
        db.flush()

        document_id = document.id
        owner_id = owner.id
        viewer_id = viewer.id

        # Confirm the document persists and belongs to its owner.
        db.commit()

        saved_document = db.query(Document).filter(
            Document.id == document_id
        ).one()

        assert saved_document.owner_id == owner_id
        assert saved_document.original_filename == "integration-test.txt"

        # Grant the viewer read access.
        grant = DocumentGrant(
            document_id=document_id,
            user_id=viewer_id,
            permissions=["view"],
            granted_by=owner_id,
        )
        db.add(grant)
        db.commit()

        saved_grant = db.query(DocumentGrant).filter(
            DocumentGrant.document_id == document_id,
            DocumentGrant.user_id == viewer_id,
        ).one()

        assert "view" in saved_grant.permissions

        # Revoke access and confirm the grant is gone.
        db.delete(saved_grant)
        db.commit()

        remaining_grant = db.query(DocumentGrant).filter(
            DocumentGrant.document_id == document_id,
            DocumentGrant.user_id == viewer_id,
        ).first()

        assert remaining_grant is None

        # Soft-delete the document and verify normal listings exclude it.
        saved_document = db.query(Document).filter(
            Document.id == document_id
        ).one()

        saved_document.deleted_at = datetime.now(timezone.utc)
        db.commit()

        visible_document = db.query(Document).filter(
            Document.id == document_id,
            Document.deleted_at.is_(None),
        ).first()

        assert visible_document is None

    finally:
        # Clean up only this test's records.
        try:
            db.rollback()

            if document is not None and document.id is not None:
                db.query(DocumentGrant).filter(
                    DocumentGrant.document_id == document.id
                ).delete(synchronize_session=False)

                db.query(Document).filter(
                    Document.id == document.id
                ).delete(synchronize_session=False)

            if viewer is not None and viewer.id is not None:
                db.query(User).filter(
                    User.id == viewer.id
                ).delete(synchronize_session=False)

            if owner is not None and owner.id is not None:
                db.query(User).filter(
                    User.id == owner.id
                ).delete(synchronize_session=False)

            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
