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


class DBStorage:
    """interacts with the POSTGRESQL database"""
    __engine = None
    __session = None

    def __init__(self):
        """Instantiate a DBStorage object"""
        db_url = getenv("DB_URL", "sqlite:///game_data.db")
        self.__engine = create_engine(db_url)
        # Base.metadata.drop_all(self.__engine)

    def all(self):
        """query on the current database session"""
        new_dict = {}
        objs = self.__session.query(GameData).all()
        for obj in objs:
            key = obj.__class__.__name__ + '.' + str(obj.id)
            new_dict[key] = obj
        return new_dict

    def time_diff(self, hours=1.0):
        """query on the current database session based of time difference"""
        new_dict = {}
        objs = self.__session.query(GameData).filter(
            GameData.date >= (datetime.now() - timedelta(hours=float(hours)))
        )
        for obj in objs:
            key = obj.__class__.__name__ + '.' + str(obj.id)
            new_dict[key] = obj
        return new_dict

    def new(self, obj):
        """add the object to the current database session"""
        self.__session.add(obj)

    def save(self):
        """commit all changes of the current database session"""
        self.__session.commit()

    def delete(self, obj=None):
        """delete from the current database session obj if not None"""
        if obj is not None:
            self.__session.delete(obj)

    def reload(self):
        """reloads data from the database"""
        Base.metadata.create_all(self.__engine)
        sess_factory = sessionmaker(bind=self.__engine, expire_on_commit=False)
        session = scoped_session(sess_factory)
        self.__session = session

    def close(self):
        """call remove() method on the private session attribute"""
        self.__session.remove()

    @staticmethod
    def get(id_=None):
        """
        Returns the object based on the class name and its ID, or
        None if not found
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
        count = len(models.storage.all().values())
        return count
