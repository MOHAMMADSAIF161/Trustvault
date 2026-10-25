
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user
from app.documents import router
from app.models import UserRole


app = FastAPI()
app.include_router(router)


def make_user(user_id):
    return SimpleNamespace(
        id=user_id,
        role=UserRole.OWNER,
        is_active=True,
    )


def make_document():
    return SimpleNamespace(
        id=100,
        owner_id=1,
        original_filename="private.txt",
        storage_key="12345678-1234-4123-8123-123456789abc.enc",
        deleted_at=None,
        wrapped_key="wrapped-key",
    )


class FakeQuery:
    def __init__(self, document):
        self.document = document

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.document


class FakeDB:
    def __init__(self, document):
        self.document = document
        self.committed = False

    def query(self, model):
        return FakeQuery(self.document)

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


@pytest.fixture
def client_for_user():
    def create(user_id):
        document = make_document()
        db = FakeDB(document)

        app.dependency_overrides[get_current_user] = lambda: make_user(user_id)
        app.dependency_overrides[get_db] = lambda: db

        client = TestClient(app)
        return client, document, db

    yield create
    app.dependency_overrides.clear()


def test_owner_can_delete_own_document(client_for_user):
    client, document, db = client_for_user(1)

    with patch("app.documents.delete_encrypted_file") as delete_file, \
         patch("app.documents.log_audit_event"):
        response = client.delete("/documents/100")

    assert response.status_code == 204
    delete_file.assert_called_once_with(document.storage_key)
    assert document.deleted_at is not None
    assert document.wrapped_key is None
    assert db.committed is True
    client.close()


def test_other_owner_cannot_delete_document(client_for_user):
    client, document, db = client_for_user(2)

    with patch("app.documents.delete_encrypted_file") as delete_file, \
         patch("app.documents.log_audit_event") as audit:
        response = client.delete("/documents/100")

    assert response.status_code == 404
    delete_file.assert_not_called()
    audit.assert_called_once()
    assert audit.call_args.kwargs["result"] == "denied"
    assert document.deleted_at is None
    assert db.committed is False
    client.close()


def test_storage_failure_keeps_document_soft_deleted(client_for_user):
    client, document, db = client_for_user(1)

    with patch(
        "app.documents.delete_encrypted_file",
        side_effect=OSError("Storage unavailable"),
    ), patch("app.documents.log_audit_event") as audit:
        response = client.delete("/documents/100")

    assert response.status_code == 500

    # Database deletion was committed before storage cleanup.
    assert document.deleted_at is not None
    assert document.wrapped_key is None
    assert db.committed is True

    # Cleanup failure is recorded.
    assert audit.call_count >= 1
    assert any(
        call.kwargs.get("reason") == "storage_cleanup_failed"
        for call in audit.call_args_list
    )

    client.close()



def test_deleted_document_cannot_be_viewed(client_for_user):
    client, document, db = client_for_user(1)
    document.deleted_at = "2026-10-24T00:00:00Z"

    with patch("app.documents.can_access", return_value=False), \
         patch("app.documents.log_audit_event"):
        response = client.get("/documents/100")

    assert response.status_code == 404
    client.close()


def test_deleted_document_cannot_be_downloaded(client_for_user):
    client, document, db = client_for_user(1)
    document.deleted_at = "2026-10-24T00:00:00Z"

    with patch("app.documents.can_access", return_value=False), \
         patch("app.documents.log_audit_event"), \
         patch("app.documents.read_encrypted_file") as read_file:
        response = client.get("/documents/100/download")

    assert response.status_code == 404
    read_file.assert_not_called()
    client.close()

def test_get_document_or_404_excludes_deleted_documents():
    from unittest.mock import MagicMock
    from fastapi import HTTPException
    from app.documents import get_document_or_404

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc:
        get_document_or_404(db, 100)

    assert exc.value.status_code == 404
