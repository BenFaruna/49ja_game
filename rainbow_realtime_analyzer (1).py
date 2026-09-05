from __future__ import annotations

import json
import logging
import math
import os
import signal
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
    select,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is required. Example: "
        "postgresql+psycopg://user:password@localhost:5432/dbname"
    )

POLL_INTERVAL_SECONDS = float(os.environ.get("POLL_INTERVAL_SECONDS", "1.0"))
LOOKBACK_ROWS = max(130, int(os.environ.get("ANALYSIS_LOOKBACK_ROWS", "130")))
PROCESS_BATCH_SIZE = max(1, int(os.environ.get("PROCESS_BATCH_SIZE", "100")))
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# On a brand-new analysis table, analyze the current latest draw once and then
# continue prospectively. Set BACKFILL_EXISTING=true to process all rows instead.
BACKFILL_EXISTING = os.environ.get("BACKFILL_EXISTING", "false").lower() in {
    "1",
    "true",
    "yes",
    "y",
}

# Frozen BC thresholds. Do not tune these during live operation.
WINDOW = 100
CORE_SPREAD_MAX = 4
DELTA5_SPREAD_MAX = -4
ZERO_MEAN_MAX = 8.0
AGE3_SPREAD_MIN = 6
A_PLUS_STRONG_S2_MIN_MAX = 7

# A current BC state plus the previous state and their respective 5-draw
# comparisons requires 106 consecutive raw draws.
MIN_CONTIGUOUS_ROWS = 106

COLOURS = ("green", "red", "blue")
COUNT_COLUMN = {"green": "g_count", "red": "r_count", "blue": "b_count"}
EVENT_KEYS = ("0", "2+", "3+", "4+", "5+", "6")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("rainbow-realtime")

# -----------------------------------------------------------------------------
# Database setup
# -----------------------------------------------------------------------------

engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, future=True)

source_metadata = MetaData()
game_data = Table("game_data", source_metadata, autoload_with=engine)

REQUIRED_COLUMNS = {
    "id",
    "r_count",
    "g_count",
    "b_count",
    "y_count",
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
}
missing_columns = REQUIRED_COLUMNS - set(game_data.c.keys())
if missing_columns:
    raise RuntimeError(
        f"game_data is missing required columns: {sorted(missing_columns)}"
    )


class AnalysisBase(DeclarativeBase):
    pass


class RainbowAnalysis(AnalysisBase):
    """Prospective state/signal log produced by this analyser."""

    __tablename__ = "rainbow_analysis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    continuity_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)

    bc_tier: Mapped[str] = mapped_column(String(24), nullable=False, default="NO_BC")
    bc_action: Mapped[str] = mapped_column(String(32), nullable=False, default="OBSERVE")
    bc_strong: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    signal_prediction: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    signal_target_game_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    signal_actual: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    signal_won: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    green_state: Mapped[Optional[str]] = mapped_column(String(96), nullable=True)
    red_state: Mapped[Optional[str]] = mapped_column(String(96), nullable=True)
    blue_state: Mapped[Optional[str]] = mapped_column(String(96), nullable=True)

    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)


AnalysisBase.metadata.create_all(engine)

# -----------------------------------------------------------------------------
# Math / rolling-state model
# -----------------------------------------------------------------------------


def hypergeom_expected_exact_counts() -> Dict[int, float]:
    """Expected exact RGB colour counts in 100 draws.

    Each RGB colour owns 16 of the 49 balls and 6 balls are sampled without
    replacement, so X ~ Hypergeometric(N=49, K=16, n=6).
    """

    denom = math.comb(49, 6)
    out: Dict[int, float] = {}
    for k in range(7):
        probability = math.comb(16, k) * math.comb(33, 6 - k) / denom
        out[k] = 100.0 * probability
    return out


EXPECTED_EXACT = hypergeom_expected_exact_counts()


@dataclass
class RowData:
    id: int
    r_count: int
    g_count: int
    b_count: int
    y_count: int


@dataclass
class ColourMetrics:
    frequency: Dict[str, int]
    last_drawn: Dict[str, int]
    streak: Dict[str, int]
    exact: Dict[int, int]
    t32: float
    t43: float
    expected_delta: Dict[int, float]
    current_count: int


@dataclass
class RollingState:
    game_id: int
    colours: Dict[str, ColourMetrics]
    spread2: int
    zero_mean: float
    age3_spread: int
    s2_min: int
    actual_rainbow: str


