from playwright.async_api import async_playwright, Page
from app.core.config import HEADLESS
import random
import asyncio


class BrowserManager:
    """Handles browser setup and management operations"""

    @staticmethod
    async def setup_browser(p):
        """Set up browser with anti-detection settings - main entry point for browser setup"""
        # Launch browser with anti-detection settings
        browser = await p.chromium.launch(
            headless=HEADLESS,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-application-cache',
                '--disable-cache',
                '--disable-offline-load-stale-cache',
                '--disk-cache-size=0',
                f'--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            ]
        )

        # Create context with more realistic browser settings and disabled storage
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            locale='nl-NL',
            timezone_id='Europe/Amsterdam',
            geolocation={'latitude': 52.3676, 'longitude': 4.9041},
            permissions=['geolocation'],
            color_scheme='light',
            has_touch=True,
            is_mobile=False,
            device_scale_factor=2,
            java_script_enabled=True,
            storage_state={'cookies': [], 'origins': []},
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

        # Create page and set timeout
        page = await context.new_page()
        page.set_default_timeout(120000)  # 1:30 minute timeout

        return browser, context, page

    @staticmethod
    async def create_browser_context():
        """Create and configure a browser context with anti-detection settings"""
        p = await async_playwright().start()

        # Launch browser with anti-detection settings
        browser = await p.chromium.launch(
            headless=HEADLESS,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-application-cache',
                '--disable-cache',
                '--disable-offline-load-stale-cache',
                '--disk-cache-size=0',
                f'--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            ]
        )

        # Create context with more realistic browser settings and disabled storage
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            locale='nl-NL',
            timezone_id='Europe/Amsterdam',
            geolocation={'latitude': 52.3676, 'longitude': 4.9041},
            permissions=['geolocation'],
            color_scheme='light',
            has_touch=True,
            is_mobile=False,
            device_scale_factor=2,
            java_script_enabled=True,
            storage_state={'cookies': [], 'origins': []},
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

        return p, browser, context

    @staticmethod
    async def create_page(context):
        """Create page from context and set timeout"""
        page = await context.new_page()
        page.set_default_timeout(120000)  # 1:30 minute timeout
        return page

    @staticmethod
    async def add_human_like_behavior(page):
        """Add human-like behavior like random mouse movements"""
        try:
            # Get viewport dimensions
            viewport = page.viewport_size
            max_x = viewport['width']
            max_y = viewport['height']

            # Random mouse movement
            x = random.randint(100, max_x - 100)
            y = random.randint(100, max_y - 100)

            await page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.1, 0.3))

        except Exception as e:
            from .status_manager import StatusManager
            StatusManager.update_status(f"Could not add human-like behavior: {str(e)}", "warn")

    @staticmethod
    async def highlight_element(page, elements_or_element):
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
                from .status_manager import StatusManager
                StatusManager.update_status(f"Could not highlight element: {str(e)}", "warn")
                continue

    @staticmethod
    async def find_nearest_element(page, search_terms: list, element_type: str = 'text'):
        """
        Zoekt naar specifieke termen en vindt het dichtstbijzijnde relevante element.
        """
        try:
            # Verzamel alle tekst elementen
            elements = await page.query_selector_all('*')
            matches = []

            for element in elements:
                try:
                    text = await element.text_content()
                    if not text:
                        continue

                    text = text.strip().lower()
                    for term in search_terms:
                        if term.lower() in text:
                            # Zoek naar prijselementen in de buurt
                            nearby_price = await element.evaluate("""
                                (el) => {
                                    const searchRadius = 200; // pixels
                                    const rect = el.getBoundingClientRect();
                                    const centerX = rect.left + rect.width / 2;
                                    const centerY = rect.top + rect.height / 2;

                                    // Zoek alle elementen met cijfers
                                    const allElements = document.querySelectorAll('*');
                                    let closestPrice = null;
                                    let minDistance = Infinity;

                                    for (const candidate of allElements) {
                                        const candidateText = candidate.textContent || '';
                                        const priceMatch = candidateText.match(/[\d,.]+(€|EUR|$|\s|$)/);

                                        if (priceMatch) {
                                            const candidateRect = candidate.getBoundingClientRect();
                                            const candX = candidateRect.left + candidateRect.width / 2;
                                            const candY = candidateRect.top + candidateRect.height / 2;
                                            const distance = Math.sqrt(Math.pow(centerX - candX, 2) + Math.pow(centerY - candY, 2));

                                            if (distance < searchRadius && distance < minDistance) {
                                                minDistance = distance;
                                                closestPrice = {
                                                    text: candidateText.trim(),
                                                    distance: distance,
                                                    element: candidate
                                                };
                                            }
                                        }
                                    }

                                    return closestPrice;
                                }
                            """)

                            if nearby_price:
                                matches.append({
                                    'term': term,
                                    'element_text': text,
                                    'price_info': nearby_price,
                                    'distance': nearby_price['distance']
                                })

                except Exception:
                    continue

            # Sorteer matches op afstand (dichtsbij eerst)
            matches.sort(key=lambda x: x['distance'])

            if matches:
                return matches[0]['price_info']

            return None

        except Exception as e:
            print(f"Error bij zoeken naar element: {str(e)}")
            return None

    @staticmethod
    async def find_nearest_element(page, search_terms: list, element_type: str = 'text'):
        """
        Zoekt naar specifieke termen en vindt het dichtstbijzijnde relevante element.
        """
        try:
            # Verzamel alle tekst elementen
            elements = await page.query_selector_all('*')
            matches = []

            for element in elements:
                try:
                    text = await element.text_content()
                    if not text:
                        continue

                    text = text.strip().lower()
                    for term in search_terms:
                        if term.lower() in text:
                            # Zoek naar prijselementen in de buurt
                            nearby_price = await element.evaluate("""
                                (el) => {
                                    const searchRadius = 200; // pixels
                                    const rect = el.getBoundingClientRect();
                                    const centerX = rect.left + rect.width / 2;
                                    const centerY = rect.top + rect.height / 2;

                                    // Zoek alle elementen met cijfers
                                    const allElements = document.querySelectorAll('*');
                                    let closestPrice = null;
                                    let minDistance = Infinity;

                                    for (const candidate of allElements) {
                                        const candidateText = candidate.textContent || '';
                                        const priceMatch = candidateText.match(/[\d,.]+(€|EUR|$|\s|$)/);

                                        if (priceMatch) {
                                            const candidateRect = candidate.getBoundingClientRect();
                                            const candX = candidateRect.left + candidateRect.width / 2;
                                            const candY = candidateRect.top + candidateRect.height / 2;
                                            const distance = Math.sqrt(Math.pow(centerX - candX, 2) + Math.pow(centerY - candY, 2));

                                            if (distance < searchRadius && distance < minDistance) {
                                                minDistance = distance;
                                                closestPrice = {
                                                    text: candidateText.trim(),
                                                    distance: distance,
                                                    element: candidate
                                                };
                                            }
                                        }
                                    }

                                    return closestPrice;
                                }
                            """)

                            if nearby_price:
                                matches.append({
                                    'term': term,
                                    'element_text': text,
                                    'price_info': nearby_price,
                                    'distance': nearby_price['distance']
                                })

                except Exception:
                    continue

            # Sorteer matches op afstand (dichtsbij eerst)
            matches.sort(key=lambda x: x['distance'])

            if matches:
                return matches[0]['price_info']

            return None

        except Exception as e:
            print(f"Error bij zoeken naar element: {str(e)}")
            return None
