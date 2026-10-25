
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.documents import router
from app.models import UserRole


# Create a test-only FastAPI application.
app = FastAPI()
app.include_router(router)


def make_user(user_id, role=UserRole.OWNER):
    """Create a lightweight mock user."""
    return SimpleNamespace(
        id=user_id,
        role=role,
        is_active=True,
    )


def make_document():
    """Create a document owned by Owner A (user ID 1)."""
    return SimpleNamespace(
        id=100,
        owner_id=1,
        original_filename="private.txt",
        content_type="text/plain",
        size_bytes=100,
        sha256="example-hash",
        storage_key="example-storage-key",
        wrapped_key="example-wrapped-key",
        created_at="2026-10-24T00:00:00Z",
        updated_at="2026-10-24T00:00:00Z",
        deleted_at=None,
    )


class FakeQuery:
    """Minimal query mock for endpoint tests."""

    def __init__(self, item):
        self.item = item

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.item


class FakeDB:
    """Minimal database mock."""

    def __init__(self, document):
        self.document = document

    def query(self, model):
        return FakeQuery(self.document)


@pytest.fixture
def setup_client():
    """Authenticate as Owner B, who does not own Owner A's document."""
    owner_b = make_user(2)
    document = make_document()
    fake_db = FakeDB(document)

    app.dependency_overrides[get_current_user] = lambda: owner_b
    app.dependency_overrides[get_db] = lambda: fake_db

    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def deny_access(*args, **kwargs):
    """Simulate a permission check denying access."""
    return False


def test_other_owner_cannot_view_document_metadata(setup_client):
    """Another owner must not read private document metadata."""
    with patch("app.documents.can_access", side_effect=deny_access):
        response = setup_client.get("/documents/100")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found."


def test_other_owner_cannot_download_document(setup_client):
    """Another owner must not download or read the encrypted file."""
    with patch("app.documents.can_access", side_effect=deny_access):
        with patch("app.documents.read_encrypted_file") as read_file:
            response = setup_client.get("/documents/100/download")

    assert response.status_code == 404
    read_file.assert_not_called()


def test_other_owner_cannot_grant_document_permissions(setup_client):
    """Only the document owner may grant permissions."""
    with patch("app.documents.log_audit_event") as audit:
        response = setup_client.post(
            "/documents/100/grants",
            json={
                "user_id": 3,
                "permissions": ["view"],
            },
        )

    assert response.status_code == 404
    audit.assert_called_once()

    audit_kwargs = audit.call_args.kwargs
    assert audit_kwargs["action"] == "document.grant"
    assert audit_kwargs["result"] == "denied"
    assert audit_kwargs["reason"] == "owner_only"


def test_other_owner_cannot_revoke_document_permissions(setup_client):
    """Only the document owner may revoke permissions."""
    with patch("app.documents.log_audit_event") as audit:
        response = setup_client.delete("/documents/100/grants/3")

    assert response.status_code == 404
    audit.assert_called_once()

    audit_kwargs = audit.call_args.kwargs
    assert audit_kwargs["action"] == "document.revoke"
    assert audit_kwargs["result"] == "denied"
    assert audit_kwargs["reason"] == "owner_only"
