from sqlalchemy import text
from app.database import engine

with engine.connect() as connection:
    transaction = connection.begin()
    try:
        connection.execute(
            text("CREATE TABLE public._trustvault_permission_test (id integer)")
        )
        print("CREATE TABLE: successful")
    except Exception as exc:
        print("CREATE TABLE failed:", type(exc).__name__, str(exc))
    finally:
        transaction.rollback()

with engine.connect() as connection:
    result = connection.execute(
        text("SELECT to_regclass('public._trustvault_permission_test')")
    ).scalar()
    print("Temporary table after rollback:", result)