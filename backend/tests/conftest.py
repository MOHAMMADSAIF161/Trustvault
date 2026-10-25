
import pytest


@pytest.fixture(scope="session", autouse=True)
def require_test_database():
    """Prevent tests from running against anything except trustvault_test."""

    # Import the URL used by the application's SQLAlchemy engine.
    from app.database import engine
    from sqlalchemy.engine import make_url

    url = make_url(engine.url)

    if (
        url.get_backend_name() != "postgresql"
        or url.database != "trustvault_test"
    ):
        pytest.exit(
            "Safety check failed: tests must use PostgreSQL trustvault_test.",
            returncode=2,
        )
