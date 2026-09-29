from models.base import Base

from models.engine import DBStorage
from models.switch_tracker import SwitchAlert, SwitchTrackerState  # noqa: F401

storage = DBStorage()
storage.reload()