@dataclass
class BcDecision:
    current_spread: int
    spread_5_ago: int
    delta5: int
    core_raw: bool
    previous_core_raw: bool
    fresh_entry: bool
    zero_mean: float
    zero_calm: bool
    age3_spread: int
    age3_pass: bool
    s2_min: int
    strong_flag: bool
    tier: str
    action: str
    prediction: Optional[str]


def event_matches(count: int, key: str) -> bool:
    if key == "0":
        return count == 0
    if key == "2+":
        return count >= 2
    if key == "3+":
        return count >= 3
    if key == "4+":
        return count >= 4
    if key == "5+":
        return count >= 5
    if key == "6":
        return count == 6
    raise ValueError(f"Unknown event key: {key}")


def max_true_run(flags: Sequence[bool]) -> int:
    best = 0
    current = 0
    for flag in flags:
        if flag:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def age_since_last(flags: Sequence[bool]) -> int:
    for age, flag in enumerate(reversed(flags)):
        if flag:
            return age
    return WINDOW


def actual_rainbow(row: RowData) -> str:
    counts = {"RED": row.r_count, "GREEN": row.g_count, "BLUE": row.b_count}
    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    if ordered[0][1] > ordered[1][1]:
        return ordered[0][0]
    return "NONE"


def validate_row(row: RowData) -> None:
    if any(v < 0 or v > 6 for v in (row.r_count, row.g_count, row.b_count, row.y_count)):
        raise ValueError(f"Invalid colour count in draw {row.id}")
    if row.r_count + row.g_count + row.b_count + row.y_count != 6:
        raise ValueError(
            f"Colour counts do not sum to 6 in draw {row.id}: "
            f"R={row.r_count}, G={row.g_count}, B={row.b_count}, Y={row.y_count}"
        )


def compute_colour_metrics(window: Sequence[RowData], colour: str) -> ColourMetrics:
    attr = COUNT_COLUMN[colour]
    counts = [getattr(row, attr) for row in window]

    frequency: Dict[str, int] = {}
    last_drawn: Dict[str, int] = {}
    streak: Dict[str, int] = {}

    for key in EVENT_KEYS:
        flags = [event_matches(count, key) for count in counts]
        frequency[key] = sum(flags)
        last_drawn[key] = age_since_last(flags)
        streak[key] = max_true_run(flags)

    exact = {
        0: frequency["0"],
        1: WINDOW - frequency["0"] - frequency["2+"],
        2: frequency["2+"] - frequency["3+"],
        3: frequency["3+"] - frequency["4+"],
        4: frequency["4+"] - frequency["5+"],
        5: frequency["5+"] - frequency["6"],
        6: frequency["6"],
    }

    t32 = frequency["3+"] / frequency["2+"] if frequency["2+"] else 0.0
    t43 = frequency["4+"] / frequency["3+"] if frequency["3+"] else 0.0
    expected_delta = {k: exact[k] - EXPECTED_EXACT[k] for k in range(7)}

    return ColourMetrics(
        frequency=frequency,
        last_drawn=last_drawn,
        streak=streak,
        exact=exact,
        t32=t32,
        t43=t43,
        expected_delta=expected_delta,
        current_count=counts[-1],
    )


def compute_rolling_state(window: Sequence[RowData]) -> RollingState:
    if len(window) != WINDOW:
        raise ValueError(f"Rolling window must contain {WINDOW} rows")

    for row in window:
        validate_row(row)

    colours = {colour: compute_colour_metrics(window, colour) for colour in COLOURS}
    two_plus = [colours[c].frequency["2+"] for c in COLOURS]
    zeroes = [colours[c].frequency["0"] for c in COLOURS]
    ages3 = [colours[c].last_drawn["3+"] for c in COLOURS]
    s2 = [colours[c].streak["2+"] for c in COLOURS]

    return RollingState(
        game_id=window[-1].id,
        colours=colours,
        spread2=max(two_plus) - min(two_plus),
        zero_mean=sum(zeroes) / 3.0,
        age3_spread=max(ages3) - min(ages3),
        s2_min=min(s2),
        actual_rainbow=actual_rainbow(window[-1]),
    )


def build_states(contiguous_rows: Sequence[RowData]) -> List[RollingState]:
    if len(contiguous_rows) < WINDOW:
        return []
    states: List[RollingState] = []
    for end in range(WINDOW - 1, len(contiguous_rows)):
        window = contiguous_rows[end - WINDOW + 1 : end + 1]
        states.append(compute_rolling_state(window))
    return states


