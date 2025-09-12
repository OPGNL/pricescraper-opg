from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database.database import get_db
import app.services.crud as crud, app.schemas.schemas as schemas
from app.schemas.package import PackageRequest

# Create router instance
router = APIRouter()

@router.get("/api/packages")
async def get_packages(db: Session = Depends(get_db)):
    """Get all package configurations"""
    packages = {config.package_id: config.config for config in crud.get_package_configs(db)}
    return {"packages": packages}

@router.get("/api/packages/{package_id}")
async def get_package(package_id: str, db: Session = Depends(get_db)):
    """Get a specific package configuration"""
    config = crud.get_package_config(db, package_id)
    if not config:
        raise HTTPException(status_code=404, detail="Package configuration not found")
    return config.config

@router.post("/api/packages")
async def save_package(request: PackageRequest, db: Session = Depends(get_db)):
    """Save or update a package configuration"""
    try:
        config = schemas.PackageConfigCreate(package_id=request.package_id, config=request.config)
        crud.create_package_config(db, config)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.delete("/api/packages/{package_id}")
async def delete_package(package_id: str, db: Session = Depends(get_db)):
    """Delete a package configuration"""
    if not crud.delete_package_config(db, package_id):
        raise HTTPException(status_code=404, detail="Package configuration not found")
    return {"success": True}
