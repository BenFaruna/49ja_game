#!/usr/bin/env python3
"""
Super Admin CLI — Create or manage admin accounts.

Usage:
    python scripts/create_admin.py [OPTIONS]

Options:
    --username   Admin username  (prompted if omitted)
    --email      Admin email     (prompted if omitted)
    --password   Admin password  (prompted securely if omitted)
    --super      Grant super-admin privileges (flag, default: False)

Examples:
    python scripts/create_admin.py --super
    python scripts/create_admin.py --username alice --email alice@example.com --super
"""

import argparse
import getpass
import os
import re
import sys

# ---------------------------------------------------------------------------
# Bootstrap — make sure project root is on sys.path
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Load .env if present (mirrors app startup behaviour)
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
except ImportError:
    pass  # python-dotenv not installed; env vars must be set manually

from models import storage  # noqa: E402 — must come after sys.path setup
from models.admin import Admin  # noqa: E402
from utils.auth import hash_password  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MIN_PASSWORD_LEN = 8


def _prompt(label: str, secret: bool = False) -> str:
    """Interactive prompt; uses getpass for secrets."""
    while True:
        value = (
            getpass.getpass(f"{label}: ") if secret else input(f"{label}: ")
        ).strip()
        if value:
            return value
        print("  ⚠  This field cannot be empty.")


def _validate_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))


def _username_exists(username: str) -> bool:
    return (
        storage.session().query(Admin).filter_by(username=username).first()
    ) is not None


def _email_exists(email: str) -> bool:
    return (storage.session().query(Admin).filter_by(email=email).first()) is not None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def create_admin(username: str, email: str, password: str, is_super: bool) -> None:
    """Persist a new admin record to the database."""
    if _username_exists(username):
        print(f"  ✗  Username '{username}' is already taken.")
        sys.exit(1)

    if _email_exists(email):
        print(f"  ✗  Email '{email}' is already registered.")
        sys.exit(1)

    if len(password) < MIN_PASSWORD_LEN:
        print(f"  ✗  Password must be at least {MIN_PASSWORD_LEN} characters.")
        sys.exit(1)

    admin = Admin(
        username=username,
        email=email,
        password_hash=hash_password(password),
        is_super_admin=is_super,
        is_active=True,
    )
    admin.save()

    role = "super-admin" if is_super else "admin"
    print(f"\n  ✓  Created {role}: username='{username}'  email='{email}'")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="49ja Super Admin CLI — create admin accounts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--username", help="Admin username")
    parser.add_argument("--email", help="Admin email address")
    parser.add_argument("--password", help="Admin password (use prompt for security)")
    parser.add_argument(
        "--super",
        dest="is_super",
        action="store_true",
        default=False,
        help="Grant super-admin privileges",
    )
    args = parser.parse_args()

    print("\n──────────────────────────────────────────")
    print("  49ja  ·  Admin Account Creation")
    print("──────────────────────────────────────────")

    # Collect username
    username = args.username
    while not username:
        username = _prompt("Username")

    # Collect & validate email
    email = args.email
    while not email or not _validate_email(email):
        if email:
            print("  ⚠  Please enter a valid email address.")
        email = _prompt("Email")

    # Collect password securely
    password = args.password
    if not password:
        while True:
            password = _prompt("Password (min 8 chars)", secret=True)
            if len(password) < MIN_PASSWORD_LEN:
                print(
                    f"  ⚠  Password too short. Minimum {MIN_PASSWORD_LEN} characters."
                )
                continue
            confirm = _prompt("Confirm password", secret=True)
            if password != confirm:
                print("  ⚠  Passwords do not match. Please try again.")
                password = None
                continue
            break

    is_super = args.is_super
    if not is_super:
        ans = input("\nGrant super-admin privileges? [y/N]: ").strip().lower()
        is_super = ans == "y"

    print()
    create_admin(username, email, password, is_super)


if __name__ == "__main__":
    main()
