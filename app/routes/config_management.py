from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.services.config_manager import export_configs_to_file, import_configs_from_file
import tempfile
import os

# Create router instance
router = APIRouter()

@router.post("/api/configs/export")
async def export_configs_endpoint(db: Session = Depends(get_db)):
    """
    Export all configurations to a JSON file and return it.
    """
    try:
        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
            export_configs_to_file(db, tmp.name)
            return FileResponse(
                tmp.name,
                media_type='application/json',
                filename='configs_backup.json',
                background=None
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/configs/import")
async def import_configs_endpoint(
    file: UploadFile = File(...),
    clear_existing: bool = False,
    db: Session = Depends(get_db)
):
    """
    Import configurations from a JSON file.
    """
    try:
        # Create a temporary file to store the uploaded content
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp.flush()

            # Import the configurations
            import_configs_from_file(db, tmp.name, clear_existing)

        return {"message": "Configurations imported successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up the temporary file
        if 'tmp' in locals():
            os.unlink(tmp.name)
