
from getpass import getpass

from app.database import SessionLocal
from app.models import User, UserRole
from app.security import hash_password

email = input("Admin email: ").strip().lower()
password = getpass("Admin password (minimum 12 characters): ")

if len(password) < 12 or len(password) > 128:
    raise ValueError("Password must be between 12 and 128 characters.")

db = SessionLocal()

try:
    existing_user = db.query(User).filter(User.email == email).first()

    if existing_user:
        print(
            f"Account already exists: {existing_user.email}, "
            f"role={existing_user.role.value}"
        )
    else:
        admin = User(
            email=email,
            password_hash=hash_password(password),
            role=UserRole.ADMIN,
        )
        db.add(admin)
        db.commit()
        print(f"Admin account created: {email}")

except Exception:
    db.rollback()
    raise
finally:
    db.close()
