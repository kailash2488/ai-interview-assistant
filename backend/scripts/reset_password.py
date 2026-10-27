"""Reset an account's password from the server (there is no email service to send reset links).

Usage (from backend/):
    python scripts/reset_password.py someone@example.com           # prompts for the new password
    python scripts/reset_password.py --list                        # list account emails

In Docker:  docker compose exec backend python -m scripts.reset_password someone@example.com
Every browser signed in to that account is signed out.
"""
import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.core.db import SessionLocal, init_db  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.models import User  # noqa: E402


def reset(email: str, password: str) -> bool:
    if not 8 <= len(password) <= 128:
        raise ValueError("The password must be 8 to 128 characters")
    init_db()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            return False
        user.password_hash = hash_password(password)
        for row in list(user.auth_sessions):
            db.delete(row)
        db.commit()
        return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("email", nargs="?")
    ap.add_argument("--list", action="store_true", help="list account emails and exit")
    args = ap.parse_args()
    if args.list:
        init_db()
        with SessionLocal() as db:
            for email in db.scalars(select(User.email).order_by(User.created_at)):
                print(email)
        return 0
    if not args.email:
        ap.error("give the account's email address (or --list)")
    password = getpass.getpass("New password: ")
    if password != getpass.getpass("Repeat it: "):
        print("The passwords do not match.")
        return 1
    try:
        found = reset(args.email, password)
    except ValueError as exc:
        print(exc)
        return 1
    print("Password changed and all sessions signed out." if found else "No account with that email.")
    return 0 if found else 1


if __name__ == "__main__":
    raise SystemExit(main())
