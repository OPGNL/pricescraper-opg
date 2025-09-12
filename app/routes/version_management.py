from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime
from sqlalchemy.orm import Session
from app.database.database import get_db
import app.services.crud as crud
from urllib.parse import unquote
from app.schemas.version import VersionResponse

# Create router instance
router = APIRouter()

@router.get("/api/config/{domain}/versions")
async def get_domain_versions(domain: str, db: Session = Depends(get_db)):
    """Haal alle versies op van een domein configuratie"""
    # URL decode the domain
    decoded_domain = unquote(domain)

    versions = crud.get_config_versions(db, 'domain', decoded_domain)
    if not versions:
        raise HTTPException(status_code=404, detail="No versions found")
    return [VersionResponse(
        version=v.version,
        created_at=v.created_at,
        comment=v.comment,
        config=v.config
    ) for v in versions]

@router.post("/api/config/{domain}/restore/{version}")
async def restore_domain_version(domain: str, version: int, db: Session = Depends(get_db)):
    """Herstel een specifieke versie van een domein configuratie"""
    # URL decode the domain
    decoded_domain = unquote(domain)

    config = crud.restore_config_version(db, 'domain', decoded_domain, version)
    if not config:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"success": True}

@router.get("/api/country/{country}/versions")
async def get_country_versions(country: str, db: Session = Depends(get_db)):
    """Haal alle versies op van een land configuratie"""
    versions = crud.get_config_versions(db, 'country', country)
    if not versions:
        raise HTTPException(status_code=404, detail="No versions found")
    return [VersionResponse(
        version=v.version,
        created_at=v.created_at,
        comment=v.comment,
        config=v.config
    ) for v in versions]

@router.post("/api/country/{country}/restore/{version}")
async def restore_country_version(country: str, version: int, db: Session = Depends(get_db)):
    """Herstel een specifieke versie van een land configuratie"""
    config = crud.restore_config_version(db, 'country', country, version)
    if not config:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"success": True}

@router.get("/api/packages/{package_id}/versions")
async def get_package_versions(package_id: str, db: Session = Depends(get_db)):
    """Haal alle versies op van een pakket configuratie"""
    versions = crud.get_config_versions(db, 'package', package_id)
    if not versions:
        raise HTTPException(status_code=404, detail="No versions found")
    return [VersionResponse(
        version=v.version,
        created_at=v.created_at,
        comment=v.comment,
        config=v.config
    ) for v in versions]

@router.post("/api/packages/{package_id}/restore/{version}")
async def restore_package_version(package_id: str, version: int, db: Session = Depends(get_db)):
    """Herstel een specifieke versie van een pakket configuratie"""
    config = crud.restore_config_version(db, 'package', package_id, version)
    if not config:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"success": True}
