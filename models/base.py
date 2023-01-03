from datetime import datetime

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, DateTime

import models

Base = declarative_base()
time = "%Y-%m-%dT%H:%M:%S"


class BaseModel:
    """The BaseModel class from which future classes will be derived"""
    date = Column(DateTime, default=datetime.now)

    def __init__(self, **kwargs):
        """Initialization of the base model"""
        if kwargs:
            for key, value in kwargs.items():
                if key != "__class__":
                    setattr(self, key, value)
            if kwargs.get("date", None) and type(self.date) is str:
                self.date = datetime.strptime(kwargs["date"], time)
            else:
                self.date = datetime.now()
        else:
            self.date = datetime.now()

    def __str__(self):
        """String representation of the BaseModel class"""
        return "[{:s}] ({:s}) {}".format(self.__class__.__name__, self.date, self.__dict__)

    def save(self):
        """updates the attribute 'updated_at' with the current datetime"""
        self.date = datetime.now()
        models.storage.new(self)
        models.storage.save()

    def to_dict(self):
        """returns a dictionary containing all keys/values of the instance"""
        new_dict = self.__dict__.copy()
        if "date" in new_dict:
            new_dict["date"] = new_dict["date"].strftime(time)
        new_dict["__class__"] = self.__class__.__name__
        if "_sa_instance_state" in new_dict:
            del new_dict["_sa_instance_state"]
        return new_dict

    def delete(self):
        """delete the current instance from the storage"""
        models.storage.delete(self)
