"""ORM models for the Switch Trigger Analytics system.

Persists the state of 8 independent switch-trigger trackers and
records every alert (8 consecutive losses) they produce.
"""

from sqlalchemy import Column, DateTime, Integer, String

from models.base import Base, BaseModel, utc_now


class SwitchTrackerState(BaseModel, Base):
    """Persisted state for a single switch-trigger tracker (1 through 8)."""

    __tablename__ = "switch_tracker_state"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trigger_id = Column(Integer, unique=True, index=True, nullable=False)
    assumed_direction = Column(String(1), nullable=False, default="L")
    overall_losses = Column(Integer, nullable=False, default=0)
    trigger_losses = Column(Integer, nullable=False, default=0)
    last_game_id = Column(Integer, nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __str__(self):
        return (
            f"[SwitchTrackerState] trigger={self.trigger_id} "
            f"dir={self.assumed_direction} losses={self.overall_losses}/{self.trigger_losses}"
        )


class SwitchAlert(BaseModel, Base):
    """Historical log of every 8-consecutive-loss alert fired."""

    __tablename__ = "switch_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, index=True, nullable=False)
    trigger_id = Column(Integer, nullable=False)
    direction_at_alert = Column(String(1), nullable=False)
    created_at = Column(DateTime, default=utc_now)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __str__(self):
        return (
            f"[SwitchAlert] game={self.game_id} trigger={self.trigger_id} "
            f"dir={self.direction_at_alert}"
        )
