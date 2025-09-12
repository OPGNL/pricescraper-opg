from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime

class ConfigBase(BaseModel):
    config: Dict[str, Any]

class DomainConfigCreate(ConfigBase):
    domain: str

class DomainConfigResponse(DomainConfigCreate):
    id: int
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True

class ConfigRequest(BaseModel):
    domain: str
    config: dict
