from pydantic import BaseModel
from typing import Dict, Any
from datetime import datetime

class ConfigBase(BaseModel):
    config: Dict[str, Any]

class CountryConfigCreate(ConfigBase):
    country_code: str

class CountryConfigResponse(CountryConfigCreate):
    id: int
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True

class CountryRequest(BaseModel):
    country: str
    config: dict
