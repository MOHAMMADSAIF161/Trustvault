
import base64
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import settings


NONCE_SIZE = 12
KEY_SIZE = 32


class EncryptionError(Exception):
    """Raised when encrypted data or encryption configuration is invalid."""


@dataclass(frozen=True)
class EncryptedFile:
    ciphertext: bytes
    wrapped_key: str


def _load_master_key() -> bytes:
    """Load and validate the Base64-encoded AES-256 master key."""

    encoded_key = settings.master_encryption_key

    if not encoded_key:
        raise EncryptionError("MASTER_ENCRYPTION_KEY is missing.")

    try:
        key = base64.b64decode(encoded_key, validate=True)
    except Exception as exc:
        raise EncryptionError(
            "MASTER_ENCRYPTION_KEY must be valid Base64."
        ) from exc

    if len(key) != KEY_SIZE:
        raise EncryptionError(
            "MASTER_ENCRYPTION_KEY must decode to exactly 32 bytes."
        )

    return key


def encrypt_file(plaintext: bytes) -> EncryptedFile:
    """
    Encrypt a file using a unique AES-256-GCM file key.
    Encrypt (wrap) the file key using the master key.

    ciphertext format: 12-byte nonce + encrypted data + GCM tag
    wrapped_key format: Base64(12-byte nonce + encrypted file key + GCM tag)
    """

    if not isinstance(plaintext, bytes):
        raise TypeError("plaintext must be bytes.")

    master_key = _load_master_key()

    # Generate an independent 256-bit key for this file.
    file_key = AESGCM.generate_key(bit_length=256)
    file_nonce = os.urandom(NONCE_SIZE)

    encrypted_content = AESGCM(file_key).encrypt(
        file_nonce,
        plaintext,
        None,
    )
    ciphertext = file_nonce + encrypted_content

    # Protect the per-file key with the master key.
    wrap_nonce = os.urandom(NONCE_SIZE)
    encrypted_file_key = AESGCM(master_key).encrypt(
        wrap_nonce,
        file_key,
        None,
    )

    wrapped_key = base64.b64encode(
        wrap_nonce + encrypted_file_key
    ).decode("ascii")

    return EncryptedFile(
        ciphertext=ciphertext,
        wrapped_key=wrapped_key,
    )


def decrypt_file(ciphertext: bytes, wrapped_key: str) -> bytes:
    """Authenticate and decrypt previously encrypted file data."""

    if not isinstance(ciphertext, bytes):
        raise EncryptionError("Encrypted file data must be bytes.")

    if len(ciphertext) < NONCE_SIZE + 16:
        raise EncryptionError("Encrypted file data is incomplete.")

    if not isinstance(wrapped_key, str):
        raise EncryptionError("Wrapped file key must be a string.")

    master_key = _load_master_key()

    try:
        wrapped_bytes = base64.b64decode(
            wrapped_key,
            validate=True,
        )
    except Exception as exc:
        raise EncryptionError("Wrapped file key is invalid.") from exc

    if len(wrapped_bytes) < NONCE_SIZE + 16:
        raise EncryptionError("Wrapped file key is incomplete.")

    wrap_nonce = wrapped_bytes[:NONCE_SIZE]
    encrypted_file_key = wrapped_bytes[NONCE_SIZE:]

    try:
        file_key = AESGCM(master_key).decrypt(
            wrap_nonce,
            encrypted_file_key,
            None,
        )

        if len(file_key) != KEY_SIZE:
            raise EncryptionError("Decrypted file key has an invalid length.")

        file_nonce = ciphertext[:NONCE_SIZE]
        encrypted_content = ciphertext[NONCE_SIZE:]

        return AESGCM(file_key).decrypt(
            file_nonce,
            encrypted_content,
            None,
        )

    except InvalidTag as exc:
        raise EncryptionError(
            "Decryption failed: the key or encrypted data is invalid."
        ) from exc
