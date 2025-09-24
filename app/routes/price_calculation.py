from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
import json
import asyncio
import logging
from app.services.price_calculator import PriceCalculator
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
from app.database.database import get_db
import app.services.crud as crud
from app.schemas.calculate import SquareMeterPriceRequest, ShippingRequest

# Create router instance
router = APIRouter()

@router.post("/api/calculate-smp")
async def calculate_square_meter_price(request: SquareMeterPriceRequest, db: Session = Depends(get_db)):
    try:
        # Initialize calculator with fresh configs for each request
        calculator = PriceCalculator()
        dimensions = {
            'thickness': request.dikte,
            'length': request.lengte,
            'width': request.breedte,
            'quantity': request.quantity  # Voeg quantity toe aan dimensions
        }

        price_excl_vat, price_incl_vat = await calculator.calculate_price(
            request.url,
            dimensions,
            country=request.country,
            category='square_meter_price'
        )

        country_config = crud.get_country_config(db, request.country)
        if not country_config:
            country_config = crud.get_country_config(db, 'nl')  # Fallback to NL
        country_info = country_config.config

        return {
            "status": "success",
            "status_code": 200,
            "message": "Square meter price calculated successfully",
            "data": {
                "price_excl_vat": round(price_excl_vat, 2),
                "price_incl_vat": round(price_incl_vat, 2),
                "currency": country_info['currency'],
                "currency_symbol": country_info['currency_symbol'],
                "vat_rate": country_info['vat_rate']
            }
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "status_code": 400,
                "message": str(e),
                "error_type": "ValueError"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "status_code": 500,
                "message": str(e),
                "error_type": type(e).__name__
            }
        )

@router.post("/api/calculate-shipping")
async def calculate_shipping(request: ShippingRequest, db: Session = Depends(get_db)):
    """Calculate shipping costs"""
    try:
        # Initialize calculator with fresh configs for each request
        calculator = PriceCalculator()
        package_id = str(request.package_type)
        package_config = crud.get_package_config(db, package_id)
        if not package_config:
            raise ValueError(f"Invalid package type: {request.package_type}. Must be between 1 and 6.")

        package = package_config.config

        # Determine the quantity to use (from request or from package config)
        actual_quantity = request.quantity if request.quantity is not None else package['quantity']

        # Create detailed dimensions object with all parameters from the package config
        dimensions = {
            'package_type': package_id,  # Add package_type to dimensions
            'thickness': request.thickness if request.thickness is not None else package['thickness'],  # Allow thickness override
            'length': package['length'],
            'width': package['width'],
            'quantity': actual_quantity,  # Use the determined quantity
            'name': package['name'],
            'description': package['description'],
            'display': package['display']
        }

        # Log the complete dimensions for debugging
        logging.info(f"Using package dimensions for calculation: {dimensions}")

        price_excl_vat, price_incl_vat = await calculator.calculate_price(
            request.url,
            dimensions,
            country=request.country,
            category='shipping'
        )

        country_config = crud.get_country_config(db, request.country)
        if not country_config:
            country_config = crud.get_country_config(db, 'nl')  # Fallback to NL
        country_info = country_config.config

        return {
            "status": "success",
            "status_code": 200,
            "message": "Shipping costs calculated successfully",
            "data": {
                "price_excl_vat": round(price_excl_vat, 2),
                "price_incl_vat": round(price_incl_vat, 2),
                "currency": country_info['currency'],
                "currency_symbol": country_info['currency_symbol'],
                "vat_rate": country_info['vat_rate'],
                "package_info": {
                    "type": request.package_type,
                    "name": package['name'],
                    "description": package['description'],
                    "quantity": actual_quantity,  # Use the determined quantity
                    "dimensions": f"{package['length']}x{package['width']} mm",
                    "thickness": dimensions['thickness'],  # Use the actual thickness being used
                    "display": package['display']
                }
            }
        }
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "status_code": 400,
                "message": str(e),
                "error_type": "ValueError"
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "status_code": 500,
                "message": str(e),
                "error_type": type(e).__name__
            }
        )

async def price_status_stream(request: Request):
    """SSE endpoint voor real-time status updates"""
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break

            if PriceCalculator.latest_status:
                yield {
                    "event": "status",
                    "data": json.dumps(PriceCalculator.latest_status)
                }
                PriceCalculator.latest_status = None

            await asyncio.sleep(0.1)

    return EventSourceResponse(event_generator())

# Add SSE route to router
router.add_route("/api/status-stream", price_status_stream)
