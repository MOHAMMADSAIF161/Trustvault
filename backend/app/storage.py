
import os
import re
from pathlib import Path

from fastapi import HTTPException

STORAGE_ROOT = Path(r"C:\TrustVaultPrivateStorage").resolve()


def _validate_storage_key(storage_key: str) -> str:
    """Accept only a generated UUID-style storage filename."""

    if not re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.enc",
        storage_key,
        flags=re.IGNORECASE,
    ):
        raise ValueError("Invalid storage key.")

    return storage_key


def save_encrypted_file(storage_key: str, ciphertext: bytes) -> None:
    """Save encrypted bytes in private storage, never in the web root."""

    safe_key = _validate_storage_key(storage_key)
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

    destination = (STORAGE_ROOT / safe_key).resolve()

    if destination.parent != STORAGE_ROOT:
        raise ValueError("Invalid storage path.")

    # Exclusive creation avoids accidentally overwriting an existing file.
    with destination.open("xb") as file:
        file.write(ciphertext)


def read_encrypted_file(storage_key: str) -> bytes:
    """Read encrypted bytes using a validated generated storage key."""

    safe_key = _validate_storage_key(storage_key)
    source = (STORAGE_ROOT / safe_key).resolve()

    if source.parent != STORAGE_ROOT or not source.is_file():
        raise FileNotFoundError("Stored document not found.")

    return source.read_bytes()


def delete_encrypted_file(storage_key: str) -> None:
    """Delete an encrypted file if it exists."""

    safe_key = _validate_storage_key(storage_key)
    source = (STORAGE_ROOT / safe_key).resolve()

    if source.parent != STORAGE_ROOT:
        raise ValueError("Invalid storage path.")

    if source.exists():
        source.unlink()