def bc_decision(states: Sequence[RollingState]) -> BcDecision:
    if len(states) < 7:
        raise ValueError("Need at least 7 rolling states (106 consecutive raw draws)")

    current = states[-1]
    previous = states[-2]
    five_ago = states[-6]
    six_ago = states[-7]

    delta5 = current.spread2 - five_ago.spread2
    previous_delta5 = previous.spread2 - six_ago.spread2

    core_raw = current.spread2 <= CORE_SPREAD_MAX and delta5 <= DELTA5_SPREAD_MAX
    previous_core_raw = (
        previous.spread2 <= CORE_SPREAD_MAX
        and previous_delta5 <= DELTA5_SPREAD_MAX
    )
    fresh_entry = core_raw and not previous_core_raw

    zero_calm = current.zero_mean <= ZERO_MEAN_MAX
    age3_pass = current.age3_spread >= AGE3_SPREAD_MIN

    tier = "NO_BC"
    action = "OBSERVE"
    prediction: Optional[str] = None
    strong = False

    if fresh_entry:
        tier = "BC-CORE"
        action = "WATCH_ONLY"
        if zero_calm:
            tier = "BC-A"
            action = "TEST_NEXT_DRAW"
            prediction = "NONE"
            if age3_pass:
                tier = "BC-A+"
                action = "TEST_NEXT_DRAW"
                prediction = "NONE"
                strong = current.s2_min <= A_PLUS_STRONG_S2_MIN_MAX

    return BcDecision(
        current_spread=current.spread2,
        spread_5_ago=five_ago.spread2,
        delta5=delta5,
        core_raw=core_raw,
        previous_core_raw=previous_core_raw,
        fresh_entry=fresh_entry,
        zero_mean=current.zero_mean,
        zero_calm=zero_calm,
        age3_spread=current.age3_spread,
        age3_pass=age3_pass,
        s2_min=current.s2_min,
        strong_flag=strong,
        tier=tier,
        action=action,
        prediction=prediction,
    )


def colour_change(current: ColourMetrics, previous: ColourMetrics) -> Dict[str, int]:
    return {
        "d2plus": current.frequency["2+"] - previous.frequency["2+"],
        "d3plus": current.frequency["3+"] - previous.frequency["3+"],
        "d4plus": current.frequency["4+"] - previous.frequency["4+"],
        "d5plus": current.frequency["5+"] - previous.frequency["5+"],
        "d_exact2": current.exact[2] - previous.exact[2],
        "d_exact3": current.exact[3] - previous.exact[3],
    }


def is_release(cur: ColourMetrics, prev: ColourMetrics) -> bool:
    d = colour_change(cur, prev)
    return d["d_exact2"] < 0 and d["d3plus"] > 0 and d["d4plus"] > 0


def is_ignition(cur: ColourMetrics, prev: ColourMetrics) -> bool:
    d = colour_change(cur, prev)
    return d["d_exact2"] < 0 and d["d3plus"] > 0 and d["d4plus"] <= 0


def diagnostic_flags(cur: ColourMetrics) -> List[str]:
    """Expected-probability diagnostics only; these are not betting rules."""

    flags: List[str] = []
    if cur.exact[0] >= EXPECTED_EXACT[0] + 4:
        flags.append("ZERO_HIGH")
    if cur.exact[2] >= 37:
        flags.append("EXACT2_HIGH")
    if cur.exact[3] >= EXPECTED_EXACT[3] + 4:
        flags.append("EXACT3_HIGH")
    if cur.exact[4] <= EXPECTED_EXACT[4] - 2:
        flags.append("EXACT4_LOW")
    if cur.last_drawn["4+"] >= 20:
        flags.append("4PLUS_STALE")
    if cur.last_drawn["5+"] >= 40:
        flags.append("5PLUS_STALE")
    return flags


