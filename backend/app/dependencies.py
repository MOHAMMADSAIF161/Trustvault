
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.redis_client import redis_client
from app.security import decode_access_token

bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    # Validate the access token
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
        session_id = payload["sid"]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
        )

    # Check that the session exists in Redis
    try:
        session_user_id = redis_client.get(
            f"trustvault:session:{session_id}"
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable.",
        )

    # Normalize Redis responses that may be bytes or strings
    if isinstance(session_user_id, bytes):
        try:
            session_user_id = session_user_id.decode("utf-8")
        except UnicodeDecodeError:
            session_user_id = None

    # Confirm that the session belongs to the token's user
    if (
        session_user_id is None
        or str(session_user_id) != str(user_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or revoked. Please log in again.",
        )

    # Confirm that the account exists and is active
    user = db.query(User).filter(User.id == user_id).first()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or account disabled.",
        )

    return user
