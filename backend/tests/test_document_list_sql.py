
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import User, UserRole, Document, DocumentGrant


def test_document_list_sql_filters_by_owner_and_grant():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    Base.metadata.create_all(bind=engine)

    try:
        with TestingSession() as db:
            owner = User(
                email="owner@test.local",
                password_hash="test-hash",
                role=UserRole.OWNER,
                is_active=True,
            )
            viewer = User(
                email="viewer@test.local",
                password_hash="test-hash",
                role=UserRole.VIEWER,
                is_active=True,
            )
            other_owner = User(
                email="other@test.local",
                password_hash="test-hash",
                role=UserRole.OWNER,
                is_active=True,
            )
            db.add_all([owner, viewer, other_owner])
            db.flush()

            own_doc = Document(
                owner_id=owner.id,
                original_filename="own.txt",
                storage_key="own-test.enc",
                content_type="text/plain",
                size_bytes=10,
                sha256="a" * 64,
            )
            shared_doc = Document(
                owner_id=other_owner.id,
                original_filename="shared.txt",
                storage_key="shared-test.enc",
                content_type="text/plain",
                size_bytes=10,
                sha256="b" * 64,
            )
            private_doc = Document(
                owner_id=other_owner.id,
                original_filename="private.txt",
                storage_key="private-test.enc",
                content_type="text/plain",
                size_bytes=10,
                sha256="c" * 64,
            )
            deleted_doc = Document(
                owner_id=owner.id,
                original_filename="deleted.txt",
                storage_key="deleted-test.enc",
                content_type="text/plain",
                size_bytes=10,
                sha256="d" * 64,
                deleted_at=datetime.now(timezone.utc),
            )
            db.add_all([own_doc, shared_doc, private_doc, deleted_doc])
            db.flush()

            db.add(
                DocumentGrant(
                    document_id=shared_doc.id,
                    user_id=viewer.id,
                    permissions=["view"],
                    granted_by=other_owner.id,
                )
            )
            db.commit()

            # Actual SQL query used by the Viewer branch of list_documents.
            viewer_ids = {
                row.id
                for row in (
                    db.query(Document)
                    .filter(Document.deleted_at.is_(None))
                    .join(
                        DocumentGrant,
                        DocumentGrant.document_id == Document.id,
                    )
                    .filter(DocumentGrant.user_id == viewer.id)
                    .distinct()
                    .all()
                )
            }

            assert viewer_ids == {shared_doc.id}
            assert own_doc.id not in viewer_ids
            assert private_doc.id not in viewer_ids
            assert deleted_doc.id not in viewer_ids

            # Actual SQL query used by the Owner branch.
            from sqlalchemy import or_

            owner_ids = {
                row.id
                for row in (
                    db.query(Document)
                    .filter(Document.deleted_at.is_(None))
                    .outerjoin(
                        DocumentGrant,
                        DocumentGrant.document_id == Document.id,
                    )
                    .filter(
                        or_(
                            Document.owner_id == owner.id,
                            DocumentGrant.user_id == owner.id,
                        )
                    )
                    .distinct()
                    .all()
                )
            }

            assert own_doc.id in owner_ids
            assert deleted_doc.id not in owner_ids
            assert private_doc.id not in owner_ids

    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
