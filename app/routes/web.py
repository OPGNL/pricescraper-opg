from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
from app.database.database import get_db
import app.services.crud as crud

# Create router instance
router = APIRouter()

# Get the project root directory (parent of app directory)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

# Templates for rendering HTML pages
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(get_db)):
    # Get configurations from database
    countries = {config.country_code: config.config for config in crud.get_country_configs(db)}
    packages = {config.package_id: config.config for config in crud.get_package_configs(db)}

    return templates.TemplateResponse("index.html", {
        "request": request,
        "countries": countries,
        "packages": packages
    })

@router.get("/step-editor")
async def step_editor(request: Request, db: Session = Depends(get_db)):
    # Get configurations from database
    domain_configs = {config.domain: config.config for config in crud.get_domain_configs(db)}
    return templates.TemplateResponse("step_editor.html", {
        "request": request,
        "domain_configs": domain_configs
    })

@router.get("/config")
async def config_page(request: Request, db: Session = Depends(get_db)):
    # Get configurations from database
    domain_configs = {config.domain: config.config for config in crud.get_domain_configs(db)}
    country_configs = {config.country_code: config.config for config in crud.get_country_configs(db)}
    package_configs = {config.package_id: config.config for config in crud.get_package_configs(db)}

    # Group domains by extension
    domains_by_extension = {}
    for domain, config in domain_configs.items():
        # Extract extension (like .nl, .com, .de, etc)
        parts = domain.split('.')
        if len(parts) > 1:
            extension = '.' + parts[-1]
            if extension not in domains_by_extension:
                domains_by_extension[extension] = []
            domains_by_extension[extension].append((domain, config))
        else:
            # For domains without extension
            if 'other' not in domains_by_extension:
                domains_by_extension['other'] = []
            domains_by_extension['other'].append((domain, config))

    return templates.TemplateResponse("config.html", {
        "request": request,
        "domain_configs": domain_configs,
        "domains_by_extension": domains_by_extension,
        "country_configs": country_configs,
        "package_configs": package_configs
    })

@router.get("/docs", response_class=HTMLResponse)
async def docs_page(request: Request):
    return templates.TemplateResponse("docs.html", {"request": request})

@router.get("/config-docs", response_class=HTMLResponse)
async def config_docs(request: Request):
    return templates.TemplateResponse("config_docs.html", {"request": request})
