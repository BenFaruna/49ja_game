"""ORM model for email notification recipients."""

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from models.base import Base, BaseModel, utc_now


class NotificationEmail(BaseModel, Base):
    """An email address registered to receive switch-trigger alerts."""

    __tablename__ = "notification_emails"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    label = Column(String(80), nullable=True)  # optional friendly name
    alert_threshold = Column(Integer, nullable=False, default=8)  # customisable per-recipient
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __str__(self):
        return (
            f"[NotificationEmail] {self.email} "
            f"(threshold={self.alert_threshold}, active={self.is_active})"
        )
