
import pytest

from app.encryption import (
    EncryptionError,
    decrypt_file,
    encrypt_file,
)


def test_encrypt_then_decrypt():
    original = b"TrustVault confidential document"

    encrypted = encrypt_file(original)

    assert encrypted.ciphertext != original
    assert decrypt_file(
        encrypted.ciphertext,
        encrypted.wrapped_key,
    ) == original


def test_empty_file_can_be_encrypted_and_decrypted():
    encrypted = encrypt_file(b"")

    assert decrypt_file(
        encrypted.ciphertext,
        encrypted.wrapped_key,
    ) == b""


def test_tampered_ciphertext_is_rejected():
    encrypted = encrypt_file(b"Secret document")

    tampered = bytearray(encrypted.ciphertext)
    tampered[-1] ^= 1

    with pytest.raises(EncryptionError):
        decrypt_file(bytes(tampered), encrypted.wrapped_key)


def test_wrong_wrapped_key_is_rejected():
    first = encrypt_file(b"Secret document")
    second = encrypt_file(b"Another document")

    with pytest.raises(EncryptionError):
        decrypt_file(first.ciphertext, second.wrapped_key)


def test_non_bytes_input_is_rejected():
    with pytest.raises(TypeError):
        encrypt_file("not bytes")
