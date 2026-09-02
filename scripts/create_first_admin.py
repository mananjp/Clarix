#!/usr/bin/env python
"""
Provision a real Super Admin account for a deployment (never auto-run).

This is the production-safe replacement for demo seeding: instead of the
hardcoded "password123" demo accounts, this script creates ONE administrator
with a password you choose (or a strong one it generates for you).

It NEVER runs automatically. Run it manually against the target database:

    python scripts/create_first_admin.py --username admin --email admin@company.com
    python scripts/create_first_admin.py --username admin --email admin@company.com --generate
    python scripts/create_first_admin.py --username admin --email admin@company.com --org-id some_org_id

The database is taken from the same .env / DATABASE_URL resolution as the app
(see app/config.py). The script refuses to overwrite an existing username/email.

Exit codes:
    0 - admin created
    1 - error (user exists, invalid input, etc.)
"""

import argparse
import getpass
import os
import secrets
import string
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

MIN_PASSWORD_LENGTH = 12


def generate_password(length: int = 24) -> str:
    """Generate a cryptographically random password covering all character classes."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{};:,.<>?"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        classes = 0
        if any(c.islower() for c in password):
            classes += 1
        if any(c.isupper() for c in password):
            classes += 1
        if any(c.isdigit() for c in password):
            classes += 1
        if any(c in "!@#$%^&*()-_=+[]{};:,.<>?" for c in password):
            classes += 1
        if classes >= 3:
            return password


def validate_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password too short: minimum {MIN_PASSWORD_LENGTH} characters.")
    if password.lower().strip() in ("password", "password123", "admin", "clarix"):
        raise ValueError("Password is too common. Choose a more unique password.")
    return password


def create_admin(username: str, email: str, password: str, org_id: str | None) -> str:
    from app.database import SessionLocal
    from app.models import Organization, User, UserRole
    from app.auth import get_password_hash

    db = SessionLocal()
    try:
        existing = db.query(User).filter((User.username == username) | (User.email == email)).first()
        if existing:
            raise ValueError(
                f"A user with username '{username}' or email '{email}' already exists. "
                "Refusing to overwrite an existing account."
            )

        if org_id:
            org = db.query(Organization).filter(Organization.id == org_id).first()
            if not org:
                raise ValueError(f"Organization with id '{org_id}' does not exist.")
            organization_id = org_id
        else:
            default_org = db.query(Organization).filter(Organization.id == "default_org").first()
            if not default_org:
                raise ValueError("No organization found. Create one first, or pass --org-id.")
            organization_id = default_org.id

        user = User(
            id="admin_" + secrets.token_hex(8),
            username=username,
            email=email,
            hashed_password=get_password_hash(password),
            role=UserRole.SUPER_ADMIN.value,
            active=True,
            organization_id=organization_id,
        )
        db.add(user)
        db.commit()

        org_name = ""
        try:
            org = db.query(Organization).filter(Organization.id == organization_id).first()
            org_name = f" ({org.name})" if org else ""
        except Exception:
            pass

        db.refresh(user)
        print(f"Created Super Admin '{username}' <{email}> in organization '{organization_id}'{org_name}.")
        print(f"User ID: {user.id}")
        return user.id
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", help="Username for the new admin.")
    parser.add_argument("--email", help="Email for the new admin.")
    parser.add_argument("--password", help="Password (if omitted, you are prompted).")
    parser.add_argument("--org-id", help="Organization id to place the admin in (default: default_org).")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate a strong random password and print it once.",
    )
    args = parser.parse_args()

    username = (args.username or input("Username: ")).strip()
    email = (args.email or input("Email: ")).strip()
    if not username or not email:
        print("Error: username and email are required.", file=sys.stderr)
        return 1
    if "@" not in email or "." not in email:
        print(f"Error: '{email}' does not look like a valid email address.", file=sys.stderr)
        return 1

    if args.generate:
        password = generate_password()
        print(f"\nGenerated password (shown once, save it now): {password}\n")
    else:
        password = args.password or ""
        if not password:
            password = getpass.getpass("Password (min 12 chars): ")
        try:
            validate_password(password)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    try:
        create_admin(username, email, password, args.org_id)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # database/connection errors
        print(f"Error: could not create admin: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
