from playwright.async_api import async_playwright, Page, expect
from typing import Dict, Any, Optional, Tuple, List, Union
import logging
import re
import os
import json
import asyncio
from urllib.parse import urlparse
from datetime import datetime
from app.database.database import SessionLocal
import app.services.crud as crud
from app.core.config import HEADLESS
import random
import string
from twocaptcha import TwoCaptcha
from app.core.config import Settings

# Import separated services
from .calculator.status_manager import StatusManager
from .calculator.browser_manager import BrowserManager
from .calculator.price_extractor import PriceExtractor
from .calculator.step_handlers import StepHandlers
from .calculator.captcha_handler import CaptchaHandler
from .calculator.utils import CalculatorUtils

logging.basicConfig(level=logging.INFO)

class PriceCalculator:
    """Calculate prices based on dimensions for different domains"""

    # Class variable to store latest status
    latest_status = None

    def __init__(self):
        """Initialize the calculator"""
        self.configs = {}  # Initialize configs dictionary
        self._load_configs()  # Load configurations from database
        StatusManager.update_status("Initializing calculator")

    def _normalize_domain(self, url: str) -> str:
        """Normalize domain name by removing www. and getting base domain"""
        parsed = urlparse(url if url.startswith('http') else f'http://{url}')
        domain = parsed.netloc or parsed.path
        return domain.replace('www.', '')

    def _load_configs(self):
        """Load configurations from database"""
        db = SessionLocal()
        try:
            # Load domain configs
            domain_configs = crud.get_domain_configs(db)
            for config in domain_configs:
                self.configs[config.domain] = config.config
        finally:
            db.close()

    def _update_status(self, message: str, step_type: str = None, step_details: dict = None):
        """Update the status of the current operation - delegated to StatusManager"""
        StatusManager.update_status(message, step_type, step_details)
        # Keep class variable for backwards compatibility
        PriceCalculator.latest_status = StatusManager.latest_status

    async def calculate_price(self, url: str, dimensions: Dict[str, float], country: str = 'nl', category: str = 'square_meter_price') -> Tuple[float, float]:
        """Calculate price based on dimensions for a given URL"""
        try:
            # Get domain from URL
            domain = self._normalize_domain(url)

            # Get configuration for domain
            config = self.configs.get(domain)
            if not config:
                self._update_status(f"No configuration found for domain: {domain}", "error")
                raise ValueError(f"No configuration found for domain: {domain}")

            # Get country configuration from database
            db = SessionLocal()
            try:
                country_config = crud.get_country_config(db, country)
                if not country_config:
                    self._update_status(f"No configuration found for country: {country}", "error")
                    raise ValueError(f"No configuration found for country: {country}")
                country_info = country_config.config
            finally:
                db.close()

            # Update status with configuration info
            self._update_status(f"Using configuration for {domain}", "config", {"domain": domain})

            # Log start of calculation
            self._update_status(
                f"Starting price calculation for {domain}",
                "config",
                {
                    "url": url,
                    "dikte": dimensions.get('thickness', ''),
                    "lengte": dimensions.get('length', ''),
                    "breedte": dimensions.get('width', ''),
                    "quantity": dimensions.get('quantity', ''),
                    "country": country,
                    "domain": domain
                }
            )

            if category not in config['categories']:
                raise ValueError(f"Category '{category}' not supported for domain: {domain}")

            # Update debug information with all request parameters
            debug_info = {
                "url": url,
                "dikte": dimensions.get('thickness', 0),
                "lengte": dimensions.get('length', 0),
                "breedte": dimensions.get('width', 0),
                "quantity": dimensions.get('quantity', 1),
                "country": country,
                "domain": domain
            }
            self._update_status(f"Starting price calculation for {domain}", "config", debug_info)

            async with async_playwright() as p:
                # Use BrowserManager for browser setup
                browser_manager = BrowserManager()
                browser, context, page = await browser_manager.setup_browser(p)

                try:
                    # Navigate to URL
                    self._update_status(f"Navigating to {url}", "navigation", {"url": url})
                    await page.goto(url)

                    self._update_status("Waiting for page to be fully loaded", "loading")
                    await page.wait_for_load_state('networkidle')
                    self._update_status("Page loaded successfully", "loaded")

                    # Execute steps using StepHandlers
                    steps = config['categories'][category]['steps']
                    for step in steps:
                        try:
                            # Add random mouse movements before each action
                            if step['type'] in ['click', 'input', 'select']:
                                await BrowserManager.add_human_like_behavior(page)

                            result = await self._process_step(page, step, dimensions)

                            if step['type'] == 'read_price' and result is not None:
                                # Convert price based on VAT
                                vat_rate = country_info.get('vat_rate', 21)
                                include_vat = step.get('include_vat', False)

                                if include_vat:
                                    price_incl = result
                                    price_excl = result / (1 + vat_rate/100)
                                else:
                                    price_excl = result
                                    price_incl = result * (1 + vat_rate/100)

                                self._update_status(
                                    "Price calculation completed",
                                    "complete",
                                    {
                                        "price_excl_vat": price_excl,
                                        "price_incl_vat": price_incl,
                                        "currency_symbol": country_info.get('currency_symbol', '€'),
                                        "currency_format": country_info.get('currency_format', '{amount}'),
                                        "decimal_separator": country_info.get('decimal_separator', ','),
                                        "thousands_separator": country_info.get('thousands_separator', '.'),
                                        "formatted_excl": self._format_price(price_excl, country_info.get('currency_format', '{amount}'), country_info.get('decimal_separator', ','), country_info.get('thousands_separator', '.')),
                                        "formatted_incl": self._format_price(price_incl, country_info.get('currency_format', '{amount}'), country_info.get('decimal_separator', ','), country_info.get('thousands_separator', '.')),
                                        "currency": country_info.get('currency', 'EUR')
                                    }
                                )

                                return price_excl, price_incl
                        except Exception as step_error:
                            if step.get('continue_on_error', False):
                                self._update_status(
                                    f"Step failed but continuing: {str(step_error)}",
                                    'warn',
                                    {**step, 'error': str(step_error), 'continuing': True}
                                )
                                if step['type'] == 'read_price':
                                    # If it's a read_price step that failed, return 0.00 prices
                                    self._update_status(
                                        "Returning 0.00 for failed price reading step",
                                        "complete",
                                        {
                                            "price_excl_vat": 0.00,
                                            "price_incl_vat": 0.00
                                        }
                                    )
                                    return 0.00, 0.00
                                continue
                            else:
                                raise step_error

                except Exception as e:
                    self._update_status(f"Error: {str(e)}", "error")
                    raise
                finally:
                    await browser.close()

        except Exception as e:
            self._update_status(f"Error calculating price: {str(e)}", "error")
            raise

    async def _process_step(self, page, step, dimensions=None):
        """Process a single step in the configuration - delegated to StepHandlers"""
        step_type = step['type']

        try:
            # Format step parameters with dimension context if needed
            formatted_step = CalculatorUtils.format_step_parameters(step, dimensions or {})

            # Validate step configuration
            if not CalculatorUtils.validate_step_config(formatted_step):
                raise ValueError(f"Invalid step configuration: {step}")

            if step_type == 'read_price':
                # Handle price reading with PriceExtractor
                price = await self._handle_read_price(page, formatted_step, dimensions)
                return price
            else:
                # Use StepHandlers for all other step types
                return await StepHandlers.execute_step(page, formatted_step)

        except Exception as e:
            if step.get('continue_on_error', False):
                self._update_status(f"Step failed: {str(e)}, continuing...", "warn")
                return
            self._update_status(f"Step failed: {str(e)}", "error")
            raise

    async def _handle_read_price(self, page, step, dimensions=None):
        """Handle a read_price step - delegated to PriceExtractor"""
        try:
            return await PriceExtractor.extract_price(page, step, dimensions)
        except Exception as e:
            if step.get('continue_on_error', False):
                self._update_status(
                    f"Could not read price, returning 0.00: {str(e)}",
                    'warn',
                    {**step, 'error': str(e), 'price': 0.00}
                )
                return 0.00
            raise

    def _format_price(self, amount: float, currency_format: str, decimal_separator: str = ',', thousands_separator: str = '.') -> str:
        """Format a price according to the specified format and separators"""
        try:
            # Split number into integer and decimal parts
            str_amount = f"{amount:.2f}"
            int_part, dec_part = str_amount.split('.')

            # Add thousands separator
            if len(int_part) > 3:
                int_part = format(int(int_part), ',').replace(',', thousands_separator)

            # Combine with decimal separator
            formatted_number = f"{int_part}{decimal_separator}{dec_part}"

            # Replace {amount} in the format string with the formatted number
            return currency_format.replace('{amount}', formatted_number)
        except Exception as e:
            logging.error(f"Error formatting price: {str(e)}")
            # Fallback to simple formatting
            return f"{amount:.2f}".replace('.', decimal_separator)

    @classmethod
    def get_latest_status(cls):
        """Get the latest status of price calculation"""
        return cls.latest_status
