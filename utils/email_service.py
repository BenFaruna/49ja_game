"""Email notification service — sends switch-trigger alerts via Gmail SMTP."""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List

import mailtrap as mt

import models
from models.notification_email import NotificationEmail
from utils.logger import get_logger

logger = get_logger(__name__, "server.log")

# ---------------------------------------------------------------------------
# Config — sourced from environment variables
# ---------------------------------------------------------------------------
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")  # Gmail address
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")  # Gmail App Password
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "49ja Analytics")
MAILTRAP_TOKEN = os.getenv("MAILTRAP_TOKEN", "")
IS_SANDBOX = os.getenv("MAILTRAP_USE_SANDBOX", "true").lower() == "true"
INBOX_ID = os.getenv("MAILTRAP_INBOX_ID")
HOSTNAME = os.getenv("HOSTNAME", "localhost")


def _is_configured() -> bool:
    """Return True when SMTP credentials are present."""
    return bool(SMTP_USER and SMTP_PASSWORD) or bool(MAILTRAP_TOKEN)


# ---------------------------------------------------------------------------
# Recipient queries
# ---------------------------------------------------------------------------


def get_active_recipients(threshold: int | None = None) -> List[NotificationEmail]:
    """Return active notification emails, optionally filtered by threshold."""
    session = models.storage.session()
    query = session.query(NotificationEmail).filter_by(is_active=True)
    if threshold is not None:
        query = query.filter(NotificationEmail.alert_threshold <= threshold)
    return query.all()


# ---------------------------------------------------------------------------
# Email builder
# ---------------------------------------------------------------------------


def _build_alert_html(game_id: int, trigger_ids: List[int], overall_losses: int) -> str:
    """Return a styled HTML body for the alert email."""
    triggers_str = ", ".join(f"{t}-Switch" for t in trigger_ids)
    return f"""
    <div style="font-family:'Inter',Arial,sans-serif; max-width:520px; margin:auto;
                background:#1a1a2e; color:#e0e0e0; border-radius:12px;
                overflow:hidden; border:1px solid #2a2a4a;">
      <div style="background:linear-gradient(135deg,#e94560,#c23152);
                  padding:24px 28px; text-align:center;">
        <h1 style="margin:0; font-size:22px; color:#fff;">🚨 Switch Trigger Alert</h1>
      </div>
      <div style="padding:24px 28px;">
        <p style="font-size:15px; line-height:1.6;">
          <strong>{overall_losses} consecutive losses</strong> detected on
          Draw <strong>#{game_id}</strong>.
        </p>
        <table style="width:100%; border-collapse:collapse; margin:16px 0;">
          <tr>
            <td style="padding:8px 12px; background:#16213e; border-radius:6px 0 0 6px;
                       font-size:13px; color:#8892b0;">Triggers Fired</td>
            <td style="padding:8px 12px; background:#16213e; border-radius:0 6px 6px 0;
                       font-weight:600; color:#e94560;">{triggers_str}</td>
          </tr>
          <tr><td colspan="2" style="height:6px;"></td></tr>
          <tr>
            <td style="padding:8px 12px; background:#16213e; border-radius:6px 0 0 6px;
                       font-size:13px; color:#8892b0;">Draw ID</td>
            <td style="padding:8px 12px; background:#16213e; border-radius:0 6px 6px 0;
                       font-weight:600;">#{game_id}</td>
          </tr>
          <tr><td colspan="2" style="height:6px;"></td></tr>
          <tr>
            <td style="padding:8px 12px; background:#16213e; border-radius:6px 0 0 6px;
                       font-size:13px; color:#8892b0;">Consecutive Losses</td>
            <td style="padding:8px 12px; background:#16213e; border-radius:0 6px 6px 0;
                       font-weight:600; color:#ffc107;">{overall_losses}</td>
          </tr>
        </table>
        <p style="font-size:12px; color:#6c7293; margin-top:20px; text-align:center;">
          This is an automated alert from 49ja Analytics.
        </p>
      </div>
    </div>
    """


# ---------------------------------------------------------------------------
# Send logic
# ---------------------------------------------------------------------------


def _send_email(to_addr: str, subject: str, html_body: str) -> bool:
    """Send a single email via SMTP. Returns True on success."""
    if MAILTRAP_TOKEN:
        return _use_mailtrap(to_addr, subject, html_body)

    return _use_smtplib(to_addr, subject, html_body)


def _use_mailtrap(to_addr: str, subject: str, html_body: str) -> bool:
    mail = mt.Mail(
        sender=mt.Address(email=f"49ja@{HOSTNAME}", name="49ja Alerts"),
        to=[mt.Address(email=to_addr)],
        subject=subject,
        html=html_body,
        category="49jaAlerts",
    )

    client = mt.MailtrapClient(
        token=MAILTRAP_TOKEN,
        sandbox=IS_SANDBOX,
        inbox_id=INBOX_ID if IS_SANDBOX else None,
    )
    response = client.send(mail)
    if response.get("success"):
        logger.info("✉️  Email sent to %s", to_addr)
        return True
    else:
        logger.error("Failed to send email to %s: %s", to_addr, response.errors)

    return False


def _use_smtplib(to_addr: str, subject: str, html_body: str) -> bool:
    msg = MIMEMultipart("alternative")
    msg["From"] = f"49ja@{HOSTNAME}"
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to_addr, msg.as_string())
        logger.info("✉️  Email sent to %s", to_addr)
        return True
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to_addr, exc)
        return False


def send_alert_emails(game_id: int, trigger_ids: List[int], overall_losses: int) -> int:
    """Send alert notifications to all qualifying recipients.

    Returns the number of emails successfully sent.
    """
    if not _is_configured():
        logger.warning("SMTP not configured — skipping email notifications.")
        return 0

    recipients = get_active_recipients(threshold=overall_losses)
    if not recipients:
        logger.info(
            "No active recipients with threshold <= %d — no emails to send.",
            overall_losses,
        )
        return 0

    subject = f"🚨 49ja Alert: {overall_losses} Consecutive Losses — Draw #{game_id}"
    html_body = _build_alert_html(game_id, trigger_ids, overall_losses)

    sent = 0
    for recipient in recipients:
        if _send_email(recipient.email, subject, html_body):
            sent += 1

    logger.info("Alert emails sent: %d/%d for draw #%d", sent, len(recipients), game_id)
    return sent
