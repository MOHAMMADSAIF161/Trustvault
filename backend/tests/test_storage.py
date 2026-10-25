
import pytest
from app import storage


VALID_KEY = "123e4567-e89b-42d3-a456-426614174000.enc"


def test_save_and_read_encrypted_file(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_ROOT", tmp_path.resolve())

    encrypted_data = b"test-encrypted-file-content"

    storage.save_encrypted_file(VALID_KEY, encrypted_data)
    result = storage.read_encrypted_file(VALID_KEY)

    assert result == encrypted_data


def test_delete_encrypted_file(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_ROOT", tmp_path.resolve())

    storage.save_encrypted_file(VALID_KEY, b"test-data")
    storage.delete_encrypted_file(VALID_KEY)

    with pytest.raises(FileNotFoundError):
        storage.read_encrypted_file(VALID_KEY)


def test_reject_path_traversal_key():
    with pytest.raises(ValueError):
        storage.save_encrypted_file("../secret.enc", b"test-data")


def test_reject_invalid_key_when_reading():
    with pytest.raises(ValueError):
        storage.read_encrypted_file("../secret.enc")


def test_reject_invalid_key_when_deleting():
    with pytest.raises(ValueError):
        storage.delete_encrypted_file("../secret.enc")
