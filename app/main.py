from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Dict
import logging
from app.services.scraper import MaterialScraper
from app.database.database import init_db
from app.routes.api import router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(),  # Output to console
        logging.FileHandler('app.log')  # Also save to file
    ]
)

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
    port=8080
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Include API routes
app.include_router(router)

# Templates for HTML interface (kept for backward compatibility if needed)
templates = Jinja2Templates(directory="templates")

# Legacy models for backward compatibility
class URLInput(BaseModel):
    url: str

class DimensionsInput(BaseModel):
    url: str
    dimensions: Dict[str, float] = {
        'dikte': 2,
        'lengte': 1000,
        'breedte': 1000
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
    """
    Analyseert een URL om dimensie velden te vinden (Legacy endpoint)

    - **url**: De URL van de productpagina om te analyseren

    Returns:
        - De gevonden dimensie velden (dikte, lengte, breedte, prijs)
    """
    try:
        scraper = MaterialScraper()
        results = await scraper.analyze_form_fields(input.url)

        return AnalyzeResponse(
            url=input.url,
            dimension_fields=results['dimension_fields']
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
