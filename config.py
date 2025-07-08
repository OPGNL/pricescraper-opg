import os
from sqlalchemy import Column, String, create_engine
from sqlalchemy.ext.declarative import declarative_base

# Environment settings
ENV = os.getenv('ENV', 'development')  # 'development' or 'production'
IS_PRODUCTION = ENV == 'production'

# Browser settings
HEADLESS = IS_PRODUCTION  # True in production, False in development
# HEADLESS = True

# Database settings
USE_POSTGRES_LOCALLY = os.getenv('USE_POSTGRES_LOCALLY', 'true').lower() == 'true'
LOCAL_DATABASE_URL = "postgresql://localhost/competitor_price_watcher" if USE_POSTGRES_LOCALLY else "sqlite:///./competitor_price_watcher.db" 

Base = declarative_base()

class Settings(Base):
    __tablename__ = 'settings'

    key = Column(String, primary_key=True)
    value = Column(String)

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
        else:
            setting = cls(key=key, value=value)
            session.add(setting)
        session.commit() 