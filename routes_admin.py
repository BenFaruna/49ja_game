"""
Admin Blueprint — handles login, logout, and the protected admin dashboard.
"""

from datetime import timedelta

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from sqlalchemy import and_, or_

from models import storage
from models.admin import Admin
from utils.auth import (
    login_admin,
    login_required,
    logout_admin,
    super_admin_required,
    verify_password,
)
from utils.logger import get_logger

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")
logger = get_logger(__name__, "server.log")

# Keep sessions alive for 8 hours by default
SESSION_LIFETIME = timedelta(hours=8)


# ---------------------------------------------------------------------------
# Login / Logout
# ---------------------------------------------------------------------------


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    """Admin login page."""
    from utils.auth import is_authenticated

    if is_authenticated():
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Username and password are required.", "danger")
            return render_template("admin/login.html")

        try:
            admin = (
                storage.session()
                .query(Admin)
                .filter(
                    and_(
                        or_(Admin.username == username, Admin.email == username),
                        Admin.is_active == True,
                    ),
                )
                .first()
            )
        except Exception as e:
            logger.error(f"DB error during admin login: {e}")
            flash("An error occurred. Please try again.", "danger")
            return render_template("admin/login.html")

        if admin and verify_password(password, admin.password_hash):
            login_admin(admin.id, is_super=admin.is_super_admin)
            logger.info(f"Admin '{username}' logged in (super={admin.is_super_admin})")
            flash(f"Welcome back, {admin.username}!", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("admin.dashboard"))

        flash("Invalid username or password.", "danger")
        logger.warning(f"Failed login attempt for username='{username}'")

    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    """Log the current admin out."""
    logout_admin()
    flash("You have been logged out.", "info")
    return redirect(url_for("admin.login"))


# ---------------------------------------------------------------------------
# Protected Admin Dashboard
# ---------------------------------------------------------------------------


@admin_bp.route("/")
@login_required
def dashboard():
    """Main admin dashboard — protected."""
    from models.notification_email import NotificationEmail
    from utils.auth import current_admin_id
    from utils.auth import is_super_admin as _is_super

    try:
        current = (
            storage.session().query(Admin).filter_by(id=current_admin_id()).first()
        )
        all_admins = (
            storage.session().query(Admin).order_by(Admin.id).all()
            if _is_super()
            else []
        )
        notification_emails = (
            storage.session()
            .query(NotificationEmail)
            .order_by(NotificationEmail.id)
            .all()
            if _is_super()
            else []
        )
    except Exception as e:
        logger.error(f"DB error loading admin dashboard: {e}")
        current = None
        all_admins = []
        notification_emails = []

    return render_template(
        "admin/dashboard.html",
        current_admin=current,
        all_admins=all_admins,
        notification_emails=notification_emails,
        is_super=_is_super(),
    )


# ---------------------------------------------------------------------------
# Email Recipient Management (super admin only)
# ---------------------------------------------------------------------------


@admin_bp.route("/emails", methods=["POST"])
@super_admin_required
def add_email():
    """Register a new notification email recipient."""
    from models.notification_email import NotificationEmail

    email_addr = request.form.get("email", "").strip().lower()
    label = request.form.get("label", "").strip() or None
    try:
        threshold = int(request.form.get("threshold", 8))
        threshold = max(1, min(threshold, 20))
    except (ValueError, TypeError):
        threshold = 8

    if not email_addr:
        flash("Email address is required.", "danger")
        return redirect(url_for("admin.dashboard"))

    # Duplicate check
    existing = (
        storage.session().query(NotificationEmail).filter_by(email=email_addr).first()
    )
    if existing:
        flash(f"'{email_addr}' is already registered.", "warning")
        return redirect(url_for("admin.dashboard"))

    try:
        entry = NotificationEmail(
            email=email_addr, label=label, alert_threshold=threshold
        )
        entry.save()
        flash(f"✅ '{email_addr}' added with threshold={threshold}.", "success")
        logger.info(
            "Notification email added: %s (threshold=%d)", email_addr, threshold
        )
    except Exception as e:
        logger.error("Failed to add notification email: %s", e)
        flash("Failed to add email. Please try again.", "danger")

    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/emails/<int:email_id>/delete", methods=["POST"])
@super_admin_required
def delete_email(email_id):
    """Remove a notification email recipient."""
    from models.notification_email import NotificationEmail

    entry = storage.session().query(NotificationEmail).get(email_id)
    if not entry:
        flash("Email not found.", "danger")
        return redirect(url_for("admin.dashboard"))

    addr = entry.email
    try:
        entry.delete()
        storage.save()
        flash(f"🗑️ '{addr}' removed.", "success")
        logger.info("Notification email deleted: %s", addr)
    except Exception as e:
        logger.error("Failed to delete notification email: %s", e)
        flash("Failed to delete. Please try again.", "danger")

    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/emails/<int:email_id>/toggle", methods=["POST"])
@super_admin_required
def toggle_email(email_id):
    """Toggle active/inactive status of a notification email."""
    from models.notification_email import NotificationEmail

    entry = storage.session().query(NotificationEmail).get(email_id)
    if not entry:
        flash("Email not found.", "danger")
        return redirect(url_for("admin.dashboard"))

    entry.is_active = not entry.is_active
    storage.save()
    status = "activated" if entry.is_active else "deactivated"
    flash(f"📧 '{entry.email}' {status}.", "success")
    return redirect(url_for("admin.dashboard"))
