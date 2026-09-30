from models.admin import Admin
from models.base import Base
from models.engine import DBStorage
from models.notification_email import NotificationEmail
from models.switch_tracker import SwitchAlert, SwitchTrackerState

storage = DBStorage()
storage.reload()
