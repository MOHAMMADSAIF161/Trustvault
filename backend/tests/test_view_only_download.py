
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


def make_viewer():
    return SimpleNamespace(
        id=2,
        role=UserRole.VIEWER,
        is_active=True,
    )


def make_document():
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
    def __init__(self, item):
        self.item = item

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.item


class FakeDB:
    def __init__(self, document):
        self.document = document

    def query(self, model):
        return FakeQuery(self.document)


@pytest.fixture
def client():
    app.dependency_overrides[get_current_user] = make_viewer
    app.dependency_overrides[get_db] = lambda: FakeDB(make_document())

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_view_only_user_cannot_download_document(client):
    with patch("app.documents.can_access", return_value=False):
        with patch("app.documents.read_encrypted_file") as read_file:
            response = client.get("/documents/100/download")

    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found."
    read_file.assert_not_called()
