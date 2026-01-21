import os

from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base

# Environment settings
ENV = os.getenv("ENV", "development")  # 'development' or 'production'
IS_PRODUCTION = ENV == "production"

# Browser settings
HEADLESS = IS_PRODUCTION  # True in production, False in development

# Database settings
def get_database_url() -> str:
    """Get database URL from environment variables with fallback."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url

    # Fallback logic
    use_postgres_locally = os.getenv("USE_POSTGRES_LOCALLY", "false").lower() == "true"
    if use_postgres_locally:
        return os.getenv("LOCAL_POSTGRES_URL", "postgresql://postgres:password@localhost:5432/competitor_price_watcher")
    return os.getenv("LOCAL_SQLITE_URL", "sqlite:///./competitor_price_watcher.db")

LOCAL_DATABASE_URL = get_database_url()

Base = declarative_base()

class Settings(Base):
    __tablename__ = "settings"

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