def classify_colour(
    current: ColourMetrics,
    previous: ColourMetrics,
    previous_previous: Optional[ColourMetrics],
) -> str:
    """Deterministic lifecycle label.

    These labels describe rolling-state transitions. They are intentionally
    separate from the frozen BC next-draw signal engine.
    """

    d = colour_change(current, previous)
    prev_was_release = (
        previous_previous is not None and is_release(previous, previous_previous)
    )
    prev_was_ignition = (
        previous_previous is not None and is_ignition(previous, previous_previous)
    )

    # 1) Confirmed synchronous transmission.
    if is_release(current, previous):
        return "FULL_RELEASE"

    # 2) Middle transmission without 4+ confirmation.
    if is_ignition(current, previous):
        return "IGNITION_WATCH"

    # 3) A fresh deep event after stale depth, without release geometry.
    if current.current_count >= 5 and previous.last_drawn["5+"] >= 15:
        return "DEEP_5PLUS_SHOCK_NO_RELEASE"
    if current.current_count >= 4 and previous.last_drawn["4+"] >= 15:
        return "LATE_4PLUS_SHOCK_NO_RELEASE"

    # 4) Resolve the immediately preceding lifecycle state.
    if prev_was_release:
        if d["d4plus"] >= 0 and d["d3plus"] >= 0:
            return "POST_RELEASE_PERSISTENCE"
        return "POST_RELEASE_COOLING"

    if prev_was_ignition and (d["d3plus"] <= 0 or d["d_exact2"] >= 0):
        return "FAILED_IGNITION_COOLING"

    # 5) Structural congestion/starvation diagnostics.
    if (
        current.exact[3] >= EXPECTED_EXACT[3] + 4
        and current.frequency["4+"] <= 6
        and current.last_drawn["4+"] >= 15
    ):
        return "EXACT3_CONGESTION_DEEP_TAIL_STARVATION"

    if current.exact[2] >= 37 and current.last_drawn["4+"] >= 8:
        return "EXACT2_CONGESTION"

    # 6) Generic cooling / rebuilding states.
    if d["d2plus"] < 0 and d["d3plus"] < 0 and d["d4plus"] <= 0:
        if current.last_drawn["4+"] >= 15:
            return "HARD_COOLING_STALE_DEPTH"
        return "BROAD_COOLING"

    if d["d_exact2"] > 0 and d["d3plus"] <= 0:
        return "RE_CONGESTION"

    if d["d2plus"] > 0 and d["d3plus"] <= 0:
        return "SHALLOW_BREADTH_BUILD"

    if d["d3plus"] > 0 and d["d4plus"] <= 0:
        return "MIDDLE_REFRESH"

    if d["d2plus"] > 0 and d["d3plus"] > 0 and d["d4plus"] > 0:
        return "SYNCHRONIZED_EXPANSION_RELEASE_WATCH"

    return "STABLE_OBSERVE"

# -----------------------------------------------------------------------------
# Database IO
# -----------------------------------------------------------------------------


def mapping_to_row(m: Mapping[str, Any]) -> RowData:
    return RowData(
        id=int(m["id"]),
        r_count=int(m["r_count"]),
        g_count=int(m["g_count"]),
        b_count=int(m["b_count"]),
        y_count=int(m["y_count"]),
    )


def fetch_recent_rows(session: Session, upto_game_id: int, limit: int) -> List[RowData]:
    stmt = (
        select(
            game_data.c.id,
            game_data.c.r_count,
            game_data.c.g_count,
            game_data.c.b_count,
            game_data.c.y_count,
        )
        .where(game_data.c.id <= upto_game_id)
        .order_by(game_data.c.id.desc())
        .limit(limit)
    )
    rows = [mapping_to_row(row) for row in session.execute(stmt).mappings().all()]
    rows.reverse()
    return rows


def contiguous_suffix(rows: Sequence[RowData]) -> List[RowData]:
    if not rows:
        return []
    start = len(rows) - 1
    while start > 0 and rows[start].id == rows[start - 1].id + 1:
        start -= 1
    return list(rows[start:])


def latest_game_id(session: Session) -> Optional[int]:
    value = session.execute(select(func.max(game_data.c.id))).scalar_one_or_none()
    return int(value) if value is not None else None


def min_game_id(session: Session) -> Optional[int]:
    value = session.execute(select(func.min(game_data.c.id))).scalar_one_or_none()
    return int(value) if value is not None else None


def last_processed_game_id(session: Session) -> Optional[int]:
    value = session.execute(select(func.max(RainbowAnalysis.game_id))).scalar_one_or_none()
    return int(value) if value is not None else None


def fetch_new_ids(session: Session, after_id: int, batch_size: int) -> List[int]:
    stmt = (
        select(game_data.c.id)
        .where(game_data.c.id > after_id)
        .order_by(game_data.c.id.asc())
        .limit(batch_size)
    )
    return [int(x) for x in session.execute(stmt).scalars().all()]


def get_row_by_id(session: Session, game_id: int) -> Optional[RowData]:
    stmt = select(
        game_data.c.id,
        game_data.c.r_count,
        game_data.c.g_count,
        game_data.c.b_count,
        game_data.c.y_count,
    ).where(game_data.c.id == game_id)
    m = session.execute(stmt).mappings().first()
    return mapping_to_row(m) if m else None


