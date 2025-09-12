from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.database.database import get_db
import app.services.crud as crud, app.schemas.schemas as schemas
from urllib.parse import unquote
from app.schemas.config import ConfigRequest

# Create router instance
router = APIRouter()

@router.get("/api/config/{domain}")
async def get_config(domain: str, db: Session = Depends(get_db)):
    # URL decode the domain
    decoded_domain = unquote(domain)

    config = crud.get_domain_config(db, decoded_domain)
    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return config.config

@router.post("/api/config")
async def save_config(request: ConfigRequest, db: Session = Depends(get_db)):
    try:
        # Save configuration to database
        config = schemas.DomainConfigCreate(domain=request.domain, config=request.config)
        crud.create_domain_config(db, config)
        return JSONResponse({"success": True})
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)

@router.delete("/api/config/{domain}")
async def delete_config(domain: str, db: Session = Depends(get_db)):
    # URL decode the domain
    decoded_domain = unquote(domain)

    if not crud.delete_domain_config(db, decoded_domain):
        raise HTTPException(status_code=404, detail="Configuration not found")
    return {"success": True}

@router.post("/api/config/delete")
async def delete_config_by_body(request: ConfigRequest, db: Session = Depends(get_db)):
    """Delete domain configuration by providing domain in request body instead of URL path"""
    domain = request.domain
    if not crud.delete_domain_config(db, domain):
        raise HTTPException(status_code=404, detail="Configuration not found")
    return {"success": True}
