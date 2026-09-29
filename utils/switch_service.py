"""Switch Trigger Analytics — service layer.

Hosts the in-memory SwitchTriggerTracker / LiveDrawMonitor logic (extracted
verbatim from gemini-code-1789921893091.py) and bridges it to the SQLite
persistence layer via the existing ``models.storage`` singleton.

Public API
----------
- ``initialize_from_db()``   — call once at app startup
- ``process_new_draw(game_data)`` — call after every scraped draw is saved
- ``get_tracker_states()``   — returns list[dict] for the JSON endpoint
- ``get_alerts(limit, offset)`` — returns (total, list[dict]) for the JSON endpoint
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import models
from models.switch_tracker import SwitchAlert, SwitchTrackerState
from utils.logger import get_logger

logger = get_logger("switch_service")

# ---------------------------------------------------------------------------
# Outcome mapping: GameData.hi_lo_mid  →  H / L / M
# ---------------------------------------------------------------------------
OUTCOME_MAP: Dict[str, str] = {"Hi": "H", "Lo": "L", "Mid": "M"}


def _map_outcome(hi_lo_mid: str) -> Optional[str]:
    """Convert *hi_lo_mid* field value to the H/L/M alphabet the tracker uses."""
    return OUTCOME_MAP.get(hi_lo_mid)


class SwitchTriggerTracker:
    def __init__(self, trigger_value: int):
        """
        Initializes a single switch trigger tracker.
        :param trigger_value: The threshold for switching (1 through 8)
        """
        self.trigger_value = trigger_value
        self.assumed_direction = "L"  # Default starting assumption
        self.overall_losses = 0  # Tracks the total consecutive losing streak
        self.trigger_losses = 0  # Tracks losses on the current assumption

    def process_outcome(self, outcome: str) -> bool:
        """
        Processes a single live outcome and updates the trigger state.
        :param outcome: 'H', 'L', or 'M'
        :return: Boolean indicating if an alert should be triggered (hit exactly 8 overall losses)
        """
        is_win = outcome == self.assumed_direction

        if is_win:
            # A win resets both the overall progression and the trigger loss counter
            self.overall_losses = 0
            self.trigger_losses = 0
            return False
        else:
            # A loss increments both counters
            self.overall_losses += 1
            self.trigger_losses += 1

            # Check if we need to flip our assumption based on this specific trigger rule
            if self.trigger_losses == self.trigger_value:
                self.assumed_direction = "H" if self.assumed_direction == "L" else "L"
                self.trigger_losses = 0  # Reset trigger counter after flipping

            # Return True if we have hit exactly 8 consecutive losses overall
            if self.overall_losses == 8:
                return True

        return False


class LiveDrawMonitor:
    def __init__(self):
        """
        Initializes the monitor to track triggers 1 through 8 simultaneously.
        """
        # Create a dictionary of 8 independent trackers
        self.trackers: Dict[int, SwitchTriggerTracker] = {
            i: SwitchTriggerTracker(trigger_value=i) for i in range(1, 9)
        }
        self.draw_count = 0

    def feed_live_data(self, draw_id: int, outcome: str) -> List[int]:
        """
        Main entry point to pass data into the monitor.
        :param draw_id: The ID of the current game
        :param outcome: The result ('H', 'L', or 'M')
        :return: List of trigger_ids that hit exactly 8 consecutive losses
        """
        outcome = str(outcome).upper().strip()
        if outcome not in ("H", "L", "M"):
            logger.error("Invalid outcome '%s' received for Draw %s.", outcome, draw_id)
            return []

        self.draw_count += 1
        alerts_triggered: List[int] = []

        # Feed the outcome to all 8 triggers simultaneously
        for trigger_id, tracker in self.trackers.items():
            alert = tracker.process_outcome(outcome)
            if alert:
                alerts_triggered.append(trigger_id)

        return alerts_triggered


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
_monitor: Optional[LiveDrawMonitor] = None


def _get_monitor() -> LiveDrawMonitor:
    global _monitor
    if _monitor is None:
        _monitor = LiveDrawMonitor()
    return _monitor


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def _persist_tracker_states(game_id: int) -> None:
    """Write current in-memory tracker states to SQLite."""
    monitor = _get_monitor()
    session = models.storage._DBStorage__session  # access the scoped session

    for trigger_id, tracker in monitor.trackers.items():
        row = session.query(SwitchTrackerState).filter_by(trigger_id=trigger_id).first()
        if row is None:
            row = SwitchTrackerState(
                trigger_id=trigger_id,
                assumed_direction=tracker.assumed_direction,
                overall_losses=tracker.overall_losses,
                trigger_losses=tracker.trigger_losses,
                last_game_id=game_id,
            )
            session.add(row)
        else:
            row.assumed_direction = tracker.assumed_direction
            row.overall_losses = tracker.overall_losses
            row.trigger_losses = tracker.trigger_losses
            row.last_game_id = game_id

    try:
        session.commit()
    except Exception as exc:
        logger.error("Failed to persist tracker states: %s", exc)
        session.rollback()


def _record_alerts(game_id: int, trigger_ids: List[int]) -> None:
    """Record alert events in the switch_alerts table."""
    monitor = _get_monitor()

    for tid in trigger_ids:
        tracker = monitor.trackers[tid]
        alert = SwitchAlert(
            game_id=game_id,
            trigger_id=tid,
            direction_at_alert=tracker.assumed_direction,
        )
        alert.save()

    triggers_str = ", ".join(f"{t}-Switch" for t in trigger_ids)
    logger.warning(
        "🚨 DANGER ALERT: 8 CONSECUTIVE LOSSES — Draw #%s — Triggers: %s",
        game_id,
        triggers_str,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def initialize_from_db() -> None:
    """Restore tracker states from SQLite on application startup.

    If the ``switch_tracker_state`` table is empty the monitor starts fresh
    with default settings (all trackers assume ``'L'``).
    """
    global _monitor
    _monitor = LiveDrawMonitor()

    session = models.storage._DBStorage__session
    rows = session.query(SwitchTrackerState).all()

    if not rows:
        logger.info("No persisted switch-tracker state found — starting fresh.")
        return

    for row in rows:
        tid = row.trigger_id
        if tid not in _monitor.trackers:
            continue
        tracker = _monitor.trackers[tid]
        tracker.assumed_direction = row.assumed_direction
        tracker.overall_losses = row.overall_losses
        tracker.trigger_losses = row.trigger_losses

    _monitor.draw_count = max((r.last_game_id or 0 for r in rows), default=0)
    logger.info("Restored switch-tracker state from DB (%d tracker rows).", len(rows))


def process_new_draw(game_data) -> None:
    """Process a freshly-saved GameData through all 8 switch trackers.

    Called by the scraper immediately after ``game_data.save()``.
    """
    outcome = _map_outcome(game_data.hi_lo_mid)
    if outcome is None:
        logger.warning(
            "Could not map hi_lo_mid='%s' for draw #%s — skipping switch analysis.",
            game_data.hi_lo_mid,
            game_data.id,
        )
        return

    monitor = _get_monitor()
    alerts = monitor.feed_live_data(game_data.id, outcome)

    if alerts:
        _record_alerts(game_data.id, alerts)

    _persist_tracker_states(game_data.id)


def get_tracker_states() -> List[Dict]:
    """Return current state of all 8 trackers for the JSON API."""
    monitor = _get_monitor()
    session = models.storage._DBStorage__session

    states: List[Dict] = []
    for trigger_id in range(1, 9):
        tracker = monitor.trackers[trigger_id]

        # Fetch last_game_id from DB
        row = session.query(SwitchTrackerState).filter_by(trigger_id=trigger_id).first()
        last_game_id = row.last_game_id if row else None

        states.append(
            {
                "trigger_id": trigger_id,
                "assumed_direction": tracker.assumed_direction,
                "overall_losses": tracker.overall_losses,
                "trigger_losses": tracker.trigger_losses,
                "last_game_id": last_game_id,
            }
        )
    return states


def get_alerts(limit: int = 50, offset: int = 0) -> Tuple[int, List[Dict]]:
    """Return recent alerts for the JSON API.

    Returns ``(total_count, list_of_alert_dicts)``.
    """
    session = models.storage._DBStorage__session
    total = session.query(SwitchAlert).count()

    rows = (
        session.query(SwitchAlert)
        .order_by(SwitchAlert.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    alerts = [
        {
            "id": r.id,
            "game_id": r.game_id,
            "trigger_id": r.trigger_id,
            "direction_at_alert": r.direction_at_alert,
            "created_at": (
                r.created_at.strftime("%Y-%m-%dT%H:%M:%SZ") if r.created_at else None
            ),
        }
        for r in rows
    ]
    return total, alerts
