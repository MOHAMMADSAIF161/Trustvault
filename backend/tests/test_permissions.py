
from types import SimpleNamespace
from unittest.mock import patch

from app.permissions import Action, can_access

from app.models import UserRole
class FakeQuery:
    def __init__(self, grant):
        self.grant = grant

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.grant


class FakeDB:
    def __init__(self, grant=None):
        self.grant = grant

    def query(self, model):
        return FakeQuery(self.grant)


def make_user(user_id=1, active=True, role=None):
    if role is None:
        role = UserRole.OWNER if user_id == 1 else UserRole.VIEWER

    return SimpleNamespace(
        id=user_id,
        is_active=active,
        role=role,
    )

def make_document(owner_id=1, deleted_at=None):
    return SimpleNamespace(id=10, owner_id=owner_id, deleted_at=deleted_at)


def make_grant(permissions):
    return SimpleNamespace(permissions=permissions)


def check_access(db, user, document, action):
    with patch("app.permissions.log_audit_event") as audit:
        result = can_access(db, user, document, action)
    audit.assert_called_once()
    return result, audit.call_args.kwargs


def test_owner_can_view():
    result, audit = check_access(
        FakeDB(), make_user(1), make_document(1), Action.VIEW
    )
    assert result is True
    assert audit["result"] == "allowed"


def test_inactive_user_is_denied():
    result, audit = check_access(
        FakeDB(), make_user(2, False), make_document(1), Action.VIEW
    )
    assert result is False
    assert audit["result"] == "denied"


def test_deleted_document_is_denied():
    result, audit = check_access(
        FakeDB(), make_user(1), make_document(1, "deleted"), Action.VIEW
    )
    assert result is False
    assert audit["result"] == "denied"


def test_viewer_with_view_grant_can_view():
    result, audit = check_access(
        FakeDB(make_grant(["view"])),
        make_user(2),
        make_document(1),
        Action.VIEW,
    )
    assert result is True
    assert audit["result"] == "allowed"


def test_view_only_grant_cannot_download():
    result, audit = check_access(
        FakeDB(make_grant(["view"])),
        make_user(2),
        make_document(1),
        Action.DOWNLOAD,
    )
    assert result is False
    assert audit["result"] == "denied"


def test_viewer_without_grant_is_denied():
    result, audit = check_access(
        FakeDB(), make_user(2), make_document(1), Action.VIEW
    )
    assert result is False
    assert audit["result"] == "denied"
def test_viewer_cannot_edit_even_with_edit_grant():
    result, audit = check_access(
        FakeDB(make_grant(["edit"])),
        make_user(2),
        make_document(1),
        Action.EDIT,
    )
    assert result is False
    assert audit["result"] == "denied"


def test_viewer_cannot_delete_even_with_delete_grant():
    result, audit = check_access(
        FakeDB(make_grant(["delete"])),
        make_user(2),
        make_document(1),
        Action.DELETE,
    )
    assert result is False
    assert audit["result"] == "denied"


def test_viewer_cannot_share_even_with_share_grant():
    result, audit = check_access(
        FakeDB(make_grant(["share"])),
        make_user(2),
        make_document(1),
        Action.SHARE,
    )
    assert result is False
    assert audit["result"] == "denied"


def test_admin_cannot_access_private_document_by_default():
    result, audit = check_access(
        FakeDB(),
        make_user(3, role=UserRole.ADMIN),
        make_document(1),
        Action.VIEW,
    )
    assert result is False
    assert audit["result"] == "denied"