def grade_pending_signal(session: Session, game_id: int) -> None:
    row = get_row_by_id(session, game_id)
    if row is None:
        return
    actual = actual_rainbow(row)

    pending = session.execute(
        select(RainbowAnalysis).where(
            RainbowAnalysis.signal_target_game_id == game_id,
            RainbowAnalysis.signal_prediction.is_not(None),
            RainbowAnalysis.signal_actual.is_(None),
        )
    ).scalars().all()

    for analysis in pending:
        analysis.signal_actual = actual
        analysis.signal_won = analysis.signal_prediction == actual
        log.info(
            "GRADED signal from draw %s -> target %s | predicted=%s actual=%s won=%s",
            analysis.game_id,
            game_id,
            analysis.signal_prediction,
            actual,
            analysis.signal_won,
        )


def serialize_colour(metrics: ColourMetrics, state_label: str) -> Dict[str, Any]:
    return {
        "state": state_label,
        "frequency": metrics.frequency,
        "last_drawn": metrics.last_drawn,
        "streak": metrics.streak,
        "exact": {str(k): v for k, v in metrics.exact.items()},
        "t32": round(metrics.t32, 6),
        "t43": round(metrics.t43, 6),
        "expected_delta": {str(k): round(v, 4) for k, v in metrics.expected_delta.items()},
        "diagnostic_flags": diagnostic_flags(metrics),
        "current_count": metrics.current_count,
    }


