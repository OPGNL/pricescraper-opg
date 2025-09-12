from pydantic import BaseModel
from datetime import datetime

class VersionResponse(BaseModel):
    version: int
    created_at: datetime
    comment: str | None
    config: dict
