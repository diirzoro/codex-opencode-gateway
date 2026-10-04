"""Promote an existing account. Run from backend: python -m scripts.promote_admin EMAIL."""
import sys
from sqlalchemy import select
from app.database import SessionLocal
from app.models import User

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m scripts.promote_admin EMAIL")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == sys.argv[1].strip().lower()))
        if not user:
            raise SystemExit("User not found")
        user.role = "admin"
        db.commit()
        print(f"Promoted {user.email} to admin")
if __name__ == "__main__": main()
