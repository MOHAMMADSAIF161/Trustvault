
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import get_current_user
from app.documents import router
from app.models import UserRole


app = FastAPI()
app.include_router(router)


def make_user(user_id, role):
    return SimpleNamespace(
        id=user_id,
        role=role,
        is_active=True,
    )


def make_document(document_id, owner_id, filename):
    return SimpleNamespace(
        id=document_id,
        owner_id=owner_id,
        original_filename=filename,
        content_type="text/plain",
        size_bytes=100,
        created_at="2026-10-24T00:00:00Z",
        deleted_at=None,
    )


def make_grant(document_id, user_id, permissions):
    return SimpleNamespace(
        document_id=document_id,
        user_id=user_id,
        permissions=permissions,
    )


def run_document_list(user, documents, grants):
    app.dependency_overrides[get_current_user] = lambda: user

    # Fake query chain: supports the filters, joins and ordering used
    # by list_documents without connecting to the real database.
    class FakeQuery:
        def __init__(self, model):
            self.model = model
            self.items = documents if model.__name__ == "Document" else grants

        def filter(self, *args, **kwargs):
            return self

        def outerjoin(self, *args, **kwargs):
            return self

        def join(self, *args, **kwargs):
            return self

        def distinct(self):
            return self

        def order_by(self, *args, **kwargs):
            return self

        def all(self):
            return self.items

    class FakeDB:
        def query(self, model):
            return FakeQuery(model)

    app.dependency_overrides.clear()
    app.dependency_overrides[get_current_user] = lambda: user

    from app.database import get_db
    app.dependency_overrides[get_db] = lambda: FakeDB()

    # Mock the final authorization check to focus on the endpoint.
    def allowed(db, current_user, document, action, ip_address=None):
        if document.owner_id == current_user.id:
            return True

        grant = next(
            (
                item for item in grants
                if item.document_id == document.id
                and item.user_id == current_user.id
            ),
            None,
        )
        return bool(grant and "view" in (grant.permissions or []))

    with patch("app.documents.can_access", side_effect=allowed):
        try:
            with TestClient(app) as client:
                response = client.get("/documents")
            return response
        finally:
            app.dependency_overrides.clear()


def test_owner_sees_own_documents():
    owner = make_user(1, UserRole.OWNER)
    documents = [
        make_document(10, 1, "owner.txt"),
        make_document(11, 2, "other.txt"),
    ]

    response = run_document_list(owner, documents, [])

    assert response.status_code == 200
    assert [item["filename"] for item in response.json()["documents"]] == [
        "owner.txt"
    ]


def test_viewer_sees_only_documents_with_view_permission():
    viewer = make_user(3, UserRole.VIEWER)
    documents = [
        make_document(10, 1, "shared.txt"),
        make_document(11, 2, "private.txt"),
    ]
    grants = [
        make_grant(10, 3, ["view"]),
    ]

    response = run_document_list(viewer, documents, grants)

    assert response.status_code == 200
    assert [item["filename"] for item in response.json()["documents"]] == [
        "shared.txt"
    ]


def test_viewer_without_view_permission_sees_no_documents():
    viewer = make_user(3, UserRole.VIEWER)
    documents = [make_document(10, 1, "download-only.txt")]
    grants = [make_grant(10, 3, ["download"])]

    response = run_document_list(viewer, documents, grants)

    assert response.status_code == 200
    assert response.json()["documents"] == []
