#!/usr/bin/python3
"""
Contains the class DBStorage
"""
from datetime import datetime, timedelta
from os import getenv

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

import models
from models.base import Base
from models.game_data import GameData
from logger import get_logger

logger = get_logger("db_storage")


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
        """query on the current database session based of time difference"""
        new_dict = {}
        try:
            objs = self.__session.query(GameData).filter(
                GameData.date >= (datetime.now() - timedelta(hours=float(hours)))
            )
            for obj in objs:
                key = obj.__class__.__name__ + "." + str(obj.id)
                new_dict[key] = obj
            return new_dict
        except Exception as e:
            logger.error(f"Database query error in time_diff(): {e}")
            self.__session.rollback()
            return {}

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
        sess_factory = sessionmaker(bind=self.__engine, expire_on_commit=False)
        session = scoped_session(sess_factory)
        self.__session = session

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
