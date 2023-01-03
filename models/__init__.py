from models.base import Base

from models.engine import DBStorage

storage = DBStorage()
storage.reload()
