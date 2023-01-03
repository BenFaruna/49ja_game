from sqlalchemy import Column, Integer, String

from models.base import Base, BaseModel


class GameData(BaseModel, Base):
    """ORM for game data"""
    __tablename__ = "game_data"

    id = Column(Integer, primary_key=True, nullable=False)
    first = Column(Integer, nullable=False)
    second = Column(Integer, nullable=False)
    third = Column(Integer, nullable=False)
    fourth = Column(Integer, nullable=False)
    fifth = Column(Integer, nullable=False)
    sixth = Column(Integer, nullable=False)
    colour = Column(String(7))
    hi_lo_mid = Column(String(3), nullable=False)
    total = Column(Integer, nullable=False)
    r_count = Column(Integer, nullable=False)
    g_count = Column(Integer, nullable=False)
    b_count = Column(Integer, nullable=False)
    y_count = Column(Integer, nullable=False)

    def __str__(self):
        """String representation of the BaseModel class"""
        return "[{:s}] ({:d}) {}".format(self.__class__.__name__, self.id, self.__dict__)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
