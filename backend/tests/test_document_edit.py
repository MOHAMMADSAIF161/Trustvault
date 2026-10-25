
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
        original_filename="old.txt",
        storage_key="12345678-1234-4123-8123-123456789abc.enc",
        content_type="text/plain",
        size_bytes=3,
        sha256="old-hash",
        wrapped_key="old-wrapped-key",
        deleted_at=None,
    )


class FakeQuery:
    def __init__(self, item):
        self.item = item

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.item


class FakeDB:
    def __init__(self, document):
        self.document = document
        self.committed = False
        self.original_values = {
            "original_filename": document.original_filename,
            "storage_key": document.storage_key,
            "content_type": document.content_type,
            "size_bytes": document.size_bytes,
            "sha256": document.sha256,
            "wrapped_key": document.wrapped_key,
        }

    def query(self, model):
        return FakeQuery(self.document)

    def commit(self):
        self.committed = True

    def refresh(self, obj):
        pass

    def rollback(self):
        for key, value in self.original_values.items():
            setattr(self.document, key, value)
        self.committed = False


@pytest.fixture
def client_for_user():
    def create(user_id):
        document = make_document()
        db = FakeDB(document)

        app.dependency_overrides[get_current_user] = (
            lambda: make_user(user_id)
        )
        app.dependency_overrides[get_db] = lambda: db

        client = TestClient(
            app,
            raise_server_exceptions=False,
        )
        return client, document, db

    yield create
    app.dependency_overrides.clear()


def test_owner_can_edit_document(client_for_user):
    client, document, db = client_for_user(1)

    with patch(
        "app.documents.validate_file_content",
        return_value="text/plain",
    ), patch(
        "app.documents.encrypt_file",
        return_value=SimpleNamespace(
            ciphertext=b"encrypted-new",
            wrapped_key="new-wrapped-key",
        ),
    ), patch(
        "app.documents.save_encrypted_file"
    ) as save_file, patch(
        "app.documents.delete_encrypted_file"
    ) as delete_file, patch(
        "app.documents.log_audit_event"
    ), patch(
        "app.permissions.log_audit_event"
    ):
        response = client.put(
            "/documents/100/edit",
            files={
                "file": ("new.txt", b"new content", "text/plain")
            },
        )

    assert response.status_code == 200
    assert document.original_filename == "new.txt"
    assert document.size_bytes == len(b"new content")
    assert document.wrapped_key == "new-wrapped-key"
    assert document.storage_key != (
        "12345678-1234-4123-8123-123456789abc.enc"
    )
    assert db.committed is True

    save_file.assert_called_once()
    delete_file.assert_called_once_with(
        "12345678-1234-4123-8123-123456789abc.enc"
    )

    client.close()


def test_other_owner_cannot_edit_document(client_for_user):
    client, document, db = client_for_user(2)

    with patch(
        "app.documents.can_access",
        return_value=False,
    ), patch(
        "app.documents.save_encrypted_file"
    ) as save_file, patch(
        "app.documents.log_audit_event"
    ):
        response = client.put(
            "/documents/100/edit",
            files={
                "file": ("new.txt", b"new content", "text/plain")
            },
        )

    assert response.status_code == 404
    save_file.assert_not_called()
    assert db.committed is False
    assert document.original_filename == "old.txt"

    client.close()


def test_edit_database_failure_cleans_up_new_file(client_for_user):
    client, document, db = client_for_user(1)

    def fail_commit():
        raise RuntimeError("DB unavailable")

    db.commit = fail_commit

    with patch(
        "app.documents.validate_file_content",
        return_value="text/plain",
    ), patch(
        "app.documents.encrypt_file",
        return_value=SimpleNamespace(
            ciphertext=b"encrypted-new",
            wrapped_key="new-wrapped-key",
        ),
    ), patch(
        "app.documents.save_encrypted_file"
    ) as save_file, patch(
        "app.documents.delete_encrypted_file"
    ) as delete_file, patch(
        "app.documents.log_audit_event"
    ), patch(
        "app.permissions.log_audit_event"
    ):
        response = client.put(
            "/documents/100/edit",
            files={
                "file": ("new.txt", b"new content", "text/plain")
            },
        )

    assert response.status_code == 500
    save_file.assert_called_once()
    delete_file.assert_called_once()

    # Rollback should preserve the original document metadata.
    assert document.storage_key == (
        "12345678-1234-4123-8123-123456789abc.enc"
    )
    assert document.original_filename == "old.txt"
    assert document.wrapped_key == "old-wrapped-key"
    assert db.committed is False

    client.close()
