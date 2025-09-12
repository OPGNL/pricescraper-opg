from fastapi import APIRouter, HTTPException, Depends, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from app.database.database import get_db
from app.core.settings import Settings

# Create router instance
router = APIRouter()

# Get the project root directory (parent of app directory)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

# Templates for rendering HTML pages
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/settings", name="settings")
async def settings_page(request: Request, db: Session = Depends(get_db)):
    """Settings page for configuring application settings"""
    # Get current settings
    api_key = Settings.get_value(db, '2captcha_api_key', '')

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "api_key": api_key
    })

@router.post("/settings", name="save_settings")
async def save_settings(
    request: Request,
    api_key: str = Form(...),
    db: Session = Depends(get_db)
):
    """Save application settings"""
    try:
        Settings.set_value(db, '2captcha_api_key', api_key)
        return {"success": True, "message": "Settings saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
