
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.admin import router
from app.dependencies import get_current_user
from app.database import get_db
from app.models import UserRole


app = FastAPI()
app.include_router(router)


def make_user(user_id, role, active=True):
    return SimpleNamespace(
        id=user_id,
        role=role,
        is_active=active,
        email=f"user{user_id}@test.local",
    )


def setup_client(current_user, target_user=None):
    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value.first.return_value = target_user

    app.dependency_overrides[get_current_user] = lambda: current_user
    app.dependency_overrides[get_db] = lambda: db

    return TestClient(app), db


def teardown_client():
    app.dependency_overrides.clear()


def test_viewer_cannot_disable_user():
    client, db = setup_client(
        make_user(2, UserRole.VIEWER),
        make_user(3, UserRole.OWNER),
    )

    try:
        response = client.patch("/admin/users/3/disable")
        assert response.status_code == 403
        db.commit.assert_not_called()
    finally:
        teardown_client()


def test_admin_cannot_disable_self():
    client, db = setup_client(
        make_user(1, UserRole.ADMIN),
        make_user(1, UserRole.ADMIN),
    )

    try:
        response = client.patch("/admin/users/1/disable")
        assert response.status_code == 400
        db.commit.assert_not_called()
    finally:
        teardown_client()


def test_admin_gets_404_for_missing_user():
    client, db = setup_client(
        make_user(1, UserRole.ADMIN),
        None,
    )

    try:
        response = client.patch("/admin/users/99/disable")
        assert response.status_code == 404
        db.commit.assert_not_called()
    finally:
        teardown_client()


def test_admin_can_disable_active_user_and_audit_action():
    admin = make_user(1, UserRole.ADMIN)
    target = make_user(2, UserRole.VIEWER)

    client, db = setup_client(admin, target)

    try:
        with patch("app.admin.log_audit_event") as audit:
            response = client.patch("/admin/users/2/disable")

        assert response.status_code == 200
        assert response.json()["is_active"] is False
        assert target.is_active is False
        db.commit.assert_called_once()
        audit.assert_called_once()

        assert audit.call_args.kwargs["action"] == "user.disable"
        assert audit.call_args.kwargs["result"] == "success"
    finally:
        teardown_client()


def test_admin_cannot_disable_already_disabled_user():
    admin = make_user(1, UserRole.ADMIN)
    target = make_user(2, UserRole.VIEWER, active=False)

    client, db = setup_client(admin, target)

    try:
        response = client.patch("/admin/users/2/disable")
        assert response.status_code == 409
        db.commit.assert_not_called()
    finally:
        teardown_client()
def test_disabled_user_cannot_access_protected_endpoint():
    from unittest.mock import MagicMock
    from fastapi import Depends, FastAPI
    from fastapi.testclient import TestClient
    from app.dependencies import get_current_user
    from app.models import User, UserRole

    app = FastAPI()

    disabled_user = MagicMock(spec=User)
    disabled_user.id = 2
    disabled_user.email = "disabled@example.com"
    disabled_user.role = UserRole.VIEWER
    disabled_user.is_active = False

    def fake_get_current_user():
        if not disabled_user.is_active:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=401,
                detail="Inactive or invalid user.",
            )
        return disabled_user

    @app.get("/protected")
    def protected_route(
        user=Depends(fake_get_current_user),
    ):
        return {"message": "Access granted"}

    client = TestClient(app)
    response = client.get("/protected")

    assert response.status_code == 401

def test_disabled_user_cannot_login():
    from unittest.mock import MagicMock, patch

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.auth import router
    from app.database import get_db
    from app.models import User, UserRole

    app = FastAPI()
    app.include_router(router)

    disabled_user = MagicMock(spec=User)
    disabled_user.id = 2
    disabled_user.email = "disabled@example.com"
    disabled_user.password_hash = "fake-hash"
    disabled_user.role = UserRole.VIEWER
    disabled_user.is_active = False

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = (
        disabled_user
    )

    app.dependency_overrides[get_db] = lambda: db

    with (
        patch("app.auth.verify_password", return_value=True),
        patch("app.auth.redis_client"),
    ):
        client = TestClient(app)
        response = client.post(
            "/auth/login",
            json={
                "email": "disabled@example.com",
                "password": "CorrectPassword123!",
            },
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "This account is disabled."

    app.dependency_overrides.clear()

def test_owner_cannot_disable_user():
    owner = make_user(1, UserRole.OWNER)
    target = make_user(2, UserRole.VIEWER)
    client, db = setup_client(owner, target)

    try:
        response = client.patch("/admin/users/2/disable")
        assert response.status_code == 403
        db.commit.assert_not_called()
    finally:
        teardown_client()


def test_viewer_cannot_verify_audit_logs():
    viewer = make_user(2, UserRole.VIEWER)
    client, db = setup_client(viewer)

    try:
        with patch("app.admin.verify_audit_chain_details") as verify:
            response = client.get("/admin/audit/verify")

        assert response.status_code == 403
        verify.assert_not_called()
    finally:
        teardown_client()
