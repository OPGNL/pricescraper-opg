import re
import logging
import asyncio
from typing import List, Dict, Optional


class PriceExtractor:
    """Handles price extraction and formatting operations"""

    @staticmethod
    async def extract_price(page, step, dimensions=None):
        """Extract price from page based on step configuration"""
        try:
            # Get the selector from step
            selector = step.get('selector')
            search_terms = step.get('search_terms', [])

            if selector:
                # Direct selector approach
                element = await page.wait_for_selector(selector, timeout=5000)
                if element:
                    text = await element.text_content()
                    if text:
                        price = PriceExtractor.extract_price_from_text(text.strip())
                        if price > 0:
                            return price

            if search_terms:
                # Search for elements containing specific terms
                for term in search_terms:
                    elements = await page.query_selector_all(f'*:has-text("{term}")')
                    for element in elements:
                        try:
                            text = await element.text_content()
                            if text:
                                price = PriceExtractor.extract_price_from_text(text.strip())
                                if price > 0:
                                    return price
                        except Exception:
                            continue

            # Fallback: collect all price elements and find changed ones
            initial_prices = await PriceExtractor.collect_price_elements(page)

            # Wait a bit for any price updates
            await asyncio.sleep(1)

            updated_prices = await PriceExtractor.collect_price_elements(page)
            changed_prices = PriceExtractor.find_changed_prices(initial_prices, updated_prices)

            if changed_prices:
                # Return the first changed price
                return changed_prices[0].get('new_price', 0.0)
            elif updated_prices:
                # Return the highest price if no changes detected
                return max(p['price'] for p in updated_prices)

            return 0.0

        except Exception as e:
            logging.error(f"Error extracting price: {str(e)}")
            return 0.0

    @staticmethod
    def extract_price_from_text(price_text: str) -> float:
        """Extract numeric price from text, handling different thousand/decimal separators."""
        try:
            # Remove currency symbols (€, $, etc.) and leading/trailing whitespace
            cleaned = re.sub(r'[€$\s]+', '', price_text).strip()

            # Check if the string contains likely separators
            has_dot = '.' in cleaned
            has_comma = ',' in cleaned

            # If both or neither are present, or only one type is present multiple times, we need careful parsing
            if has_dot and has_comma:
                # Assume the last separator is the decimal one
                last_dot_pos = cleaned.rfind('.')
                last_comma_pos = cleaned.rfind(',')

                if last_comma_pos > last_dot_pos:
                    # Comma is the decimal separator, dots are thousands
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    # Dot is the decimal separator, commas are thousands
                    cleaned = cleaned.replace(',', '')
            elif has_comma:
                # Only commas present. Assume last comma is decimal if multiple exist (e.g. 1,234,56 -> 1234.56)
                if cleaned.count(',') > 1:
                    # Multiple commas, assume last is decimal
                    parts = cleaned.rsplit(',', 1)
                    cleaned = parts[0].replace(',', '') + '.' + parts[1]
                else:
                    # Single comma, assume it's decimal
                    cleaned = cleaned.replace(',', '.')
            # elif has_dot: -> If only dots, Python's float() handles it if it's a valid float string
            #                 No cleaning needed beyond removing currency/spaces

            # After cleaning, try to convert to float
            # Use regex to find the number pattern again to be sure
            match = re.search(r'[-+]?\d+(\.\d+)?', cleaned)
            if match:
                numeric_string = match.group()
                return float(numeric_string)
            else:
                logging.warning(f"Could not extract valid number from cleaned string: '{cleaned}' (original: '{price_text}')")

        except Exception as e:
            logging.error(f"Error extracting price from '{price_text}': {str(e)}")

        # Return 0.0 if any step failed
        return 0.0
        """Extract numeric price from text, handling different thousand/decimal separators."""
        try:
            # Remove currency symbols (€, $, etc.) and leading/trailing whitespace
            cleaned = re.sub(r'[€$\s]+', '', price_text).strip()

            # Check if the string contains likely separators
            has_dot = '.' in cleaned
            has_comma = ',' in cleaned

            # If both or neither are present, or only one type is present multiple times, we need careful parsing
            if has_dot and has_comma:
                # Assume the last separator is the decimal one
                last_dot_pos = cleaned.rfind('.')
                last_comma_pos = cleaned.rfind(',')

                if last_comma_pos > last_dot_pos:
                    # Comma is the decimal separator, dots are thousands
                    cleaned = cleaned.replace('.', '').replace(',', '.')
                else:
                    # Dot is the decimal separator, commas are thousands
                    cleaned = cleaned.replace(',', '')
            elif has_comma:
                # Only commas present. Assume last comma is decimal if multiple exist (e.g. 1,234,56 -> 1234.56)
                if cleaned.count(',') > 1:
                    # Multiple commas, assume last is decimal
                    parts = cleaned.rsplit(',', 1)
                    cleaned = parts[0].replace(',', '') + '.' + parts[1]
                else:
                    # Single comma, assume it's decimal
                    cleaned = cleaned.replace(',', '.')
            # elif has_dot: -> If only dots, Python's float() handles it if it's a valid float string
            #                 No cleaning needed beyond removing currency/spaces

            # After cleaning, try to convert to float
            # Use regex to find the number pattern again to be sure
            match = re.search(r'[-+]?\d+(\.\d+)?', cleaned)
            if match:
                numeric_string = match.group()
                return float(numeric_string)
            else:
                logging.warning(f"Could not extract valid number from cleaned string: '{cleaned}' (original: '{price_text}')")

        except Exception as e:
            logging.error(f"Error extracting price from '{price_text}': {str(e)}")

        # Return 0.0 if any step failed
        return 0.0

    @staticmethod
    def format_price(amount: float, currency_format: str, decimal_separator: str = ',', thousands_separator: str = '.') -> str:
        """Format a price according to the specified format and separators"""
        try:
            # Split number into integer and decimal parts
            str_amount = f"{amount:.2f}"
            int_part, dec_part = str_amount.split('.')

            # Add thousands separator
            if len(int_part) > 3:
                # Add thousands separator from right to left
                formatted_int = ""
                for i, digit in enumerate(reversed(int_part)):
                    if i > 0 and i % 3 == 0:
                        formatted_int = thousands_separator + formatted_int
                    formatted_int = digit + formatted_int
                int_part = formatted_int

            # Combine with decimal separator
            formatted_number = f"{int_part}{decimal_separator}{dec_part}"

            # Replace {amount} in the format string with the formatted number
            return currency_format.replace('{amount}', formatted_number)
        except Exception as e:
            logging.error(f"Error formatting price: {str(e)}")
            # Fallback to simple formatting
            return f"{amount:.2f}".replace('.', decimal_separator)

    @staticmethod
    async def collect_price_elements(page) -> List[Dict]:
        """Verzamelt alle elementen met prijzen"""
        prices = []

        # Zoek alleen in relevante tekst elementen
        selectors = [
            'p', 'span', 'div', 'td', 'th', 'label',
            '[class*="price"]', '[class*="prijs"]',
            '[id*="price"]', '[id*="prijs"]',
            '[class*="total"]', '[class*="totaal"]',
            '[class*="amount"]', '[class*="bedrag"]',
            '[class*="cost"]', '[class*="kosten"]',
            '.woocommerce-Price-amount',
            '.product-price',
            '.price-wrapper'
        ]

        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    try:
                        text = await element.text_content()
                        if text and re.search(r'[\d,.]', text):
                            price = PriceExtractor.extract_price_from_text(text)
                            if price > 0:
                                element_id = await element.get_attribute('id')
                                prices.append({
                                    'text': text.strip(),
                                    'price': price,
                                    'selector': selector,
                                    'element_id': element_id
                                })
                    except Exception:
                        continue
            except Exception as e:
                logging.debug(f"Error collecting prices from {selector}: {str(e)}")

        return prices

    @staticmethod
    def find_changed_prices(initial_prices: List[Dict], updated_prices: List[Dict]) -> List[Dict]:
        """Vindt prijzen die zijn veranderd na het invullen van dimensies"""
        changed = []

        # Maak maps voor snelle vergelijking
        initial_by_id = {p['element_id']: p for p in initial_prices if 'element_id' in p}
        initial_by_text = {p['text']: p for p in initial_prices}

        print("\nVergelijken van prijzen:")
        print(f"Initiële prijzen: {len(initial_prices)}")
        print(f"Nieuwe prijzen: {len(updated_prices)}")

        # Check welke prijzen zijn veranderd of nieuw zijn
        for price_info in updated_prices:
            element_id = price_info.get('element_id')
            text = price_info['text']
            price = price_info['price']

            # Probeer eerst te matchen op element ID
            if element_id and element_id in initial_by_id:
                if initial_by_id[element_id]['price'] != price:
                    changed.append({
                        'old_price': initial_by_id[element_id]['price'],
                        'new_price': price,
                        'text': text,
                        'change_reason': 'price_updated'
                    })
            elif text in initial_by_text:
                if initial_by_text[text]['price'] != price:
                    changed.append({
                        'old_price': initial_by_text[text]['price'],
                        'new_price': price,
                        'text': text,
                        'change_reason': 'price_updated'
                    })
            else:
                # Nieuwe prijs element
                changed.append({
                    'old_price': None,
                    'new_price': price,
                    'text': text,
                    'change_reason': 'new_price'
                })

        if not changed:
            print("\nGeen prijsveranderingen gedetecteerd")
            # Als er geen veranderingen zijn, kijk naar nieuwe prijzen die mogelijk relevant zijn
            for price_info in updated_prices:
                if price_info['price'] > 1:  # Filter uit zeer kleine prijzen
                    changed.append({
                        'old_price': None,
                        'new_price': price_info['price'],
                        'text': price_info['text'],
                        'change_reason': 'potential_final_price'
                    })

        return changed
