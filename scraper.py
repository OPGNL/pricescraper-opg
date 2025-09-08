from playwright.async_api import async_playwright
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse
import logging
from database import SessionLocal
import crud
from config import HEADLESS
import traceback

class MaterialScraper:
    def __init__(self):
        self.db = SessionLocal()

    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()

    def _normalize_domain(self, url: str) -> str:
        """Extract and normalize the domain from a URL"""
        return urlparse(url).netloc.replace('www.', '')

    async def _execute_prerequisite_steps(self, page, steps: List[Dict], target_fields: List[str]) -> None:
        """Execute steps until we reach the fields we need to analyze"""
        for i, step in enumerate(steps):
            step_type = step.get('type')

            # Check if we've reached a field we're looking for
            if step_type == 'input' and step.get('value') in [f'{{{field}}}' for field in target_fields]:
                break

            # Execute non-field steps
            if step_type == 'click':
                selector = step.get('selector')
                if not selector:
                    continue

                try:
                    element = await page.query_selector(selector)
                    if not element:
                        try:
                            await page.wait_for_selector(selector, timeout=5000)
                        except:
                            continue

                    try:
                        await page.click(selector, timeout=5000)
                    except:
                        await page.click(selector, force=True, timeout=5000)

                except Exception:
                    continue

                await page.wait_for_timeout(1000)

            elif step_type == 'wait':
                duration = step.get('duration', 'short')
                if duration == 'default':
                    wait_time = 2000
                elif duration == 'short':
                    wait_time = 1000
                else:
                    wait_time = 3000
                await page.wait_for_timeout(wait_time)

    async def analyze_form_fields(self, url: str) -> Dict[str, Any]:
        """Analyze form fields on the page using domain configuration from database"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=HEADLESS)
            page = await browser.new_page()

            await page.goto(url)

            domain = self._normalize_domain(url)
            config = crud.get_domain_config(self.db, domain)
            if not config:
                raise ValueError(f"No configuration found for domain: {domain}")

            config = config.config
            dimension_fields = {}

            try:
                await page.wait_for_load_state('networkidle')

                # Wait for any upload indicators to disappear
                try:
                    await page.wait_for_selector('.neonConfiguratorUploadIndicator', state='hidden', timeout=30000)
                except Exception:
                    pass

                if 'categories' not in config:
                    await browser.close()
                    return dimension_fields

                # Find and execute prerequisite steps
                target_fields = ['thickness', 'width', 'length']
                for category_name, category_data in config['categories'].items():
                    if 'steps' in category_data:
                        has_target_fields = any(
                            step.get('value') in [f'{{{field}}}' for field in target_fields]
                            for step in category_data['steps']
                            if step.get('type') == 'input'
                        )

                        if has_target_fields:
                            await self._execute_prerequisite_steps(page, category_data['steps'], target_fields)
                            break

                await page.wait_for_timeout(2000)

                # Analyze the fields
                for field_type in target_fields:
                    field_pattern = f"{{{field_type}}}"
                    found_field = False

                    for category_name, category_data in config['categories'].items():
                        if 'steps' not in category_data:
                            continue

                        for step in category_data['steps']:
                            if (step.get('value') == field_pattern and
                                step.get('type') in ['input', 'select']):

                                selector = step.get('selector', '').strip()

                                if not selector:
                                    continue

                                try:
                                    element = await page.wait_for_selector(selector, timeout=5000, state='visible')

                                    if element:
                                        field_info = {
                                            'type': step['type'],
                                            'selector': selector,
                                            'unit': step.get('unit', ''),
                                            'category': category_name
                                        }

                                        if step['type'] == 'select':
                                            options = await self._get_select_options(element)
                                            field_info['options'] = options

                                        dimension_fields[field_type] = field_info
                                        logging.info(f"Found {field_type} field: {field_info}")
                                        found_field = True
                                        break

                                except Exception as e:
                                    logging.warning(f"Could not find {field_type} element with selector '{selector}': {e}")

                        if found_field:
                            break

            except Exception as e:
                logging.exception(f"Error analyzing form fields for URL {url}: {e}")
                await browser.close()
                raise

            await browser.close()
            return dimension_fields

    async def _get_select_options(self, element) -> list:
        """Get options from a select element"""
        options = []
        try:
            option_elements = await element.query_selector_all('option')
            for option in option_elements:
                value = await option.get_attribute('value')
                text = await option.text_content()
                if value and text:
                    options.append({
                        'value': value,
                        'text': text.strip()
                    })
        except Exception as e:
            logging.exception(f"Error getting select options: {str(e)}")
        return options

    async def _fill_dimension_field(self, page, field_config: Dict[str, Any], value: float) -> bool:
        """Fill a dimension field based on configuration"""
        if not field_config.get('exists', True):
            return False

        try:
            element = await page.query_selector(field_config['selector'])
            if not element:
                logging.error(f"Could not find element with selector: {field_config['selector']}")
                return False

            if field_config['type'] == 'select':
                return await self._fill_select_field(element, value)
            else:
                await element.fill(str(value))
                return True

        except Exception as e:
            logging.exception(f"Error filling dimension field: {str(e)}")
            return False

    async def _fill_select_field(self, element, value: float) -> bool:
        """Fill a select field with the closest matching value"""
        try:
            options = await self._get_select_options(element)
            best_match = None
            min_diff = float('inf')

            for option in options:
                try:
                    option_value = float(option['value'])
                    diff = abs(option_value - value)
                    if diff < min_diff:
                        min_diff = diff
                        best_match = option['value']
                except ValueError:
                    continue

            if best_match:
                await element.select_option(best_match)
                return True

            return False

        except Exception as e:
            logging.exception(f"Error filling select field: {str(e)}")
            return False
