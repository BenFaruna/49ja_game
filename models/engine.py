#!/usr/bin/python3
"""
Contains the class DBStorage
"""
from datetime import datetime, timedelta, timezone
from os import getenv

from sqlalchemy import create_engine, func, select, text, union_all
from sqlalchemy.orm import scoped_session, sessionmaker

import models
from models.base import Base
from models.game_data import GameData
from utils.logger import get_logger

logger = get_logger(__name__)

BALL_COLUMNS = ("first", "second", "third", "fourth", "fifth", "sixth")


class DBStorage:
    """interacts with the database"""

    __engine = None
    __session = None

    def __init__(self):
        """Instantiate a DBStorage object"""
        db_url = getenv("DB_URL", "sqlite:///game_data.db")
        self.__engine = create_engine(db_url)

    def all(self):
        """query on the current database session"""
        new_dict = {}
        try:
            objs = self.__session.query(GameData).all()
            for obj in objs:
                key = obj.__class__.__name__ + "." + str(obj.id)
                new_dict[key] = obj
            return new_dict
        except Exception as e:
            logger.error(f"Database query error in all(): {e}")
            self.__session.rollback()
            return {}

    def time_diff(self, hours=1.0):
        """query on the current database session based on relative UTC time difference"""
        new_dict = {}
        try:
            utc_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
                hours=float(hours)
            )
            objs = self.__session.query(GameData).filter(GameData.date >= utc_cutoff)
            for obj in objs:
                key = obj.__class__.__name__ + "." + str(obj.id)
                new_dict[key] = obj
            return new_dict
        except Exception as e:
            logger.error(f"Database query error in time_diff(): {e}")
            self.__session.rollback()
            return {}

    def filter_draws(
        self, hours=0.0, start_datetime=None, end_datetime=None, occurrence=0
    ):
        """Query game data filtered by time window, explicit datetime bounds, and color occurrence."""
        new_dict = {}
        try:
            objs = (
                self.__session.query(GameData)
                .filter(
                    *self._conditions(
                        hours=hours,
                        start_datetime=start_datetime,
                        end_datetime=end_datetime,
                        occurrence=occurrence,
                    )
                )
                .all()
            )
            for obj in objs:
                key = obj.__class__.__name__ + "." + str(obj.id)
                new_dict[key] = obj
            return new_dict
        except Exception as e:
            logger.error(f"Database query error in filter_draws(): {e}")
            self.__session.rollback()
            return {}

    # ------------------------------------------------------------------
    # Filtering helpers
    # ------------------------------------------------------------------

    def _conditions(
        self, hours=0.0, start_datetime=None, end_datetime=None, occurrence=0
    ):
        """Build the SQL filters shared by every read query.

        Explicit datetime bounds win over the relative window, matching the
        behaviour the history filters have always had.
        """
        conditions = []

        if start_datetime:
            conditions.append(GameData.date >= start_datetime)
        if end_datetime:
            conditions.append(GameData.date <= end_datetime)

        if not start_datetime and not end_datetime and hours:
            hours = float(hours)
            if hours > 0:
                utc_cutoff = datetime.now(timezone.utc).replace(
                    tzinfo=None
                ) - timedelta(hours=hours)
                conditions.append(GameData.date >= utc_cutoff)

        if occurrence:
            occurrence = int(occurrence)
            if occurrence > 0:
                conditions.append(
                    (GameData.r_count == occurrence)
                    | (GameData.g_count == occurrence)
                    | (GameData.b_count == occurrence)
                )

        return conditions

    @staticmethod
    def _empty_analytics():
        """The zero-value analytics payload used when there is nothing to aggregate."""
        return {
            "total_draws": 0,
            "latest_draw": None,
            "color_counts": {"Red": 0, "Blue": 0, "Green": 0, "Yellow": 0, "None": 0},
            "color_percentages": {
                "Red": 0,
                "Blue": 0,
                "Green": 0,
                "Yellow": 0,
                "None": 0,
            },
            "hi_lo_mid": {"Hi": 0, "Lo": 0, "Mid": 0},
            "ball_freq": {n: 0 for n in range(1, 50)},
            "avg_total": 0,
        }

    # ------------------------------------------------------------------
    # Read paths (SQL aggregation and SQL pagination)
    # ------------------------------------------------------------------

    def analytics(self, hours=0.0, start_datetime=None, end_datetime=None):
        """Dashboard analytics computed by the database, without loading rows."""
        result = self._empty_analytics()
        try:
            conditions = self._conditions(
                hours=hours,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
            )

            total_draws, total_sum = self.__session.execute(
                select(
                    func.count(GameData.id),
                    func.coalesce(func.sum(GameData.total), 0),
                ).where(*conditions)
            ).one()
            total_draws = int(total_draws or 0)
            result["total_draws"] = total_draws
            if total_draws == 0:
                return result

            colour_rows = self.__session.execute(
                select(GameData.colour, func.count(GameData.id))
                .where(*conditions)
                .group_by(GameData.colour)
            ).all()
            for colour, count in colour_rows:
                key = colour if colour in result["color_counts"] else "None"
                result["color_counts"][key] += int(count)

            range_rows = self.__session.execute(
                select(GameData.hi_lo_mid, func.count(GameData.id))
                .where(*conditions)
                .group_by(GameData.hi_lo_mid)
            ).all()
            for category, count in range_rows:
                key = category if category in result["hi_lo_mid"] else "Mid"
                result["hi_lo_mid"][key] += int(count)

            balls = union_all(
                *[
                    select(getattr(GameData, column).label("ball")).where(*conditions)
                    for column in BALL_COLUMNS
                ]
            ).subquery()
            frequency_rows = self.__session.execute(
                select(balls.c.ball, func.count()).group_by(balls.c.ball)
            ).all()
            for ball, count in frequency_rows:
                if ball is not None and 1 <= ball <= 49:
                    result["ball_freq"][int(ball)] += int(count)

            result["color_percentages"] = {
                name: round((count / total_draws) * 100, 1)
                for name, count in result["color_counts"].items()
            }
            result["avg_total"] = round(total_sum / total_draws, 1)

            return result
        except Exception as e:
            logger.error(f"Database analytics error: {e}")
            self.__session.rollback()
            return self._empty_analytics()

    def recent(self, limit=10):
        """Return the newest draws, most recent first."""
        try:
            return (
                self.__session.query(GameData)
                .order_by(GameData.date.desc(), GameData.id.desc())
                .limit(int(limit))
                .all()
            )
        except Exception as e:
            logger.error(f"Database query error in recent(): {e}")
            self.__session.rollback()
            return []

    def count_draws(
        self, hours=0.0, start_datetime=None, end_datetime=None, occurrence=0
    ):
        """Count draws matching the filters, in the database."""
        try:
            conditions = self._conditions(
                hours=hours,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                occurrence=occurrence,
            )
            total = self.__session.query(func.count(GameData.id)).filter(
                *conditions
            ).scalar()
            return int(total or 0)
        except Exception as e:
            logger.error(f"Database query error in count_draws(): {e}")
            self.__session.rollback()
            return 0

    def page_draws(
        self,
        hours=0.0,
        start_datetime=None,
        end_datetime=None,
        occurrence=0,
        limit=25,
        offset=0,
    ):
        """Return one page of draws, newest first."""
        try:
            conditions = self._conditions(
                hours=hours,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                occurrence=occurrence,
            )
            return (
                self.__session.query(GameData)
                .filter(*conditions)
                .order_by(GameData.date.desc(), GameData.id.desc())
                .limit(int(limit))
                .offset(int(offset))
                .all()
            )
        except Exception as e:
            logger.error(f"Database query error in page_draws(): {e}")
            self.__session.rollback()
            return []

    def iter_draws(
        self,
        hours=0.0,
        start_datetime=None,
        end_datetime=None,
        occurrence=0,
        batch_size=1000,
    ):
        """Yield draws newest first without materialising them all (used by CSV export)."""
        try:
            conditions = self._conditions(
                hours=hours,
                start_datetime=start_datetime,
                end_datetime=end_datetime,
                occurrence=occurrence,
            )
            query = (
                self.__session.query(GameData)
                .filter(*conditions)
                .order_by(GameData.date.desc(), GameData.id.desc())
                .yield_per(int(batch_size))
            )
            yield from query
        except Exception as e:
            logger.error(f"Database query error in iter_draws(): {e}")
            self.__session.rollback()

    def new(self, obj):
        """add the object to the current database session"""
        try:
            self.__session.add(obj)
        except Exception as e:
            logger.error(f"Error adding object to session: {e}")
            self.__session.rollback()

    def save(self):
        """commit all changes of the current database session"""
        try:
            self.__session.commit()
        except Exception as e:
            logger.error(f"Database commit error: {e}")
            self.__session.rollback()

    def delete(self, obj=None):
        """delete from the current database session obj if not None"""
        if obj is not None:
            try:
                self.__session.delete(obj)
            except Exception as e:
                logger.error(f"Error deleting object: {e}")
                self.__session.rollback()

    def reload(self):
        """reloads data from the database"""
        Base.metadata.create_all(self.__engine)
        self._ensure_indexes()
        sess_factory = sessionmaker(bind=self.__engine, expire_on_commit=False)
        session = scoped_session(sess_factory)
        self.__session = session

    def _ensure_indexes(self):
        """Create the indexes the read paths rely on, for databases that predate them.

        ``create_all`` never alters an existing table, so a database that already
        has ``game_data`` would never get the new index without this. The DDL is
        idempotent, so it is just a no-op on every start after the first.
        """
        try:
            with self.__engine.begin() as connection:
                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_game_data_date "
                        "ON game_data (date)"
                    )
                )
        except Exception as e:
            logger.error(f"Index creation failed: {e}")

    def session(self):
        """Return the current scoped session for direct model queries."""
        return self.__session

    def close(self):
        """call remove() method on the private session attribute"""
        if self.__session:
            self.__session.remove()

    @staticmethod
    def get(id_=None):
        """
        Returns the object based on its ID, or None if not found
        """
        all_cls = models.storage.all()
        for value in all_cls.values():
            if value.id == id_:
                return value
        return None

    @staticmethod
    def count():
        """
        count the number of objects in storage
        """
        return len(models.storage.all().values())
