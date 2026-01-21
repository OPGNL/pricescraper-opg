import logging
from pathlib import Path

# Get the project root directory (parent of app directory)
BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Configure logging FIRST, before any other imports that might trigger module-level code
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),  # Output to console
        logging.FileHandler(BASE_DIR / "debug.log"),  # Also save to file in project root
    ],
)

# Now import everything else (after logging is configured)

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.database.database import init_db
from app.routes.config_management import router as config_mgmt_router
from app.routes.country_config import router as country_router
from app.routes.domain_config import router as domain_router
from app.routes.package_config import router as package_router
from app.routes.price_calculation import router as price_router
from app.routes.settings import router as settings_router
from app.routes.version_management import router as version_router
from app.routes.web import router as web_router
from app.services.scraper import MaterialScraper

# Initialize database on startup
init_db()

# Create FastAPI app
app = FastAPI(
    title="Competitor Price Watcher",
    description="API for watching competitor prices",
    version="1.0.0",
    default_response_class=JSONResponse,
    timeout=120,
    host="0.0.0.0",
    port=8080,
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include all routers
app.include_router(web_router)
app.include_router(price_router)
app.include_router(domain_router)
app.include_router(country_router)
app.include_router(package_router)
app.include_router(version_router)
app.include_router(config_mgmt_router)
app.include_router(settings_router)

# Templates for HTML interface (kept for backward compatibility if needed)
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Legacy models for backward compatibility
class URLInput(BaseModel):
    url: str

class DimensionsInput(BaseModel):
    url: str
    dimensions: dict[str, float] = {
        "dikte": 2,
        "lengte": 1000,
        "breedte": 1000,
    }

class AnalyzeResponse(BaseModel):
    url: str
    dimension_fields: dict

class PriceResponse(BaseModel):
    price_excl_btw: float
    price_incl_btw: float

# Optional: Legacy analyze endpoint for backward compatibility
@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_url(input: URLInput):
    """Analyseert een URL om dimensie velden te vinden (Legacy endpoint)

    - **url**: De URL van de productpagina om te analyseren

    Returns:
        - De gevonden dimensie velden (dikte, lengte, breedte, prijs)

    """
    try:
        scraper = MaterialScraper()
        results = await scraper.analyze_form_fields(input.url)

        return AnalyzeResponse(
            url=input.url,
            dimension_fields=results["dimension_fields"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
