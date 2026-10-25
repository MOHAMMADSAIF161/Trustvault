
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.dependencies import get_current_user
from app.models import User, UserRole


def test_disabled_user_with_existing_session_is_rejected():
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="test-token",
    )

    disabled_user = MagicMock(spec=User)
    disabled_user.id = 2
    disabled_user.email = "disabled@example.com"
    disabled_user.role = UserRole.VIEWER
    disabled_user.is_active = False

    with (
        patch(
            "app.dependencies.decode_access_token"
        ) as mock_decode,
        patch(
            "app.dependencies.redis_client.get",
            return_value="2",
        ),
    ):
        mock_decode.return_value = {
            "sub": "2",
            "sid": "existing-session",
        }

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = (
            disabled_user
        )

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(
                credentials=credentials,
                db=db,
            )

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == (
            "User not found or account disabled."
        )
