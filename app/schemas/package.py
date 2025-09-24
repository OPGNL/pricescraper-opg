from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime

class ConfigBase(BaseModel):
    config: Dict[str, Any]

class PackageConfigCreate(ConfigBase):
    package_id: str

class PackageConfigResponse(PackageConfigCreate):
    id: int
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True

class PackageRequest(BaseModel):
    package_id: str
    config: dict
