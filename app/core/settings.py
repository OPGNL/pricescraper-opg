from datetime import datetime

from sqlalchemy import Column, DateTime, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Settings(Base):
    __tablename__ = "settings"

    key = Column(String, primary_key=True)
    value = Column(String)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_value(cls, session, key, default=None):
        """Get a setting value by key"""
        setting = session.query(cls).filter_by(key=key).first()
        return setting.value if setting else default

    @classmethod
    def set_value(cls, session, key, value):
        """Set a setting value"""
        setting = session.query(cls).filter_by(key=key).first()
        if setting:
            setting.value = value
            setting.updated_at = datetime.utcnow()
        else:
            setting = cls(key=key, value=value)
            session.add(setting)
        session.commit()
