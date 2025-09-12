def _convert_dimensions(self, dimensions: Dict[str, float], units: Dict[str, str]) -> Dict[str, float]:
    """Convert dimensions to the units required by the domain"""
    converted = {}

    # Handle thickness separately
    if 'thickness' in dimensions:
        if units.get('thickness') == 'cm':
            converted['thickness'] = dimensions['thickness'] / 10  # mm to cm
        else:
            converted['thickness'] = dimensions['thickness']  # keep as mm

    # Handle length and width
    dimension_unit = units.get('dimensions', 'mm')
    for field in ['length', 'width']:
        if field in dimensions:
            if dimension_unit == 'cm':
                converted[field] = dimensions[field] / 10  # mm to cm
            else:
                converted[field] = dimensions[field]  # keep as mm

    return converted


async def _collect_price_elements(self, page) -> List[Dict]:
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
                    if not text:
                        continue

                    text = text.lower().strip()

                    # Zoek naar prijzen met verschillende patronen
                    price_patterns = [
                        r'€\s*(\d+(?:[.,]\d{2})?)',  # €20,00
                        r'(\d+(?:[.,]\d{2})?)\s*€',  # 20,00€
                        r'eur\s*(\d+(?:[.,]\d{2})?)',  # EUR 20,00
                        r'(\d+(?:[.,]\d{2})?)\s*eur'   # 20,00 EUR
                    ]

                    for pattern in price_patterns:
                        price_matches = re.findall(pattern, text)
                        if price_matches:
                            # Neem de laatste match (vaak de meest relevante bij meerdere prijzen)
                            price_str = price_matches[-1]
                            price = float(price_str.replace(',', '.'))

                            # Valideer dat de prijs realistisch is
                            if 0.01 <= price <= 10000.0:  # Verruim de prijsrange
                                # Check BTW indicatie
                                is_incl = any(term in text for term in ['incl', 'inclusief', 'inc.', 'incl.'])

                                # Genereer een unieke identifier voor het element
                                element_id = await element.evaluate("""el => {
                                    if (el.id) return el.id;
                                    if (el.className) return el.className;
                                    return el.tagName + '_' + (el.textContent || '').substring(0, 20);
                                }""")

                                prices.append({
                                    'element': element,
                                    'element_id': element_id,
                                    'text': text,
                                    'price': price,
                                    'is_incl': is_incl,
                                    'pattern_used': pattern
                                })
                                print(f"Gevonden prijs in element {element_id}: €{price:.2f} ({'incl' if is_incl else 'excl'} BTW)")
                                break  # Stop na eerste geldige prijs in dit element

                except Exception as e:
                    print(f"Error bij element verwerking: {str(e)}")
                    continue
        except Exception as e:
            print(f"Error bij selector {selector}: {str(e)}")
            continue

    return prices


def _find_changed_prices(self, initial_prices: List[Dict], updated_prices: List[Dict]) -> List[Dict]:
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
            initial_price = initial_by_id[element_id]['price']
            if abs(initial_price - price) > 0.01:  # Gebruik kleine marge voor float vergelijking
                print(f"\nPrijsverandering gedetecteerd in element {element_id}:")
                print(f"- Oude prijs: €{initial_price:.2f}")
                print(f"- Nieuwe prijs: €{price:.2f}")
                changed.append(price_info)
        # Als geen ID match, probeer op tekst
        elif text in initial_by_text:
            initial_price = initial_by_text[text]['price']
            if abs(initial_price - price) > 0.01:
                print(f"\nPrijsverandering gedetecteerd in tekst '{text}':")
                print(f"- Oude prijs: €{initial_price:.2f}")
                print(f"- Nieuwe prijs: €{price:.2f}")
                changed.append(price_info)
        # Volledig nieuwe prijs
        else:
            # Valideer dat het echt een prijs is
            if any(indicator in text.lower() for indicator in ['€', 'eur', 'prijs', 'price', 'total', 'bedrag']):
                print(f"\nNieuwe prijs gevonden: €{price:.2f}")
                print(f"In element: {element_id if element_id else text}")
                changed.append(price_info)

    if not changed:
        print("\nGeen prijsveranderingen gedetecteerd")
        # Als er geen veranderingen zijn, kijk naar nieuwe prijzen die mogelijk relevant zijn
        for price_info in updated_prices:
            if 5.0 <= price_info['price'] <= 500.0:  # Typische m² prijsrange
                if any(term in price_info['text'].lower() for term in ['totaal', 'total', 'prijs', 'price']):
                    print(f"\nMogelijk relevante prijs gevonden: €{price_info['price']:.2f}")
                    print(f"In element: {price_info.get('element_id', price_info['text'])}")
                    changed.append(price_info)

    return changed


