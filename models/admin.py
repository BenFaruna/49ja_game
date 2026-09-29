from sqlalchemy import Column, Integer, String, Boolean

from models.base import Base, BaseModel


class Admin(BaseModel, Base):
    """ORM model for admin users."""
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    username = Column(String(80), unique=True, nullable=False, index=True)
    email = Column(String(120), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    is_super_admin = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def __str__(self):
        return "[Admin] ({}) username={} super={}".format(
            self.id, self.username, self.is_super_admin
        )
