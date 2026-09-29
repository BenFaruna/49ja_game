"""
Auth utilities for the admin panel.
Provides session-based login helpers and login_required decorator.
"""
import os
from functools import wraps

from flask import redirect, session, url_for, flash
from werkzeug.security import check_password_hash, generate_password_hash


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(plain_text: str) -> str:
    """Return a Werkzeug-hashed password string."""
    return generate_password_hash(plain_text)


def verify_password(plain_text: str, hashed: str) -> bool:
    """Return True if the plain-text password matches the stored hash."""
    return check_password_hash(hashed, plain_text)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

SESSION_ADMIN_KEY = "admin_id"
SESSION_SUPER_KEY = "is_super_admin"


def login_admin(admin_id: int, is_super: bool = False) -> None:
    """Persist the admin session after a successful login."""
    session[SESSION_ADMIN_KEY] = admin_id
    session[SESSION_SUPER_KEY] = is_super
    session.permanent = True


def logout_admin() -> None:
    """Clear admin session data."""
    session.pop(SESSION_ADMIN_KEY, None)
    session.pop(SESSION_SUPER_KEY, None)


def current_admin_id() -> int | None:
    """Return the logged-in admin's ID, or None."""
    return session.get(SESSION_ADMIN_KEY)


def is_authenticated() -> bool:
    """Return True when a valid admin session exists."""
    return SESSION_ADMIN_KEY in session


def is_super_admin() -> bool:
    """Return True when the logged-in admin is a super admin."""
    return session.get(SESSION_SUPER_KEY, False)


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------

def login_required(f):
    """Redirect unauthenticated requests to the admin login page."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_authenticated():
            flash("Please log in to access the admin panel.", "warning")
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated


def super_admin_required(f):
    """Restrict access to super-admin users only."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not is_authenticated():
            flash("Please log in to access the admin panel.", "warning")
            return redirect(url_for("admin.login"))
        if not is_super_admin():
            flash("Super admin privileges required.", "danger")
            return redirect(url_for("admin.dashboard"))
        return f(*args, **kwargs)
    return decorated