async def _extract_recaptcha_key(self, page):
    """Extract reCAPTCHA site key from the page"""
    try:
        # Try multiple methods to extract the site key
        site_key = await page.evaluate("""
            () => {
                // Method 1: Look for g-recaptcha elements with data-sitekey
                const recaptchaElements = document.querySelectorAll('.g-recaptcha[data-sitekey], [class*=recaptcha][data-sitekey]');
                if (recaptchaElements.length > 0) {
                    return recaptchaElements[0].getAttribute('data-sitekey');
                }

                // Method 2: Look for grecaptcha in window object and try to extract key
                if (window.grecaptcha && window.grecaptcha.render) {
                    // This is more complex as it's in the rendered parameters
                    const recaptchaDiv = document.querySelector('.g-recaptcha');
                    if (recaptchaDiv) {
                        return recaptchaDiv.getAttribute('data-sitekey');
                    }
                }

                // Method 3: Look in the page source
                const scripts = document.querySelectorAll('script');
                for (const script of scripts) {
                    const text = script.textContent || script.innerText || '';
                    const match = text.match(/('sitekey'|"sitekey"|sitekey)(\s*):(\s*)(['"`])((\\.|[^\\])*?)\4/i);
                    if (match && match[5]) {
                        return match[5];
                    }
                }

                // Method 4: Search in script src attributes
                for (const script of scripts) {
                    const src = script.getAttribute('src') || '';
                    if (src.includes('recaptcha')) {
                        const match = src.match(/[?&]k=([^&]+)/i);
                        if (match && match[1]) {
                            return match[1];
                        }
                    }
                }

                // Method 5: Look for recaptcha iframe and extract from src
                const recaptchaIframes = document.querySelectorAll('iframe[src*="recaptcha"]');
                for (const iframe of recaptchaIframes) {
                    const src = iframe.getAttribute('src') || '';
                    const match = src.match(/[?&]k=([^&]+)/i);
                    if (match && match[1]) {
                        return match[1];
                    }
                }

                return null;
            }
        """)

        if site_key:
            self._update_status(f"Found reCAPTCHA site key: {site_key}", "captcha")
            return site_key

        self._update_status("Could not find reCAPTCHA site key with JavaScript", "warn")
        return None

    except Exception as e:
        self._update_status(f"Error extracting reCAPTCHA site key: {str(e)}", "error")
        return None


async def _solve_captcha_with_external_service(self, service_name, api_key, site_key, page_url, captcha_type, max_wait_time):
    """Solve captcha using an external service"""
    try:
        import aiohttp
        import json
        import time

        start_time = time.time()
        self._update_status(f"Starting captcha solution request with {service_name}", "captcha")

        # API endpoints for different services
        service_endpoints = {
            '2Captcha': {
                'submit': 'https://2captcha.com/in.php',
                'retrieve': 'https://2captcha.com/res.php'
            },
            'Anti-Captcha': {
                'submit': 'https://api.anti-captcha.com/createTask',
                'retrieve': 'https://api.anti-captcha.com/getTaskResult'
            },
            'CapMonster': {
                'submit': 'https://api.capmonster.cloud/createTask',
                'retrieve': 'https://api.capmonster.cloud/getTaskResult'
            }
        }

        if service_name not in service_endpoints:
            self._update_status(f"Unknown captcha service: {service_name}", "error")
            return None

        # Prepare the request data
        task_data = None
        task_id = None

        # Using aiohttp for non-blocking HTTP requests
        async with aiohttp.ClientSession() as session:
            # Submit the captcha task
            if service_name == '2Captcha':
                # 2Captcha API
                params = {
                    'key': api_key,
                    'method': 'userrecaptcha',
                    'googlekey': site_key,
                    'pageurl': page_url,
                    'json': 1
                }
                async with session.get(service_endpoints[service_name]['submit'], params=params) as response:
                    result = await response.json()
                    if result.get('status') == 1:
                        task_id = result.get('request')
                    else:
                        self._update_status(f"Error from {service_name}: {result.get('error_text', 'Unknown error')}", "error")
                        return None
            else:
                # Anti-Captcha/CapMonster API
                data = {
                    'clientKey': api_key,
                    'task': {
                        'type': 'NoCaptchaTaskProxyless',
                        'websiteURL': page_url,
                        'websiteKey': site_key
                    }
                }
                async with session.post(service_endpoints[service_name]['submit'], json=data) as response:
                    result = await response.json()
                    if service_name == 'Anti-Captcha':
                        if result.get('errorId') == 0:
                            task_id = result.get('taskId')
                        else:
                            self._update_status(f"Error from {service_name}: {result.get('errorDescription', 'Unknown error')}", "error")
                            return None
                    else:  # CapMonster
                        if result.get('errorId') == 0:
                            task_id = result.get('taskId')
                        else:
                            self._update_status(f"Error from {service_name}: {result.get('errorCode', 'Unknown error')}", "error")
                            return None

            # If we have a task ID, poll for results
            if task_id:
                self._update_status(f"Captcha task submitted, waiting for solution (task ID: {task_id})", "captcha")
                # Poll with increasing delays
                wait_time = 5  # Start with 5 seconds

                while time.time() - start_time < max_wait_time:
                    # Wait before polling
                    await asyncio.sleep(wait_time)

                    # Adjust wait time for next poll
                    wait_time = min(wait_time * 1.5, 15)  # Increase wait time but cap at 15 seconds

                    self._update_status(f"Checking captcha solution status (elapsed: {int(time.time() - start_time)}s)", "captcha")

                    # Poll for results
                    if service_name == '2Captcha':
                        params = {
                            'key': api_key,
                            'action': 'get',
                            'id': task_id,
                            'json': 1
                        }
                        async with session.get(service_endpoints[service_name]['retrieve'], params=params) as response:
                            result = await response.json()
                            if result.get('status') == 1:
                                # We have a solution
                                solution = result.get('request')
                                self._update_status(f"Captcha solved successfully in {int(time.time() - start_time)}s", "captcha", {"status": "success"})
                                return solution
                            elif result.get('request') != 'CAPCHA_NOT_READY':
                                # Some error occurred
                                self._update_status(f"Error from {service_name}: {result.get('request', 'Unknown error')}", "error")
                                return None
                    else:
                        # Anti-Captcha/CapMonster API
                        data = {
                            'clientKey': api_key,
                            'taskId': task_id
                        }
                        async with session.post(service_endpoints[service_name]['retrieve'], json=data) as response:
                            result = await response.json()
                            if result.get('errorId') == 0 and result.get('status') == 'ready':
                                # We have a solution
                                solution = result.get('solution', {}).get('gRecaptchaResponse')
                                self._update_status(f"Captcha solved successfully in {int(time.time() - start_time)}s", "captcha", {"status": "success"})
                                return solution
                            elif result.get('errorId') != 0:
                                # Some error occurred
                                error_msg = result.get('errorDescription', 'Unknown error')
                                if service_name == 'CapMonster':
                                    error_msg = result.get('errorCode', 'Unknown error')
                                self._update_status(f"Error from {service_name}: {error_msg}", "error")
                                return None

                # If we get here, we've timed out
                self._update_status(f"Timed out waiting for captcha solution after {max_wait_time}s", "error")
                return None
            else:
                self._update_status("Failed to submit captcha task", "error")
                return None

    except Exception as e:
        self._update_status(f"Error using external captcha service: {str(e)}", "error")
        return None


