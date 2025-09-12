from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database.database import get_db
import app.services.crud as crud, app.schemas.schemas as schemas
from app.schemas.country import CountryRequest

# Create router instance
router = APIRouter()

@router.get("/api/country/{country}")
async def get_country_config(country: str, db: Session = Depends(get_db)):
    config = crud.get_country_config(db, country)
    if not config:
        raise HTTPException(status_code=404, detail="Country configuration not found")
    return config.config

@router.post("/api/country")
async def save_country_config(request: CountryRequest, db: Session = Depends(get_db)):
    try:
        config = schemas.CountryConfigCreate(country_code=request.country, config=request.config)
        crud.create_country_config(db, config)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.delete("/api/country/{country}")
async def delete_country_config(country: str, db: Session = Depends(get_db)):
    if not crud.delete_country_config(db, country):
        raise HTTPException(status_code=404, detail="Country configuration not found")
    return {"success": True}
