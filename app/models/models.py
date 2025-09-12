from sqlalchemy import Column, Integer, String, JSON, DateTime, Index
from sqlalchemy.sql import func
from app.database.database import Base
from datetime import datetime

class DomainConfig(Base):
    __tablename__ = "domain_configs"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, unique=True, index=True)
    config = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class CountryConfig(Base):
    __tablename__ = "country_configs"

    id = Column(Integer, primary_key=True, index=True)
    country_code = Column(String, unique=True, index=True)
    config = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class PackageConfig(Base):
    __tablename__ = "package_configs"

    id = Column(Integer, primary_key=True, index=True)
    package_id = Column(String, unique=True, index=True)
    config = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ConfigVersion(Base):
    __tablename__ = "config_versions"

    id = Column(Integer, primary_key=True, index=True)
    config_type = Column(String)  # 'domain', 'country', or 'package'
    config_id = Column(String)    # domain name, country code, or package id
    config = Column(JSON)
    version = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    comment = Column(String, nullable=True)

    __table_args__ = (
        # Composite index voor sneller zoeken van versies
        Index('idx_config_versions_type_id_version', 'config_type', 'config_id', 'version'),
    )

class Settings(Base):
    """Model for storing application settings"""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Setting {self.key}>'

    @staticmethod
    def get_value(key, default=None):
        """Get a setting value by key"""
        setting = Settings.query.filter_by(key=key).first()
        return setting.value if setting else default

    @staticmethod
    def set_value(key, value):
        """Set a setting value"""
        setting = Settings.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = Settings(key=key, value=value)
            db.session.add(setting)
        db.session.commit()