def process_game_id(session: Session, game_id: int) -> RainbowAnalysis:
    # Grade any signal that was explicitly targeted at this newly completed draw.
    grade_pending_signal(session, game_id)

    recent = fetch_recent_rows(session, game_id, LOOKBACK_ROWS)
    suffix = contiguous_suffix(recent)

    # Idempotency guard.
    existing = session.execute(
        select(RainbowAnalysis).where(RainbowAnalysis.game_id == game_id)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    if len(suffix) < MIN_CONTIGUOUS_ROWS:
        snapshot = {
            "game_id": game_id,
            "status": "INSUFFICIENT_CONTIGUOUS_DATA",
            "continuous_rows": len(suffix),
            "required_rows": MIN_CONTIGUOUS_ROWS,
            "earliest_contiguous_id": suffix[0].id if suffix else None,
        }
        record = RainbowAnalysis(
            game_id=game_id,
            continuity_ok=False,
            status="INSUFFICIENT_CONTIGUOUS_DATA",
            bc_tier="NO_BC",
            bc_action="OBSERVE",
            bc_strong=False,
            snapshot_json=json.dumps(snapshot, separators=(",", ":")),
        )
        session.add(record)
        session.flush()
        log.warning(
            "Draw %s skipped: only %s consecutive rows available; need %s",
            game_id,
            len(suffix),
            MIN_CONTIGUOUS_ROWS,
        )
        return record

    # We only need the contiguous suffix, not rows before the most recent gap.
    states = build_states(suffix)
    decision = bc_decision(states)
    current_state = states[-1]
    previous_state = states[-2]
    prevprev_state = states[-3] if len(states) >= 3 else None

    colour_labels: Dict[str, str] = {}
    for colour in COLOURS:
        colour_labels[colour] = classify_colour(
            current_state.colours[colour],
            previous_state.colours[colour],
            prevprev_state.colours[colour] if prevprev_state else None,
        )

    signal_target = game_id + 1 if decision.prediction else None

    snapshot = {
        "game_id": game_id,
        "actual_rainbow": current_state.actual_rainbow,
        "bc": asdict(decision),
        "expected_exact_per_100": {
            str(k): round(v, 6) for k, v in EXPECTED_EXACT.items()
        },
        "colours": {
            colour: serialize_colour(current_state.colours[colour], colour_labels[colour])
            for colour in COLOURS
        },
    }

    record = RainbowAnalysis(
        game_id=game_id,
        continuity_ok=True,
        status="OK",
        bc_tier=decision.tier,
        bc_action=decision.action,
        bc_strong=decision.strong_flag,
        signal_prediction=decision.prediction,
        signal_target_game_id=signal_target,
        green_state=colour_labels["green"],
        red_state=colour_labels["red"],
        blue_state=colour_labels["blue"],
        snapshot_json=json.dumps(snapshot, separators=(",", ":")),
    )
    session.add(record)
    session.flush()

    print_analysis(current_state, decision, colour_labels)
    return record

# -----------------------------------------------------------------------------
# Console output
# -----------------------------------------------------------------------------


def print_analysis(
    current: RollingState,
    decision: BcDecision,
    labels: Dict[str, str],
) -> None:
    strong_suffix = " + STRONG_FLAG" if decision.strong_flag else ""
    lines = [
        "",
        "=" * 78,
        f"DRAW {current.game_id} | ACTUAL RAINBOW: {current.actual_rainbow}",
        "-" * 78,
        (
            f"BC: {decision.tier}{strong_suffix} | spread={decision.current_spread} "
            f"| Δ5={decision.delta5:+d} | zero_mean={decision.zero_mean:.2f} "
            f"| age3_spread={decision.age3_spread} | s2_min={decision.s2_min}"
        ),
        (
            f"BC flags: raw={decision.core_raw} fresh_entry={decision.fresh_entry} "
            f"zero_calm={decision.zero_calm} age3_pass={decision.age3_pass}"
        ),
    ]

    if decision.prediction:
        lines.append(
            f"PRE-DECLARED NEXT-DRAW TEST: {decision.prediction} "
            f"for draw {current.game_id + 1}"
        )
    else:
        lines.append("ACTION: observe only")

    lines.append("-" * 78)
    for colour in COLOURS:
        m = current.colours[colour]
        flags = diagnostic_flags(m)
        flag_text = ",".join(flags) if flags else "none"
        lines.append(
            f"{colour.upper():5s} | {labels[colour]} | "
            f"2+/3+/4+/5+={m.frequency['2+']}/{m.frequency['3+']}/"
            f"{m.frequency['4+']}/{m.frequency['5+']} | "
            f"E2={m.exact[2]} E3={m.exact[3]} | "
            f"L3/L4/L5={m.last_drawn['3+']}/{m.last_drawn['4+']}/"
            f"{m.last_drawn['5+']} | flags={flag_text}"
        )
    lines.append("=" * 78)
    print("\n".join(lines), flush=True)

# -----------------------------------------------------------------------------
# Main realtime loop
# -----------------------------------------------------------------------------


_running = True


def _stop(_signum: int, _frame: Any) -> None:
    global _running
    _running = False


signal.signal(signal.SIGINT, _stop)
signal.signal(signal.SIGTERM, _stop)


def initialize_cursor(session: Session) -> Optional[int]:
    processed = last_processed_game_id(session)
    if processed is not None:
        return processed

    latest = latest_game_id(session)
    if latest is None:
        return None

    if BACKFILL_EXISTING:
        minimum = min_game_id(session)
        return (minimum - 1) if minimum is not None else None

    # Analyze the latest current state once so it can prospectively target the
    # next draw, without replaying historical rows as if they were live.
    process_game_id(session, latest)
    session.commit()
    return latest


def run_forever() -> None:
    log.info("Starting Rainbow realtime analyser")
    log.info("Source table: game_data")
    log.info("Analysis table: rainbow_analysis")
    log.info("Poll interval: %.3fs", POLL_INTERVAL_SECONDS)
    log.info(
        "Frozen BC thresholds: spread<=%s, Δ5<=%s, zero<=%.1f, age3>=%s, strong_s2<=%s",
        CORE_SPREAD_MAX,
        DELTA5_SPREAD_MAX,
        ZERO_MEAN_MAX,
        AGE3_SPREAD_MIN,
        A_PLUS_STRONG_S2_MIN_MAX,
    )

    cursor: Optional[int] = None

    while _running:
        try:
            with SessionLocal() as session:
                if cursor is None:
                    cursor = initialize_cursor(session)
                    if cursor is None:
                        log.info("game_data is empty; waiting for first draw")
                        time.sleep(POLL_INTERVAL_SECONDS)
                        continue

                new_ids = fetch_new_ids(session, cursor, PROCESS_BATCH_SIZE)
                if not new_ids:
                    time.sleep(POLL_INTERVAL_SECONDS)
                    continue

                for game_id in new_ids:
                    process_game_id(session, game_id)
                    session.commit()
                    cursor = game_id

        except SQLAlchemyError:
            log.exception("Database error; retrying after poll interval")
            time.sleep(POLL_INTERVAL_SECONDS)
        except Exception:
            log.exception("Analysis error; retrying after poll interval")
            time.sleep(POLL_INTERVAL_SECONDS)

    log.info("Rainbow realtime analyser stopped")


if __name__ == "__main__":
    run_forever()