async def _apply_captcha_solution(self, page, solution, captcha_type):
    """Apply the captcha solution to the page"""
    if captcha_type == 'recaptcha_v2':
        try:
            # Set the g-recaptcha-response textarea
            await page.evaluate(f"""
                (solution) => {{
                    // Create a textarea or find existing one if the challenge is active
                    const existing = document.querySelector('textarea#g-recaptcha-response');

                    if (existing) {{
                        // If the textarea already exists, just set its value
                        existing.value = solution;
                    }} else {{
                        // Create a new textarea if needed
                        const textarea = document.createElement('textarea');
                        textarea.id = 'g-recaptcha-response';
                        textarea.name = 'g-recaptcha-response';
                        textarea.className = 'g-recaptcha-response';
                        textarea.style.display = 'none';
                        textarea.value = solution;
                        document.body.appendChild(textarea);
                    }}

                    // Trigger events to make the site recognize the solved captcha
                    document.dispatchEvent(new Event('captcha-solution'));

                    // Try to trigger success callbacks
                    if (window.___grecaptcha_cfg && window.___grecaptcha_cfg.clients) {{
                        const clients = Object.values(window.___grecaptcha_cfg.clients);
                        for (const client of clients) {{
                            try {{
                                // Different versions of reCAPTCHA have different structures
                                // Try to find and call the callback
                                if (client && client.iY) {{
                                    const callback = client.iY.callback;
                                    if (typeof callback === 'function') {{
                                        callback(solution);
                                    }}
                                }}
                            }} catch (e) {{
                                console.error('Error triggering reCAPTCHA callback:', e);
                            }}
                        }}
                    }}

                    return true;
                }}
            """, solution)

            # Wait a moment for any callbacks to execute
            await asyncio.sleep(2.0)

            # Try to find and click any submit buttons that might have been enabled
            await page.evaluate("""
                () => {
                    // Look for newly enabled submit buttons
                    const buttons = document.querySelectorAll('button:not([disabled]), input[type="submit"]:not([disabled])');
                    for (const button of buttons) {
                        // Check if it's visible
                        const style = window.getComputedStyle(button);
                        if (style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0') {
                            // Might be a submit button that was enabled after solving captcha
                            // Don't click automatically, as it might submit a form before all fields are filled
                            // Just return that we found an enabled button
                            return true;
                        }
                    }
                    return false;
                }
            """)

            return True
        except Exception as e:
            self._update_status(f"Error applying captcha solution: {str(e)}", "error")
            return False
    else:
        self._update_status(f"Unsupported captcha type: {captcha_type}", "error")
        raise ValueError(f"Unsupported captcha type: {captcha_type}")
