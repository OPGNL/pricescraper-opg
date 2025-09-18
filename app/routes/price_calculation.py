from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
import json
import asyncio
import logging
import uuid
from app.services.price_calculator import PriceCalculator, _status_store
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
        # Generate unique request ID for status tracking
        request_id = str(uuid.uuid4())

        # Initialize calculator with request ID for status tracking
        calculator = PriceCalculator(request_id)
        dimensions = {
            'thickness': request.dikte,
            'length': request.lengte,
            'width': request.breedte,
            'quantity': request.quantity  # Voeg quantity toe aan dimensions
        }

        # Set initial status in the store
        _status_store[request_id] = {
            "message": "Calculation queued",
            "step_type": "queued",
            "step_details": None,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }

        # Run calculation in background
        async def background_calculation():
            try:
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

                # Set final result in status store
                _status_store[request_id] = {
                    "message": "Calculation completed",
                    "step_type": "complete",
                    "step_details": {
                        "price_excl_vat": round(price_excl_vat, 2),
                        "price_incl_vat": round(price_incl_vat, 2),
                        "currency": country_info['currency'],
                        "currency_symbol": country_info['currency_symbol'],
                        "vat_rate": country_info['vat_rate'],
                        "formatted_excl": f"{round(price_excl_vat, 2):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        "formatted_incl": f"{round(price_incl_vat, 2):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    },
                    "timestamp": __import__('datetime').datetime.now().isoformat()
                }
            except Exception as e:
                logging.error(f"Background calculation error for {request_id}: {str(e)}")
                _status_store[request_id] = {
                    "message": f"Calculation failed: {str(e)}",
                    "step_type": "error",
                    "step_details": {"error_type": type(e).__name__},
                    "timestamp": __import__('datetime').datetime.now().isoformat()
                }

        # Start background task
        asyncio.create_task(background_calculation())

        # Return immediately with request_id
        return {
            "status": "accepted",
            "status_code": 202,
            "message": "Calculation started, check status stream for updates",
            "request_id": request_id
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
        # Generate unique request ID for status tracking
        request_id = str(uuid.uuid4())

        # Initialize calculator with request ID for status tracking
        calculator = PriceCalculator(request_id)
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

        # Set initial status in the store
        _status_store[request_id] = {
            "message": "Shipping calculation queued",
            "step_type": "queued",
            "step_details": None,
            "timestamp": __import__('datetime').datetime.now().isoformat()
        }

        # Run calculation in background
        async def background_shipping_calculation():
            try:
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

                # Set final result in status store
                _status_store[request_id] = {
                    "message": "Shipping calculation completed",
                    "step_type": "complete",
                    "step_details": {
                        "price_excl_vat": round(price_excl_vat, 2),
                        "price_incl_vat": round(price_incl_vat, 2),
                        "currency": country_info['currency'],
                        "currency_symbol": country_info['currency_symbol'],
                        "vat_rate": country_info['vat_rate'],
                        "formatted_excl": f"{round(price_excl_vat, 2):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        "formatted_incl": f"{round(price_incl_vat, 2):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                        "package_info": {
                            "type": request.package_type,
                            "name": package['name'],
                            "description": package['description'],
                            "quantity": actual_quantity,  # Use the determined quantity
                            "dimensions": f"{package['length']}x{package['width']} mm",
                            "thickness": dimensions['thickness'],  # Use the actual thickness being used
                            "display": package['display']
                        }
                    },
                    "timestamp": __import__('datetime').datetime.now().isoformat()
                }
            except Exception as e:
                logging.error(f"Background shipping calculation error for {request_id}: {str(e)}")
                _status_store[request_id] = {
                    "message": f"Shipping calculation failed: {str(e)}",
                    "step_type": "error",
                    "step_details": {"error_type": type(e).__name__},
                    "timestamp": __import__('datetime').datetime.now().isoformat()
                }

        # Start background task
        asyncio.create_task(background_shipping_calculation())

        # Return immediately with request_id
        return {
            "status": "accepted",
            "status_code": 202,
            "message": "Shipping calculation started, check status stream for updates",
            "request_id": request_id
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

async def price_status_stream(request: Request, request_id: str):
    """SSE endpoint voor real-time status updates for a specific request"""
    async def event_generator():
        last_status = None
        logging.info(f"SSE generator started for {request_id}, status store has {len(_status_store)} items")
        while True:
            if await request.is_disconnected():
                logging.info(f"SSE client disconnected for {request_id}")
                break

            current_status = _status_store.get(request_id)
            if current_status and current_status != last_status:
                logging.info(f"Sending status update for {request_id}: {current_status['message']}")
                yield {
                    "event": "status",
                    "data": json.dumps(current_status)
                }
                last_status = current_status

            await asyncio.sleep(0.1)

    return EventSourceResponse(event_generator())

# Add SSE route to router using FastAPI decorator
@router.get("/api/status-stream/{request_id}")
async def get_price_status_stream(request: Request, request_id: str):
    """SSE endpoint voor real-time status updates for a specific request"""
    logging.info(f"SSE connection started for request_id: {request_id}")
    return await price_status_stream(request, request_id)
