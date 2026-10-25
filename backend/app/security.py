
from datetime import datetime, timedelta, timezone
import uuid

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

from app.config import settings


password_hasher = PasswordHasher()
ALGORITHM = "HS256"


# Hash a user's password securely
def hash_password(password: str) -> str:
    return password_hasher.hash(password)


# Verify a password against its stored hash
def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False


# Generate a unique ID for each login session
def new_session_id() -> str:
    return str(uuid.uuid4())


# Create a JWT containing the user ID and session ID
def create_access_token(user_id: int, session_id: str) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "sid": session_id,
        "iat": now,
        "exp": now + timedelta(
            minutes=settings.access_token_expire_minutes
        ),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )


# Decode and validate a JWT
def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[ALGORITHM],
        options={
            "require": ["sub", "sid", "iat", "exp"],
        },
    )
