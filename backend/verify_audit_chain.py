
from app.audit import verify_audit_chain
from app.database import SessionLocal

db = SessionLocal()

try:
    valid = verify_audit_chain(db)

    if valid:
        print("PASS: Audit hash chain is valid.")
    else:
        print("FAIL: Audit hash chain is invalid.")
finally:
    db.close()
