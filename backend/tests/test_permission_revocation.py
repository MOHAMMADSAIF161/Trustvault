
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.models import DocumentGrant, UserRole
from app.permissions import Action, can_access


app = FastAPI()


class FakeQuery:
    def __init__(self, db, model):
        self.db = db
        self.model = model

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        if self.model is DocumentGrant:
            return self.db.grant

        if self.model.__name__ == "AuditLog":
            return None

        return self.db.document


class FakeDB:
    def __init__(self):
        self.document = SimpleNamespace(
            id=100,
            owner_id=1,
            original_filename="private.txt",
            content_type="text/plain",
            size_bytes=12,
            sha256="example-hash",
            storage_key="example-storage-key",
            wrapped_key="example-wrapped-key",
            created_at="2026-10-24T00:00:00Z",
            updated_at="2026-10-24T00:00:00Z",
            deleted_at=None,
        )
        self.grant = SimpleNamespace(
            document_id=100,
            user_id=2,
            permissions=["view"],
        )

    def query(self, model):
        return FakeQuery(self, model)

    def delete(self, item):
        if item is self.grant:
            self.grant = None

    def commit(self):
        pass


def make_user(user_id, role):
    return SimpleNamespace(
        id=user_id,
        role=role,
        is_active=True,
    )


def test_revoked_viewer_cannot_view_document_on_next_request():
    # Import the router after importing permissions to avoid the
    # previous test import-order issue.
    from app.documents import router

    app.include_router(router)

    fake_db = FakeDB()
    owner = make_user(1, UserRole.OWNER)
    viewer = make_user(2, UserRole.VIEWER)

    # Before revocation, the real permission checker allows viewing.
    with patch("app.permissions.log_audit_event"):
        assert can_access(
            fake_db, viewer, fake_db.document, Action.VIEW
        ) is True

    app.dependency_overrides[get_current_user] = lambda: owner
    app.dependency_overrides[get_db] = lambda: fake_db

    try:
        with TestClient(app) as client:
            # Owner revokes the viewer's grant.
            with patch("app.documents.log_audit_event"):
                revoke_response = client.delete(
                    "/documents/100/grants/2"
                )

            assert revoke_response.status_code == 200
            assert fake_db.grant is None

            # The real permission checker now denies viewing.
            with patch("app.permissions.log_audit_event") as audit:
                allowed = can_access(
                    fake_db, viewer, fake_db.document, Action.VIEW
                )

            assert allowed is False
            audit.assert_called_once()
            assert audit.call_args.kwargs["result"] == "denied"
            assert audit.call_args.kwargs["reason"] == "missing_permission"

            # The next HTTP request must also be denied.
            app.dependency_overrides[get_current_user] = lambda: viewer

            with patch("app.permissions.log_audit_event"):
                view_response = client.get("/documents/100")

            assert view_response.status_code == 404
            assert view_response.json()["detail"] == "Document not found."

    finally:
        app.dependency_overrides.clear()
