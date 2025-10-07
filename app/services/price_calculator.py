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

# Global status store for per-request status tracking
_status_store = {}

class PriceCalculator:

    def __init__(self, request_id: str = None):
        """Initialize the calculator"""
        self.request_id = request_id
        # Number of seconds to keep status available after calculation completes.
        # Helps clients connect to SSE after receiving request_id and still see logs.
        self.preserve_status_ttl = 30
        self.configs = {}  # Initialize configs dictionary
        self._load_configs()  # Load configurations from database
        self._update_status("Initializing calculator")

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
        """Update the status of the current operation with detailed logging"""
        if not self.request_id:
            return  # Skip status updates if no request ID

        # Create the status object
        status_update = {
            "message": message,
            "step_type": step_type,
            "step_details": step_details,
            "timestamp": datetime.now().isoformat()
        }

        # Store status update for this request
        _status_store[self.request_id] = status_update

        # Create a detailed log message
        log_parts = []

        # Add step type if available
        if step_type:
            log_parts.append(f"[{step_type.upper()}]")

        # Add the main message
        log_parts.append(message)

        # Add details if available
        if step_details:
            # Special handling for sensitive data
            safe_details = step_details.copy()
            if 'value' in safe_details and step_type == 'input' and safe_details.get('selector', '').lower().find('password') != -1:
                safe_details['value'] = '[HIDDEN]'

            # Format details nicely
            detail_parts = []
            for key, value in safe_details.items():
                if key == 'selector':
                    detail_parts.append(f"selector='{value}'")
                elif key == 'status':
                    detail_parts.append(f"status='{value}'")
                elif key == 'value':
                    detail_parts.append(f"value='{value}'")
                elif key == 'unit':
                    detail_parts.append(f"unit='{value}'")
                elif key == 'price':
                    detail_parts.append(f"price={value:.2f}")
                elif key == 'calculation':
                    detail_parts.append(f"calculation='{value}'")
                else:
                    detail_parts.append(f"{key}='{value}'")

            if detail_parts:
                log_parts.append("(" + ", ".join(detail_parts) + ")")

        # Combine all parts into final log message
        log_message = " ".join(log_parts)

        # Log with appropriate level
        if "error" in message.lower():
            logging.error(log_message)
        elif "warn" in message.lower() or "could not" in message.lower():
            logging.warning(log_message)
        else:
            logging.info(log_message)

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
                # Get browser config from domain config
                disable_canvas_webgl = config.get('disable_canvas_webgl', False)  # Default to False for anti-detection

                # Build args conditionally
                args = [
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-application-cache',
                    '--disable-cache',
                    '--disable-offline-load-stale-cache',
                    '--disk-cache-size=0',
                    f'--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                ]
                if disable_canvas_webgl:
                    args.extend([
                        '--disable-accelerated-2d-canvas',
                        '--disable-webgl',
                        '--disable-gpu',
                        '--disable-software-rasterizer',
                    ])

                # Launch browser with conditional args
                browser = await p.chromium.launch(
                    headless=HEADLESS,
                    args=args
                )

                # Create context with more realistic browser settings and disabled storage
                context = await browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                    locale='nl-NL',
                    timezone_id='Europe/Amsterdam',
                    geolocation={'latitude': 52.3676, 'longitude': 4.9041},  # Amsterdam coordinates
                    permissions=['geolocation'],
                    color_scheme='light',
                    has_touch=True,
                    is_mobile=False,
                    device_scale_factor=2,
                    java_script_enabled=True,
                    storage_state={'cookies': [], 'origins': []},  # Start with empty storage
                    ignore_https_errors=True,
                    bypass_csp=True,
                )

                # Add common browser fingerprints and storage cleanup
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['nl-NL', 'nl', 'en-US', 'en']
                    });
                    Object.defineProperty(screen, 'colorDepth', {
                        get: () => 24
                    });

                    // Clear all storage on page load
                    window.addEventListener('load', () => {
                        localStorage.clear();
                        sessionStorage.clear();
                        indexedDB.deleteDatabase('_all_');
                    });
                """)

                # Create page from context and set timeout
                page = await context.new_page()
                page.set_default_timeout(120000)  # 1:30 minute timeout

                try:
                    # Navigate to URL with increased timeout
                    self._update_status(f"Navigating to {url}", "navigation", {"url": url})
                    await page.goto(url)

                    # Execute steps
                    steps = config['categories'][category]['steps']

                    # Wait for page to be ready using multiple strategies
                    self._update_status("Waiting for page to load completely", "loading")

                    try:
                        # Strategy 1: Wait for network idle (most reliable for dynamic content)
                        await page.wait_for_load_state('networkidle', timeout=15000)
                        self._update_status("Page loaded successfully (networkidle)", "loaded")
                    except:
                        try:
                            # Strategy 2: Wait for DOM content to be loaded
                            await page.wait_for_load_state('domcontentloaded', timeout=10000)
                            # Give a bit more time for any remaining dynamic content
                            await asyncio.sleep(2)
                            self._update_status("Page loaded successfully (domcontentloaded)", "loaded")
                        except:
                            # Strategy 3: Fallback - just wait a reasonable amount of time
                            await asyncio.sleep(3)
                            self._update_status("Page load timeout, proceeding anyway", "loaded")

                    current_category = category  # Track current category for config switching
                    step_index = 0

                    while step_index < len(steps):
                        step = steps[step_index]
                        try:
                            # Add random mouse movements before each action
                            if step['type'] in ['click', 'input', 'select']:
                                await page.mouse.move(
                                    random.randint(0, 1920),
                                    random.randint(0, 1080),
                                    steps=random.randint(5, 10)
                                )

                            result = await self._process_step(page, step, dimensions)

                            # Handle decide_config step result
                            if step['type'] == 'decide_config' and result is not None:
                                if result.get('switch_config', False):
                                    new_config = result.get('new_config')
                                    if new_config and new_config in config['categories']:
                                        self._update_status(
                                            f"Switching from '{current_category}' to '{new_config}' configuration",
                                            "config_switch",
                                            {
                                                "from_config": current_category,
                                                "to_config": new_config,
                                                "reason": "decide_config_triggered"
                                            }
                                        )
                                        # Switch to new configuration
                                        current_category = new_config
                                        steps = config['categories'][current_category]['steps']
                                        # Continue from the next step in the new configuration
                                        step_index = 0
                                        continue
                                    else:
                                        self._update_status(
                                            f"Fallback configuration '{new_config}' not found, continuing with current",
                                            "warn"
                                        )
                                # If not switching, just continue with next step
                                step_index += 1
                                continue

                            if step['type'] == 'read_price' and result is not None:
                                # Convert price based on VAT
                                vat_rate = country_info['vat_rate']
                                if step.get('includes_vat', False):
                                    price_excl = result / (1 + vat_rate/100)
                                    price_incl = result
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
                                step_index += 1
                                continue
                            else:
                                raise step_error

                        step_index += 1

                except Exception as e:
                    self._update_status(f"Error: {str(e)}", "error")
                    raise
                finally:
                    await browser.close()

        except Exception as e:
            self._update_status(f"Error calculating price: {str(e)}", "error")
            raise
        finally:
            # Clean up status when calculation is complete
            self._cleanup_status()

    def _cleanup_status(self):
        """Clean up status updates for this request"""
        if not self.request_id:
            return

        if self.request_id not in _status_store:
            return

        # If TTL is set, schedule delayed cleanup so clients have time to connect
        if getattr(self, 'preserve_status_ttl', 0) and self.preserve_status_ttl > 0:
            # Schedule deletion after TTL seconds
            try:
                asyncio.create_task(self._delayed_cleanup(self.request_id, self.preserve_status_ttl))
            except RuntimeError:
                # Event loop might be closed or unavailable; fall back to immediate delete
                _status_store.pop(self.request_id, None)
        else:
            _status_store.pop(self.request_id, None)

    async def _delayed_cleanup(self, request_id: str, ttl: int):
        await asyncio.sleep(ttl)
        _status_store.pop(request_id, None)

    def _convert_value(self, value: float, unit: str) -> float:
        """Convert a value from millimeters to the target unit"""
        # Convert value to float if it's an integer
        value = float(value)

        if unit == 'cm':
            converted = value / 10
            # Round to 1 decimal place if not a whole number
            if not converted.is_integer():
                converted = round(converted, 1)
            return converted
        return value  # Default is mm

    async def _highlight_element(self, page, elements_or_element):
        """Add a highlight effect to one or more elements"""
        # Convert single element to list for consistent handling
        elements = elements_or_element if isinstance(elements_or_element, list) else [elements_or_element]

        for element in elements:
            try:
                await element.evaluate("""
                    (el) => {
                        // Store original outline
                        const originalOutline = el.style.outline;
                        const originalOutlineOffset = el.style.outlineOffset;

                        // Add highlight
                        el.style.outline = '3px solid #2563eb';
                        el.style.outlineOffset = '2px';

                        // Remove highlight after 2 seconds and restore original outline
                        setTimeout(() => {
                            el.style.outline = originalOutline;
                            el.style.outlineOffset = originalOutlineOffset;
                        }, 2000);
                    }
                """)
            except Exception as e:
                self._update_status(f"Could not highlight element: {str(e)}", "warn")
                continue

    def _substitute_dynamic_selector(self, selector: str, dimensions: dict, step: dict, operation_type: str = "operation") -> str:
        """
        Handle dynamic selector substitution with dimension variables.

        Args:
            selector: The selector string that may contain variables like {thickness}
            dimensions: Dictionary containing dimension values
            step: The step configuration containing unit information
            operation_type: Type of operation for logging (e.g., "click", "select")

        Returns:
            Modified selector with variables substituted
        """
        if not dimensions or '{' not in selector or '}' not in selector:
            return selector

        original_selector = selector
        for key in ['thickness', 'width', 'length', 'quantity']:
            if f"{{{key}}}" in selector:
                if key in dimensions:
                    # Convert value and substitute
                    value = dimensions[key]
                    unit = step.get('unit', 'mm')
                    converted_value = self._convert_value(value, unit)

                    # Convert to integer if it's a whole number
                    if isinstance(converted_value, float) and converted_value.is_integer():
                        converted_value = int(converted_value)

                    selector = selector.replace(f"{{{key}}}", str(converted_value))
                    self._update_status(
                        f"Dynamic selector: replaced {{{key}}} with {converted_value}",
                        operation_type,
                        {"original_selector": original_selector, "final_selector": selector}
                    )
                else:
                    self._update_status(f"Dimension {key} not found for dynamic selector", "error")
                    raise ValueError(f"Dimension {key} not found in dimensions dict")

        return selector

    async def _handle_select(self, page, step, dimensions):
        """Handle a select/input step"""
        # Controleer eerst of 'value' aanwezig is in de step dictionary
        if 'value' not in step:
            # Als use_index is ingesteld en option_index is beschikbaar, gebruik index gebaseerde selectie
            if 'use_index' in step and step['use_index'] and 'option_index' in step:
                # Voeg automatisch een value toe in het juiste format
                step['value'] = f"index:{step['option_index']}"
                self._update_status(f"Added value 'index:{step['option_index']}' based on option_index", "select")
            # Als er geen selector is, probeer opties te raden op basis van andere velden
            elif 'selector' in step:
                # Log dit als een waarschuwing en gebruik een default waarde
                self._update_status(f"No value specified for select step, using empty value", "warn")
                step['value'] = ""  # Lege string als fallback
            else:
                # Als er geen selector is, kunnen we niet verder
                self._update_status("Missing required fields for select step", "error")
                raise ValueError("Missing required fields in select step: need 'value' or 'use_index' + 'option_index'")

        # Controleer of de selector aanwezig is
        if 'selector' not in step:
            if 'select_element' in step:
                # Als select_element aanwezig is, gebruik dat als selector (compatibiliteit met index selectie)
                step['selector'] = step['select_element']
                self._update_status(f"Using select_element as selector", "select")
            else:
                # Als er geen selector is, kunnen we niet verder
                self._update_status("No selector specified for select step", "error")
                raise ValueError("Missing required field 'selector' in select step")

        value = step['value']
        selector = step['selector']

        # Support dynamic selector creation with variable substitution
        selector = self._substitute_dynamic_selector(selector, dimensions, step, "select")

        # Handle index-based selection
        if isinstance(value, str) and value.startswith('index:'):
            try:
                index = int(value.split(':')[1])
                element = await page.wait_for_selector(selector)
                if not element:
                    raise ValueError(f"No element found matching selector: {selector}")

                tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
                if tag_name == 'select':
                    await element.select_option(index=index)
                    await asyncio.sleep(0.5)
                    return
                else:
                    # For non-standard dropdowns
                    await element.click()
                    await asyncio.sleep(0.5)
                    options = await page.query_selector_all('li, .option, .dropdown-item, [role="option"]')
                    if index < len(options):
                        await options[index].click()
                        await asyncio.sleep(0.5)
                        return
                    else:
                        raise ValueError(f"Index {index} out of range for options list")

            except Exception as e:
                self._update_status(f"Error with index-based selection: {str(e)}", "error")
                raise ValueError(f"Failed to select option by index: {str(e)}")

        # Value is een lege string, probeer de eerste optie te selecteren
        if value == "":
            try:
                element = await page.wait_for_selector(selector)
                if not element:
                    self._update_status(f"Element not found: {selector}", "error")
                    return  # Ga verder zonder error

                tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
                if tag_name == 'select':
                    # Voor select elementen, selecteer de eerste optie
                    await element.select_option(index=0)
                    self._update_status(f"Selected first option for empty value", "select")
                    await asyncio.sleep(0.5)
                    return
                else:
                    # Voor non-standard dropdowns, klik erop en selecteer de eerste optie
                    await element.click()
                    await asyncio.sleep(0.5)
                    options = await page.query_selector_all('li, .option, .dropdown-item, [role="option"]')
                    if options and len(options) > 0:
                        await options[0].click()
                        self._update_status(f"Selected first dropdown option for empty value", "select")
                        await asyncio.sleep(0.5)
                        return
            except Exception as e:
                self._update_status(f"Error selecting first option: {str(e)}", "warn")
                # Ga verder met reguliere selectie

        # Handle regular value-based selection
        for key in ['thickness', 'width', 'length', 'quantity']:
            if f"{{{key}}}" in value:
                if key in dimensions:
                    converted_value = self._convert_value(dimensions[key], step.get('unit', 'mm'))
                    # Convert to integer if it's a whole number
                    if isinstance(converted_value, float) and converted_value.is_integer():
                        converted_value = int(converted_value)
                    value = value.replace(f"{{{key}}}", str(converted_value))
                    unit_display = step.get('unit', 'mm')
                    self._update_status(
                        f"Setting {key} to {converted_value} {unit_display}",
                        "select",
                        {
                            "selector": selector,
                            "value": str(converted_value),
                            "unit": unit_display
                        }
                    )
                else:
                    self._update_status(f"Dimension {key} not found", "error")
                    raise ValueError(f"Dimension {key} not found in dimensions dict")

        logging.info(f"Handling select/input: {selector} with target value {value}")
        self._update_status(f"Handling select/input with value {value}", "select", {"selector": selector, "value": value})

        try:
            target_value = float(value)
        except ValueError:
            # If we can't convert to float, treat it as a string-based selection
            self._update_status(f"Using string-based selection with value: {value}", "select")

            element = await page.wait_for_selector(selector)
            if not element:
                raise ValueError(f"No element found matching selector: {selector}")

            tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
            if tag_name == 'select':
                # For select elements, try to find option with matching text
                await element.select_option(label=value)
                await asyncio.sleep(0.5)
                return
            else:
                # For non-standard dropdowns, try to find an option containing the text
                await element.click()  # Click to open dropdown
                await asyncio.sleep(0.5)

                # Try to find options with matching text
                options = await page.query_selector_all('li, .option, .dropdown-item, [role="option"]')
                for option in options:
                    option_text = await option.text_content()
                    if value.lower() in option_text.lower():
                        await option.click()
                        await asyncio.sleep(0.5)
                        return

                raise ValueError(f"No option found with text containing '{value}'")

        # First check if we need to open a dropdown/container
        if 'container_trigger' in step:
            trigger = await page.wait_for_selector(step['container_trigger'])
            if trigger:
                await trigger.click()
                await asyncio.sleep(0.5)

        # Find all matching elements
        elements = await page.query_selector_all(selector)
        if not elements:
            raise ValueError(f"No elements found matching selector: {selector}")

        best_match = None
        smallest_diff = float('inf')

        # Try each element
        for element in elements:
            try:
                # Get element type
                tag_name = await element.evaluate('el => el.tagName.toLowerCase()')
                element_type = await element.get_attribute('type') if tag_name == 'input' else None

                # Get the value and any associated text
                value_attr = await element.get_attribute('value')
                element_text = ''

                if tag_name == 'select':
                    # For select elements, get all options
                    options = await element.evaluate('''(select) => {
                        return Array.from(select.options).map(option => ({
                            value: option.value,
                            text: option.text.trim()
                        }));
                    }''')

                    for option in options:
                        try:
                            # Zoek naar een getal met optionele eenheid (bijv. "2mm" of "2 mm")
                            numeric_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:mm|cm)?', option['text'])
                            if numeric_match:
                                option_value = float(numeric_match.group(1))
                                # Voeg een extra check toe om te voorkomen dat 2 matcht met 20
                                if abs(option_value - target_value) < 0.01 and len(str(int(option_value))) == len(str(int(target_value))):
                                    smallest_diff = 0
                                    best_match = {
                                        'element': element,
                                        'type': 'select',
                                        'value': option['value'],
                                        'option_value': option_value
                                    }
                                    break  # Stop zoeken als we een exacte match hebben gevonden
                        except Exception as e:
                            logging.error(f"Error processing select option: {str(e)}")

                elif element_type in ['radio', 'checkbox']:
                    try:
                        # Get numeric value from the value attribute
                        numeric_match = re.search(r'(\d+(?:\.\d+)?)', value_attr)
                        if numeric_match:
                            option_value = float(numeric_match.group(1))
                            # Voeg dezelfde extra check toe voor radio/checkbox elementen
                            if abs(option_value - target_value) < 0.01 and len(str(int(option_value))) == len(str(int(target_value))):
                                smallest_diff = 0
                                best_match = {
                                    'element': element,
                                    'type': 'input',
                                    'option_value': option_value
                                }
                                break  # Stop zoeken als we een exacte match hebben gevonden
                    except Exception as e:
                        logging.error(f"Error processing radio/checkbox: {str(e)}")

                else:
                    # For other elements, try to find numeric value in text content
                    element_text = await element.text_content()
                    numeric_match = re.search(r'(\d+(?:\.\d+)?)', element_text)
                    if numeric_match:
                        option_value = float(numeric_match.group(1))
                        # Voeg dezelfde extra check toe voor andere elementen
                        if abs(option_value - target_value) < 0.01 and len(str(int(option_value))) == len(str(int(target_value))):
                            smallest_diff = 0
                            best_match = {
                                'element': element,
                                'type': 'other',
                                'option_value': option_value
                            }
                            break  # Stop zoeken als we een exacte match hebben gevonden

            except Exception as e:
                logging.error(f"Error processing element: {str(e)}")
                continue

        # Select the best matching option
        if best_match and smallest_diff < 0.01:  # Strict matching threshold
            logging.info(f"Found best match with value {best_match.get('option_value')} (diff: {smallest_diff})")

            # Ensure element is in view and clickable
            await best_match['element'].scroll_into_view_if_needed()
            await asyncio.sleep(0.5)  # Wait for scroll to complete

            if best_match['type'] == 'select':
                # For select elements, first click to open dropdown
                await best_match['element'].click()
                await asyncio.sleep(0.2)
                # Then select the option
                await best_match['element'].select_option(value=best_match['value'])
                # Finally click again to close dropdown
                await best_match['element'].click()
            else:
                # For radio/checkbox/other, simulate a real click
                # First ensure we're clicking the center of the element
                box = await best_match['element'].bounding_box()
                if box:
                    x = box['x'] + box['width'] / 2
                    y = box['y'] + box['height'] / 2
                    await page.mouse.click(x, y)
                else:
                    # Fallback to element click if we can't get bounding box
                    await best_match['element'].click()

            # Dispatch change event
            await best_match['element'].evaluate('(el) => el.dispatchEvent(new Event("change", { bubbles: true }))')
            await asyncio.sleep(1)
            return
        else:
            raise ValueError(f"Could not find matching option for value {value}mm (closest diff was {smallest_diff})")

    async def _handle_input(self, page, step, dimensions):
        # Check eerst of 'selector' aanwezig is
        if 'selector' not in step:
            self._update_status(f"Missing selector in input step", "error")
            raise ValueError("No selector specified for input step")

        selector = step['selector']
        max_retries = 3
        clear_first = step.get('clear_first', True)  # Default to clearing the field first
        unit = step.get('unit', 'mm')  # Get the unit from the step, default to mm

        # Bepaal de uiteindelijke waarde die ingevuld moet worden
        final_value_str = ""
        field_type = None

        # Prioriteit 1: Gebruik waarde uit dimensions als het een dimensieveld is
        if dimensions:
            # Check of de selector overeenkomt met een bekend dimensietype
            if 'length' in selector.lower() or 'lengte' in selector.lower() or selector.endswith('_length'):
                field_type = 'length'
                if 'length' in dimensions:
                    value = dimensions['length']
            elif 'width' in selector.lower() or 'breedte' in selector.lower() or selector.endswith('_width'):
                field_type = 'width'
                if 'width' in dimensions:
                    value = dimensions['width']
            elif 'thickness' in selector.lower() or 'dikte' in selector.lower() or selector.endswith('_thickness'):
                field_type = 'thickness'
                if 'thickness' in dimensions:
                    value = dimensions['thickness']
            elif 'qty' in selector.lower() or 'quantity' in selector.lower() or selector == '.qty':
                field_type = 'quantity'
                if 'quantity' in dimensions:
                    value = dimensions['quantity']

            # Als een dimensieveld is herkend en een waarde gevonden in dimensions:
            if field_type and 'value' in locals():
                # Converteer naar de juiste eenheid (cm of mm)
                if unit == 'cm':
                    value = value / 10
                    if value.is_integer():
                        value = int(value)
                    else:
                        value = round(value, 1)
                elif isinstance(value, float) and value.is_integer():
                    value = int(value)
                elif isinstance(value, float):
                     # Round to 1 decimal place for mm if needed (should usually be int)
                    value = round(value, 1)

                final_value_str = str(value)
                logging.info(f"Using {field_type} from dimensions: {final_value_str} {unit}")
                self._update_status(f"Using {field_type} from dimensions: {final_value_str} {unit}", "input", {"selector": selector})

        # Prioriteit 2: Als geen dimensiewaarde is gebruikt, check randomize
        if not final_value_str and (step.get('randomize') or step.get('input_method') == 'randomize'):
            random_type = step.get('random_type', 'Generic Term')
            # ... (logica voor het genereren van random waardes blijft hier) ...
            # Genereer willekeurige waarde op basis van het type
            if random_type == 'First Name':
                # Include both German and Dutch first names
                first_names = [
                    # German names
                    'Hans', 'Klaus', 'Peter', 'Michael', 'Wolfgang', 'Thomas', 'Andreas', 'Stefan', 'Martin', 'Christian',
                    'Anna', 'Maria', 'Ursula', 'Monika', 'Elisabeth', 'Petra', 'Sabine', 'Andrea', 'Claudia', 'Susanne',
                    # Dutch names
                    'Jan', 'Piet', 'Klaas', 'Willem', 'Hendrik', 'Maria', 'Anna', 'Sara', 'Emma', 'Sophie'
                ]
                final_value_str = random.choice(first_names)
                self._update_status(f"Using random first name: {final_value_str}", "input", {"selector": selector, "value": final_value_str})
            elif random_type == 'Last Name':
                # Include both German and Dutch last names
                last_names = [
                    # German names
                    'Müller', 'Schmidt', 'Schneider', 'Fischer', 'Weber', 'Meyer', 'Wagner', 'Becker', 'Schulz', 'Hoffmann',
                    # Dutch names
                    'Jansen', 'de Vries', 'van den Berg', 'Bakker', 'Visser', 'Meijer', 'de Boer', 'Mulder', 'de Groot', 'Bos'
                ]
                final_value_str = random.choice(last_names)
                self._update_status(f"Using random last name: {final_value_str}", "input", {"selector": selector, "value": final_value_str})
            elif random_type == 'Email Address':
                domains = ['gmail.com', 'outlook.com', 'hotmail.com', 'yahoo.com', 'protonmail.com', 'gmx.de', 'web.de', 't-online.de']
                first_names = ['jan', 'piet', 'klaas', 'hans', 'klaus', 'peter', 'maria', 'anna', 'sara', 'emma']
                last_names = ['mueller', 'schmidt', 'schneider', 'jansen', 'devries', 'bakker', 'visser', 'meijer', 'deboer']
                numbers = [str(random.randint(1, 999)) for _ in range(3)]

                # Create email with random parts
                parts = [random.choice(first_names), random.choice(last_names), random.choice(numbers)]
                random.shuffle(parts)
                email_name = '.'.join(parts[:2])
                domain = random.choice(domains)
                final_value_str = f"{email_name}@{domain}"
                self._update_status(f"Using random email: {final_value_str}", "input", {"selector": selector, "value": final_value_str})
            elif random_type == 'Street':
                # German street names
                streets = [
                    'Hauptstraße', 'Schulstraße', 'Bahnhofstraße', 'Gartenstraße', 'Kirchstraße',
                    'Bergstraße', 'Waldstraße', 'Dorfstraße', 'Lindenstraße', 'Poststraße'
                ]
                final_value_str = random.choice(streets)
                self._update_status(f"Using random street: {final_value_str}", "input", {"selector": selector, "value": final_value_str})
            elif random_type == 'City':
                # German cities
                cities = [
                    'Berlin', 'Hamburg', 'München', 'Köln', 'Frankfurt',
                    'Stuttgart', 'Düsseldorf', 'Leipzig', 'Dortmund', 'Essen'
                ]
                final_value_str = random.choice(cities)
                self._update_status(f"Using random city: {final_value_str}", "input", {"selector": selector, "value": final_value_str})
            elif random_type == 'Phone Number':
                # German mobile phone format
                prefix = random.choice(['0151', '0152', '0157', '0159', '0160', '0170', '0171', '0172', '0173', '0174'])
                number = ''.join([str(random.randint(0, 9)) for _ in range(8)])
                final_value_str = f"{prefix}{number}"
                self._update_status(f"Using random phone number: {final_value_str}", "input", {"selector": selector, "value": final_value_str})
            elif random_type == 'Postal Code':
                # German postal code (5 digits)
                final_value_str = str(random.randint(10000, 99999))
                self._update_status(f"Using random postal code: {final_value_str}", "input", {"selector": selector, "value": final_value_str})
            elif random_type == 'House Number':
                # German house number (1-999, optionally with a letter)
                number = random.randint(1, 999)
                if random.random() < 0.1:  # 10% chance to add a letter
                    letter = random.choice(['a', 'b', 'c', 'd'])
                    final_value_str = f"{number}{letter}"
                else:
                    final_value_str = str(number)
                self._update_status(f"Using random house number: {final_value_str}", "input", {"selector": selector, "value": final_value_str})
            elif random_type == 'Password':
                # Haal wachtwoordinstellingen op uit stap
                min_length = int(step.get('password_min_length', 8))  # Ensure this is an integer
                max_length = int(step.get('password_max_length', 16))  # Ensure this is an integer
                include_uppercase = step.get('password_include_uppercase', True)
                include_numbers = step.get('password_include_numbers', True)
                include_special = step.get('password_include_special', True)

                # Debug logging
                self._update_status(
                    f"Password settings - min_length: {min_length}, max_length: {max_length}, " +
                    f"uppercase: {include_uppercase}, numbers: {include_numbers}, special: {include_special}",
                    "debug"
                )

                # Bepaal de tekens die gebruikt kunnen worden
                chars = string.ascii_lowercase
                if include_uppercase:
                    chars += string.ascii_uppercase
                if include_numbers:
                    chars += string.digits
                if include_special:
                    # Use a more limited set of special characters that are more likely to work across websites
                    chars += '!@#$%^&*'

                # Genereer een wachtwoord met willekeurige lengte tussen min en max
                password_length = random.randint(min_length, max_length)

                # Ensure at least one character of each required type is included
                must_include = []
                if include_uppercase:
                    must_include.append(random.choice(string.ascii_uppercase))
                if include_numbers:
                    must_include.append(random.choice(string.digits))
                if include_special:
                    must_include.append(random.choice('!@#$%^&*'))

                # Generate remaining characters
                remaining_length = password_length - len(must_include)
                remaining_chars = [random.choice(chars) for _ in range(remaining_length)]

                # Combine and shuffle
                all_chars = must_include + remaining_chars
                random.shuffle(all_chars)

                # Generate the password and ensure it's a string
                password = ''.join(all_chars)
                final_value_str = password  # Store the password

                # Log the password generation (without showing the actual password)
                self._update_status(
                    f"Generated random password (length: {password_length})",
                    "input",
                    {
                        "selector": selector,
                        "value": "[HIDDEN]",
                        "length": str(password_length),
                        "includes_uppercase": str(include_uppercase),
                        "includes_numbers": str(include_numbers),
                        "includes_special": str(include_special)
                    }
                )
            else:  # Generic Term
                terms = ['test', 'sample', 'example', 'demo', 'trial', 'preview', 'beta', 'review', 'check', 'verify']
                final_value_str = random.choice(terms)
                self._update_status(f"Using random term: {final_value_str}", "input", {"selector": selector, "value": final_value_str})


        # Prioriteit 3: Gebruik de 'value' uit de step configuratie
        if not final_value_str:
            if 'value' not in step:
                self._update_status(f"No value specified for input step and not a dimension/random field, using empty string", "warn")
                final_value_str = ""
            else:
                final_value_str = step['value']

                # Vervang eventuele variabelen in de value string (als die er toch zijn)
                if dimensions:
                    temp_value = final_value_str
                    for key in ['thickness', 'width', 'length', 'quantity']:
                        if f"{{{key}}}" in temp_value:
                            if key in dimensions:
                                converted_value = self._convert_value(dimensions[key], unit)
                                if isinstance(converted_value, float) and converted_value.is_integer():
                                    converted_value = int(converted_value)
                                temp_value = temp_value.replace(f"{{{key}}}", str(converted_value))
                                unit_display = unit
                                self._update_status(
                                    f"Replacing variable {{{key}}} in step value with {converted_value} {unit_display}",
                                    "input", {"selector": selector}
                                )
                            else:
                                self._update_status(f"Dimension {key} not found for variable in value", "warn")
                    final_value_str = temp_value # Update final value if variables were replaced

        # Log de definitieve waarde die we gaan gebruiken
        logging.info(f"Final value to input for {selector}: {final_value_str}")
        # Correct the random_type check here, initialize random_type if not set
        random_type_for_log = None
        if 'random_type' in locals():
             random_type_for_log = random_type

        self._update_status(f"Setting input value to {final_value_str if random_type_for_log != 'Password' else '[HIDDEN]'}", "input", {"selector": selector, "value": final_value_str if random_type_for_log != 'Password' else '[HIDDEN]'})

        # === De rest van de functie blijft hetzelfde: element zoeken en waarde invullen ===
        for attempt in range(max_retries):
            try:
                # Wacht langer op het element in de online omgeving
                element = await page.wait_for_selector(selector)
                if not element:
                    raise ValueError(f"Element not found: {selector}")

                # Add highlight to the element
                await self._highlight_element(page, element)

                # Scroll naar het element om zeker te zijn dat het zichtbaar is
                await element.scroll_into_view_if_needed()

                # Focus op het element voordat we beginnen
                await element.focus()

                if clear_first:
                    # Leeg het veld op verschillende manieren
                    await element.evaluate('(el) => { el.value = ""; }')

                    # Selecteer alle tekst en verwijder
                    await element.click(click_count=3)  # Triple click selecteert alle tekst
                    await element.press('Backspace')

                # Type de NIEUWE definitieve waarde
                try:
                    # Handle passwords with special characters
                    if random_type_for_log == 'Password': # Check against potentially set random_type_for_log
                        # First try with type()
                        await element.type(final_value_str, delay=50)
                    else:
                        await element.type(final_value_str, delay=50)

                    # Stuur events om de website te informeren over de wijziging
                    await element.evaluate('''(el) => {
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                        el.dispatchEvent(new Event('change', { bubbles: true }));
                        el.dispatchEvent(new Event('blur', { bubbles: true }));
                    }''')

                    # Bevestig dat de waarde correct is ingevoerd
                    actual_value = await element.evaluate('(el) => el.value')
                    # Always convert to string for comparison
                    actual_value_str = str(actual_value)
                    # Compare with final_value_str

                    if actual_value_str == final_value_str or final_value_str in actual_value_str:
                        self._update_status(f"Successfully set input to {final_value_str if random_type_for_log != 'Password' else '[HIDDEN]'}", "input", {"status": "success"})
                        break
                    else:
                        self._update_status(f"Value mismatch: expected '{final_value_str}' not matching actual '{actual_value_str}'", "warn")

                        # For passwords or values with special characters, try an alternative method as a last resort
                        if attempt == max_retries - 1:
                            # Try direct JavaScript fill for the password
                            value_to_set = final_value_str # Use the final determined value

                            # Double escape special characters for JavaScript
                            # Correctly escape the backslash for Python's replace method
                            escaped_value = value_to_set.replace('\\', '\\\\').replace('"', '\\"').replace("'", "\\'")
                            js_code = f'''(el) => {{
                                try {{
                                    // First try direct value assignment
                                    el.value = "{escaped_value}";
                                    // Then dispatch appropriate events
                                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    return true;
                                }} catch(e) {{
                                    console.error("Error setting value:", e);
                                    return false;
                                }}
                            }}'''

                            success = await element.evaluate(js_code)
                            if success:
                                self._update_status("Successfully set value using JavaScript method", "input", {"status": "success"})
                            else:
                                self._update_status("Failed to set value with all methods", "error")

                except Exception as e:
                    self._update_status(f"Error in typing: {str(e)}", "warn")
                    if attempt == max_retries - 1:
                        # As a last resort for passwords, try filling character by character
                        if random_type_for_log == 'Password': # Check against potentially set random_type_for_log
                            try:
                                await element.fill('')  # Clear first
                                password = final_value_str # Use the final determined value
                                for char in password:
                                    await page.keyboard.press(char)
                                self._update_status("Typed password character by character", "input")
                            except Exception as char_error:
                                self._update_status(f"Character-by-character typing failed: {str(char_error)}", "error")

            except Exception as e:
                self._update_status(f"Error setting input (attempt {attempt+1}/{max_retries}): {str(e)}", "warn")
                if attempt == max_retries - 1:  # als dit de laatste poging was
                    self._update_status(f"Failed to set input after {max_retries} attempts", "error")
                    raise

    async def _handle_click(self, page, step, dimensions=None):
        """Handle a click step"""
        selector = step['selector']
        description = step.get('description', '')
        max_retries = 2

        # Support dynamic selector creation with variable substitution
        selector = self._substitute_dynamic_selector(selector, dimensions, step, "click")

        # Add more descriptive messages for specific actions
        if 'figure' in selector.lower():
            self._update_status(f"Selecting figure shape", "click", {"selector": selector})
        elif 'calculator' in selector.lower():
            self._update_status(f"Opening calculator section", "click", {"selector": selector})
        elif 'winkelwagen' in selector.lower() or '.cart' in selector.lower():
            self._update_status(f"Adding to shopping cart", "click", {"selector": selector})
        elif 'data-key' in selector:
            self._update_status(f"Selecting element with data-key", "click", {"selector": selector})
        else:
            self._update_status(f"Clicking {selector}", "click", {"selector": selector})

        for attempt in range(max_retries):
            try:
                # Wacht langer op het element
                element = await page.wait_for_selector(selector)
                if not element:
                    raise ValueError(f"Element not found: {selector}")

                # Add highlight to the element
                await self._highlight_element(page, element)

                # Zorg ervoor dat het element zichtbaar is
                is_visible = await element.is_visible()
                if not is_visible:
                    self._update_status(f"Element {selector} is not visible, trying to scroll into view", "warn")
                    await element.scroll_into_view_if_needed()

                # Als het een .cart element is of winkelwagen, probeer het op verschillende manieren te klikken
                if '.cart' in selector.lower() or 'winkelwagen' in selector.lower():
                    # Probeer eerst JavaScript klik
                    try:
                        await page.evaluate(f"""
                            const element = document.querySelector('{selector}');
                            if (element) {{
                                // Zorg ervoor dat het element zichtbaar is
                                element.style.zIndex = '9999';
                                element.style.position = 'relative';
                                element.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                                    element.click();
                            }}
                        """)
                        self._update_status(f"Clicked {selector} using JavaScript", "click", {"status": "success"})
                    except Exception as js_error:
                        self._update_status(f"JavaScript click failed: {str(js_error)}", "warn")
                        # Als JavaScript klik mislukt, probeer normale klik
                        await element.click()
                else:
                    # Normale klik voor andere elementen
                    await element.click()

                self._update_status(f"Successfully clicked {selector}", "click", {"status": "success"})
                return True

            except Exception as e:
                self._update_status(f"Click failed (attempt {attempt+1}/{max_retries}): {str(e)}", "warn")

                # Speciale aanpak voor cart elementen bij laatste poging
                if attempt == max_retries - 1 and ('.cart' in selector.lower() or 'winkelwagen' in selector.lower()):
                    try:
                        # Laatste poging: gebruik execute_script voor direct document.querySelector
                        self._update_status(f"Trying alternative method to click {selector}", "click")
                        await page.evaluate(f"""
                            const cart = document.querySelector('{selector}');
                            if (cart) {{
                                cart.style.pointerEvents = 'auto';
                                cart.style.opacity = '1';
                                cart.style.visibility = 'visible';
                                cart.style.display = 'block';
                                cart.style.zIndex = '10000';
                                cart.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                                cart.click();
                            }}
                        """)
                        self._update_status(f"Attempted alternative click on {selector}", "click")
                        return True
                    except Exception as final_error:
                        self._update_status(f"All click attempts failed: {str(final_error)}", "error")

                if attempt == max_retries - 1:
                    self._update_status(f"Click failed after {max_retries} attempts", "error")
                    raise

    async def _handle_wait(self, page, step):
        """Handle wait step"""
        self._update_status(f"Waiting for {step.get('duration', 'default')} duration...", 'wait')

        # Map duration to actual seconds
        duration_map = {
            'short': 0.5,
            'default': 1.0,
            'long': 1.5,
            'longer': 3.0,
            'longest': 5.0
        }

        duration = duration_map.get(step.get('duration', 'default'), 1.0)
        await asyncio.sleep(duration)

    async def _handle_read_price(self, page, step, dimensions=None):
        """Handle a read_price step"""
        try:
            selector = step.get('selector')
            if not selector:
                raise ValueError("Selector is required for read_price step")

            # Wait for the price element
            try:
                price_element = await page.wait_for_selector(selector, state="visible")
                if not price_element:
                    raise Exception(f"Price element not found: {selector}")
            except Exception as e:
                if step.get('continue_on_error', False):
                    self._update_status(
                        f"Could not find price element, returning 0.00: {str(e)}",
                        'warn',
                        {**step, 'error': str(e), 'price': 0.00}
                    )
                    return 0.00
                raise

            # Get the price text
            price_text = await price_element.text_content()
            if not price_text:
                if step.get('continue_on_error', False):
                    self._update_status(
                        "Price element is empty, returning 0.00",
                        'warn',
                        {**step, 'error': 'Empty price element', 'price': 0.00}
                    )
                    return 0.00
                raise ValueError("Price element is empty")

            # Extract and process the price
            price = self._extract_price(price_text)

            # Apply calculation if specified
            if step.get('calculation'):
                calculation = step['calculation']
                # Replace variables in calculation
                if dimensions:
                    for key, value in dimensions.items():
                        calculation = calculation.replace(f"{{{key}}}", str(value))
                calculation = calculation.replace("price", str(price))
                try:
                    price = float(eval(calculation))
                except Exception as e:
                    if step.get('continue_on_error', False):
                        self._update_status(
                            f"Calculation failed, returning original price: {str(e)}",
                            'warn',
                            {**step, 'error': str(e), 'price': price}
                        )
                    else:
                        raise ValueError(f"Error in calculation: {str(e)}")

            self._update_status(
                "Successfully read price",
                'read_price',
                {**step, 'price': price}
            )
            return price

        except Exception as e:
            if step.get('continue_on_error', False):
                self._update_status(
                    f"Error reading price, returning 0.00: {str(e)}",
                    'warn',
                    {**step, 'error': str(e), 'price': 0.00}
                )
                return 0.00
            raise

    def _extract_price(self, price_text: str) -> float:
        """Extract numeric price from text, handling different thousand/decimal separators."""
        try:
            # Log the original price text for debugging
            logging.info(f"Extracting price from: '{price_text}'")

            # First, try to find a number pattern with optional currency symbols
            # This regex looks for: optional currency, number with optional separators, optional currency
            price_pattern = r'[€$£¥]?\s*(\d{1,3}(?:[,.]\d{3})*(?:[,.]\d{1,2})?)\s*[€$£¥]?'

            match = re.search(price_pattern, price_text)
            if not match:
                # Fallback: look for any number in the text
                number_pattern = r'(\d+(?:[,.]\d+)?)'
                match = re.search(number_pattern, price_text)
                if not match:
                    logging.warning(f"No numeric value found in price text: '{price_text}'")
                    return 0.0

            number_str = match.group(1)
            logging.info(f"Extracted number string: '{number_str}'")

            # Now handle the decimal/thousands separator logic
            has_dot = '.' in number_str
            has_comma = ',' in number_str

            if has_dot and has_comma:
                # Both present - determine which is decimal separator
                last_dot_pos = number_str.rfind('.')
                last_comma_pos = number_str.rfind(',')

                if last_comma_pos > last_dot_pos:
                    # Comma is decimal separator (e.g., 1.234,56)
                    number_str = number_str.replace('.', '').replace(',', '.')
                else:
                    # Dot is decimal separator (e.g., 1,234.56)
                    number_str = number_str.replace(',', '')
            elif has_comma and not has_dot:
                # Only comma - check if it's likely decimal or thousands separator
                comma_pos = number_str.rfind(',')
                digits_after_comma = len(number_str) - comma_pos - 1

                if digits_after_comma <= 2:
                    # Likely decimal separator (e.g., 29,81)
                    number_str = number_str.replace(',', '.')
                else:
                    # Likely thousands separator (e.g., 1,234)
                    number_str = number_str.replace(',', '')
            # If only dot or no separators, leave as is

            result = float(number_str)
            logging.info(f"Successfully extracted price: {result}")
            return result

        except Exception as e:
            logging.error(f"Error extracting price from '{price_text}': {str(e)}")
            return 0.0

    async def _fill_select_field(self, page: Page, selector: str, value: float) -> None:
        logging.info(f"\nZoeken naar thickness veld met selector: {selector}")

        # Check if this is a custom dropdown for voskunststoffen.nl
        if selector.startswith('#partControlDropDownThickness'):
            try:
                # First click the trigger element to open the dropdown
                trigger = await page.wait_for_selector(selector)
                if not trigger:
                    raise ValueError(f"Kon geen dropdown trigger vinden met selector: {selector}")

                await trigger.click()
                await page.wait_for_timeout(500)  # Wait for dropdown to open

                # Now find the option in the popper container
                option_selector = f"li[data-value='{value}']"
                option = await page.wait_for_selector(option_selector, state="visible")
                if not option:
                    raise ValueError(f"Kon geen optie vinden voor waarde {value}mm")

                await option.click()
                await page.wait_for_timeout(500)  # Wait for selection to process

                logging.info(f"Custom dropdown: waarde {value}mm geselecteerd")
                return

            except Exception as e:
                raise ValueError(f"Error bij custom dropdown selectie: {str(e)}")

        # Regular select field handling
        element = await page.wait_for_selector(selector)
        if not element:
            raise ValueError(f"Kon geen element vinden met selector: {selector}")

        logging.info(f"Select veld gevonden, waarde invullen: {value}")

        # Get all available options
        options = await element.evaluate('''(select) => {
            return Array.from(select.options).map(option => ({
                value: option.value,
                text: option.text.trim()
            }));
        }''')

        logging.info(f"Beschikbare opties: {options}")

        # Try to find a matching option
        match_found = False
        for option in options:
            option_text = option['text']
            logging.info(f"Controleren optie: '{option_text}'")

            # Extract number from option text (e.g. "3mm" -> 3.0)
            number_match = re.search(r'(\d+(?:\.\d+)?)', option_text)
            if number_match:
                option_value = float(number_match.group(1))
                if abs(option_value - value) < 0.1:  # Allow small difference for float comparison
                    match_found = True
                    logging.info(f"Match gevonden! Selecteren van optie: {option_text}")
                    await element.select_option(value=option['value'])
                    await page.evaluate('(el) => { el.dispatchEvent(new Event("change")); }', element)
                    await page.wait_for_timeout(1000)
                    break

        if not match_found:
            available_thicknesses = ", ".join(opt['text'] for opt in options)
            raise ValueError(f"Kon geen passende optie vinden voor waarde {value}mm in select veld. Beschikbare diktes: {available_thicknesses}")

    async def _find_nearest_element(self, page, search_terms: List[str], element_type: str = 'text') -> Optional[Dict]:
        """
        Zoekt naar specifieke termen en vindt het dichtstbijzijnde relevante element.
        """
        try:
            # Verzamel alle tekst elementen
            elements = await page.query_selector_all('*')
            matches = []

            for element in elements:
                try:
                    # Haal tekst op van het element
                    text = await element.text_content()
                    if not text:
                        continue

                    text = text.lower().strip()

                    # Check of een van de zoektermen voorkomt
                    if any(term.lower() in text for term in search_terms):
                        if element_type == 'text':
                            # Voor m² prijzen: zoek naar getallen in dezelfde tekst
                            price_matches = re.findall(r'€?\s*(\d+(?:[,.]\d+)?)', text)
                            if price_matches:
                                price = float(price_matches[0].replace(',', '.'))
                                matches.append({
                                    'text': text,
                                    'value': price,
                                    'distance': 0  # Directe match in dezelfde tekst
                                })
                        else:
                            # Voor form fields: zoek naar input/select elementen in de buurt
                            # 1. Check voor een explicit label-for relatie
                            tag_name = await element.evaluate('node => node.tagName.toLowerCase()')
                            if tag_name == 'label':
                                field_id = await element.get_attribute('for')
                                if field_id:
                                    field = await page.query_selector(f'#{field_id}')
                                    if field:
                                        field_tag = await field.evaluate('node => node.tagName.toLowerCase()')
                                        if (element_type == 'select' and field_tag == 'select') or \
                                           (element_type == 'input' and field_tag == 'input'):
                                            matches.append({
                                                'text': text,
                                                'id': field_id,
                                                'distance': 0  # Directe label relatie
                                            })
                                            continue

                            # 2. Check voor elementen in de parent container
                            parent = await element.query_selector('..')
                            if parent:
                                selector = element_type
                                if element_type == 'select':
                                    selector = 'select, [class*="select"], [class*="dropdown"]'
                                elif element_type == 'input':
                                    selector = 'input[type="text"], input[type="number"], input:not([type])'

                                nearby = await parent.query_selector_all(selector)
                                for field in nearby:
                                    field_id = await field.get_attribute('id')
                                    matches.append({
                                        'text': text,
                                        'id': field_id,
                                        'distance': 1  # In dezelfde parent
                                    })

                            # 3. Check voor elementen in de grootouder container
                            grandparent = await parent.query_selector('..')
                            if grandparent:
                                selector = element_type
                                if element_type == 'select':
                                    selector = 'select, [class*="select"], [class*="dropdown"]'
                                elif element_type == 'input':
                                    selector = 'input[type="text"], input[type="number"], input:not([type])'

                                nearby = await grandparent.query_selector_all(selector)
                                for field in nearby:
                                    field_id = await field.get_attribute('id')
                                    matches.append({
                                        'text': text,
                                        'id': field_id,
                                        'distance': 2  # In de grootouder
                                    })

                except Exception as e:
                    continue

            # Sorteer matches op afstand (dichtsbij eerst)
            matches.sort(key=lambda x: x['distance'])

            if matches:
                return matches[0]

            return None

        except Exception as e:
            print(f"Error bij zoeken naar element: {str(e)}")
            return None

    async def analyze_form_fields(self, url: str) -> Dict:
        """Analyseert de form fields op de pagina"""
        try:
            async with async_playwright() as p:
                # Launch browser in non-headless mode
                browser = await p.chromium.launch(headless=HEADLESS)
                # Create page with full HD viewport
                page = await browser.new_page(viewport={'width': 1920, 'height': 1080})
                await page.goto(url)

                dimension_fields = {}

                # Zoektermen voor verschillende dimensies
                dimension_terms = {
                    'dikte': {
                        'terms': ['dikte', 'thickness', 'dicke', 'épaisseur', 'mm', 'millimeter'],
                        'type': 'select'
                    },
                    'lengte': {
                        'terms': ['lengte', 'length', 'länge', 'longueur'],
                        'type': 'input'
                    },
                    'breedte': {
                        'terms': ['breedte', 'width', 'breite', 'largeur', 'hoogte', 'height', 'höhe', 'hauteur'],
                        'type': 'input'
                    }
                }

                # Zoek naar elk type dimensie
                for dimension, config in dimension_terms.items():
                    result = await self._find_nearest_element(
                        page,
                        config['terms'],
                        config['type']
                    )

                    if result:
                        print(f"Gevonden {dimension} veld: {result['text']}")
                        dimension_fields[dimension] = [{
                            'id': result['id'],
                            'label': result['text'],
                            'tag': config['type']
                        }]

                await browser.close()
                return dimension_fields

        except Exception as e:
            print(f"Error tijdens form analyse: {str(e)}")
            return {}

    async def _handle_blur(self, page, step):
        """Handle a blur step by either using the selector from the step or the last interacted element"""
        selector = step.get('selector')

        try:
            if selector:
                # If a selector is provided, use it
                self._update_status(f"Triggering blur on {selector}", "blur", {"selector": selector})
                element = await page.wait_for_selector(selector)
                if element:
                    await element.evaluate('(el) => { el.blur(); }')
                    self._update_status(f"Blur completed on {selector}", "blur", {"selector": selector, "status": "success"})
            else:
                # If no selector is provided, try to blur the active element
                self._update_status("Triggering blur on active element", "blur")
                await page.evaluate('() => { document.activeElement?.blur(); }')
                self._update_status("Blur completed on active element", "blur", {"status": "success"})
        except Exception as e:
            self._update_status(f"Blur failed: {str(e)}", "error")
            raise

    async def _handle_modify(self, page, step, dimensions=None):
        """Handle a modify_element step that runs JavaScript to modify an element"""
        selector = step['selector']
        script = step.get('script', '')
        add_class = step.get('add_class', '')
        add_attribute = step.get('add_attribute', {})
        value = step.get('value', '')

        # Als er dimensions zijn meegegeven en er is een value met variabelen
        if dimensions and value:
            # Vervang alle variabelen in de value string
            for var_name, var_value in dimensions.items():
                value = value.replace(f"{{{var_name}}}", str(var_value))

        self._update_status(f"Modifying element {selector}", "modify", {"selector": selector, "add_class": add_class})

        try:
            # Wacht tot het element beschikbaar is
            element = await page.wait_for_selector(selector)
            if not element:
                if step.get('continue_on_error', False):
                    self._update_status(f"Element not found: {selector}, continuing...", "warn")
                    return
                self._update_status(f"Element not found: {selector}", "error")
                return

            if add_class:
                # Voeg een class toe aan het element
                await page.evaluate("""
                    const element = document.querySelector(""" + f'"{selector}"' + """);
                    if (element) {{
                        element.classList.add(""" + f'"{add_class}"' + """);
                    }}
                """)
                self._update_status(f"Added class '{add_class}' to {selector}", "modify", {"status": "success"})

            if value:
                # Zet de waarde van het element
                await page.evaluate("""
                    const element = document.querySelector(""" + f'"{selector}"' + """);
                    if (element) {{
                        if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA' || element.tagName === 'SELECT') {{
                            element.value = """ + f'"{value}"' + """;
                        }} else {{
                            element.textContent = """ + f'"{value}"' + """;
                        }}
                    }}
                """)
                self._update_status(f"Set value of {selector} to '{value}'", "modify", {"status": "success"})

            if add_attribute and isinstance(add_attribute, dict):
                # Voeg attributen toe aan het element
                for attr_name, attr_value in add_attribute.items():
                    await page.evaluate("""
                        const element = document.querySelector(""" + f'"{selector}"' + """);
                        if (element) {{
                            element.setAttribute(""" + f'"{attr_name}", "{attr_value}"' + """);
                        }}
                    """)
                self._update_status(f"Added attributes to {selector}", "modify", {"status": "success"})

            if script:
                # Voer custom JavaScript uit
                await page.evaluate("""
                    const element = document.querySelector(""" + f'"{selector}"' + """);
                    if (element) {{
                        {script}
                    }}
                """)
                self._update_status(f"Executed custom script on {selector}", "modify", {"status": "success"})

        except Exception as e:
            if step.get('continue_on_error', False):
                self._update_status(f"Error modifying element: {str(e)}, continuing...", "warn")
                return
            self._update_status(f"Error modifying element: {str(e)}", "error")
            raise

    async def _handle_navigate(self, page, step):
        """Handle a navigate step that navigates to a specific URL"""
        url = step['url']
        wait_for_load = step.get('wait_for_load', True)
        timeout = step.get('timeout', 30) * 1000  # Convert to milliseconds

        # Handle relative URLs
        if url.startswith('/'):
            # Get the current page URL and combine with relative path
            current_url = page.url
            base_url = '/'.join(current_url.split('/')[:3])  # Get protocol + domain
            url = f"{base_url}{url}"

        self._update_status(f"Navigating to {url}", "navigate", {"url": url})

        try:
            # Navigate to the URL
            await page.goto(url, wait_until='networkidle' if wait_for_load else 'domcontentloaded', timeout=timeout)

            if wait_for_load:
                # Wait for the page to be fully loaded
                await page.wait_for_load_state('load', timeout=timeout)

            self._update_status(f"Successfully navigated to {url}", "navigate", {"status": "success"})

        except Exception as e:
            if step.get('continue_on_error', False):
                self._update_status(f"Navigation failed: {str(e)}, continuing...", "warn")
                return
            self._update_status(f"Navigation failed: {str(e)}", "error")
            raise

    async def _handle_reload(self, page, step):
        """Handle a reload step that reloads the current page"""
        wait_for_load = step.get('wait_for_load', True)
        timeout = step.get('timeout', 30) * 1000  # Convert to milliseconds

        self._update_status("Reloading page", "reload")

        try:
            # Reload the current page - start basic reload without waiting
            await page.reload(wait_until='commit', timeout=timeout)

            if wait_for_load:
                # Use the same robust waiting strategy as the main page loading
                try:
                    # Strategy 1: Wait for network idle (most reliable for dynamic content)
                    await page.wait_for_load_state('networkidle', timeout=15000)
                    self._update_status("Page reloaded successfully (networkidle)", "reload", {"status": "success"})
                except:
                    try:
                        # Strategy 2: Wait for DOM content to be loaded
                        await page.wait_for_load_state('domcontentloaded', timeout=10000)
                        # Give a bit more time for any remaining dynamic content
                        await asyncio.sleep(2)
                        self._update_status("Page reloaded successfully (domcontentloaded)", "reload", {"status": "success"})
                    except:
                        # Strategy 3: Fallback - just wait a reasonable amount of time
                        await asyncio.sleep(3)
                        self._update_status("Page reload timeout, proceeding anyway", "reload", {"status": "timeout"})
            else:
                self._update_status("Page reloaded (no wait)", "reload", {"status": "success"})

        except Exception as e:
            if step.get('continue_on_error', False):
                self._update_status(f"Page reload failed: {str(e)}, continuing...", "warn")
                return
            self._update_status(f"Page reload failed: {str(e)}", "error")
            raise

    async def _process_step(self, page, step, dimensions=None):
        """Process a single step in the configuration"""
        step_type = step['type']

        try:
            if step_type == 'select':
                await self._handle_select(page, step, dimensions)
            elif step_type == 'input':
                await self._handle_input(page, step, dimensions)
            elif step_type == 'click':
                await self._handle_click(page, step, dimensions)
            elif step_type == 'wait':
                await self._handle_wait(page, step)
            elif step_type == 'blur':
                await self._handle_blur(page, step)
            elif step_type == 'modify_element':
                await self._handle_modify(page, step, dimensions)
            elif step_type == 'read_price':
                price = await self._handle_read_price(page, step, dimensions)
                return price
            elif step_type == 'navigate':
                await self._handle_navigate(page, step)
            elif step_type == 'reload':
                await self._handle_reload(page, step)
            elif step_type == 'captcha':
                await self._handle_captcha(page, step)
            elif step_type == 'decide_config':
                result = await self._handle_decide_config(page, step)
                return result
            else:
                raise ValueError(f"Unknown step type: {step_type}")

        except Exception as e:
            if step.get('continue_on_error', False):
                self._update_status(f"Step failed: {str(e)}, continuing...", "warn")
                return
            self._update_status(f"Step failed: {str(e)}", "error")
            raise

    async def _handle_captcha(self, page, step):
        """Handle captcha step"""
        self._update_status("Handling captcha...", "captcha")

        solving_method = step.get('solving_method', 'Manual')

        try:
            captcha_type = step.get('captcha_type', 'checkbox')
            frame_selector = step.get('frame_selector')
            selector = step.get('selector')

            if solving_method == 'External Service (2Captcha)':
                # Get 2Captcha API key from settings
                db = SessionLocal()
                try:
                    api_key = Settings.get_value(db, '2captcha_api_key')
                    if not api_key:
                        self._update_status("No 2Captcha API key configured in settings", "error")
                        raise Exception("2Captcha API key not configured")
                finally:
                    db.close()

                if captcha_type == 'recaptcha_v2':
                    # Handle reCAPTCHA v2
                    if frame_selector:
                        frame = await page.query_selector(frame_selector)
                        if not frame:
                            raise Exception(f"Captcha frame not found: {frame_selector}")

                    # Get the sitekey
                    site_key = await page.evaluate("""() => {
                        for (const element of document.getElementsByTagName('div')) {
                            if (element.getAttribute('data-sitekey')) {

                                return element.getAttribute('data-sitekey');
                            }
                        }
                        return null;
                    }""")

                    if not site_key:
                        raise Exception("reCAPTCHA sitekey not found")

                    # Solve using 2captcha
                    solver = TwoCaptcha(api_key)
                    result = solver.recaptcha(
                        sitekey=site_key,
                        url=page.url,
                        invisible=True
                    )

                    if not result or not result.get('code'):
                        raise Exception("Failed to solve reCAPTCHA")

                    # Insert the solution
                    await page.evaluate(f"""(response) => {{
                        document.getElementById('g-recaptcha-response').innerHTML = response;
                        ___grecaptcha_cfg.clients[0].K.K.callback(response);
                    }}, "{result['code']}")""")

                else:  # checkbox captcha
                    # Find the checkbox
                    checkbox = await page.query_selector(selector) if selector else await page.query_selector('input[type="checkbox"]')
                    if not checkbox:
                        raise Exception("Captcha checkbox not found")

                    # Click the checkbox
                    await checkbox.click()

            else:  # Manual solving
                # For manual solving, we just click the checkbox and let the user handle any challenges
                checkbox = await page.query_selector(selector) if selector else await page.query_selector('input[type="checkbox"]')
                if not checkbox:
                    raise Exception("Captcha checkbox not found")

                await checkbox.click()

                # If it's reCAPTCHA v2, we need to wait for the user to solve it
                if captcha_type == 'recaptcha_v2':
                    self._update_status("Waiting for manual captcha solution...", "captcha")
                    # Wait for the g-recaptcha-response to be filled
                    await page.wait_for_function("""
                        () => document.querySelector('textarea#g-recaptcha-response')?.value
                    """, timeout=60000)  # 60 second timeout for manual solving

            self._update_status("Captcha handled successfully", "captcha", {"status": "success"})

        except Exception as e:
            if step.get('skip_on_failure', True):
                self._update_status(f"Captcha handling failed: {str(e)}, continuing...", "warn")
                return
            self._update_status(f"Captcha handling failed: {str(e)}", "error")
            raise

    async def _handle_decide_config(self, page, step):
        """Handle decide_config step to dynamically switch configurations based on page content"""
        selector = step.get('selector')
        timeout = step.get('timeout', 10)  # Default 10 seconds timeout
        fallback_config = step.get('fallback_config', 'square_meter_price_2')

        if not selector:
            raise ValueError("Selector is required for decide_config step")

        self._update_status(
            f"Checking if element '{selector}' is visible to decide configuration",
            "decide_config",
            {"selector": selector, "timeout": timeout, "fallback_config": fallback_config}
        )

        try:
            # Wait for the selector to be visible within the timeout
            element = await page.wait_for_selector(selector, state="visible", timeout=timeout * 1000)

            if element:
                self._update_status(
                    f"Element '{selector}' found - continuing with current configuration",
                    "decide_config",
                    {"selector": selector, "decision": "continue_current_config", "status": "success"}
                )
                return {"switch_config": False, "current_config": True}

        except Exception as e:
            # Timeout or element not found - switch to fallback configuration
            self._update_status(
                f"Element '{selector}' not found within {timeout}s - switching to '{fallback_config}' configuration",
                "decide_config",
                {
                    "selector": selector,
                    "timeout": timeout,
                    "fallback_config": fallback_config,
                    "decision": "switch_config",
                    "reason": str(e),
                    "status": "config_switched"
                }
            )
            return {"switch_config": True, "new_config": fallback_config}

        # Fallback case (should not reach here, but for safety)
        return {"switch_config": True, "new_config": fallback_config}

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
