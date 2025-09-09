import asyncio
import time
import aiohttp
from twocaptcha import TwoCaptcha
from .status_manager import StatusManager


class CaptchaHandler:
    """Handles all captcha-related operations"""

    @staticmethod
    async def handle_captcha(page, step):
        """Handle captcha step"""
        StatusManager.update_status("Handling captcha...", "captcha")

        solving_method = step.get('solving_method', 'Manual')

        try:
            captcha_type = step.get('captcha_type', 'checkbox')
            frame_selector = step.get('frame_selector')
            selector = step.get('selector')

            if solving_method == 'External Service (2Captcha)':
                return await CaptchaHandler._solve_with_external_service(page, step, captcha_type)
            else:
                return await CaptchaHandler._solve_manually(page, step, captcha_type, frame_selector, selector)

            StatusManager.update_status("Captcha handled successfully", "captcha", {"status": "success"})

        except Exception as e:
            if step.get('skip_on_failure', True):
                StatusManager.update_status(f"Captcha failed but continuing: {str(e)}", "warn")
                return False
            StatusManager.update_status(f"Captcha handling failed: {str(e)}", "error")
            raise

    @staticmethod
    async def _solve_with_external_service(page, step, captcha_type):
        """Solve captcha using external service"""
        try:
            # Get site key
            site_key = await CaptchaHandler._extract_recaptcha_key(page)
            if not site_key:
                raise ValueError("Could not extract reCAPTCHA site key")

            # Get settings from database
            from app.database.database import SessionLocal
            from app.core.settings import Settings

            db = SessionLocal()
            try:
                api_key = Settings.get_value(db, '2captcha_api_key', '')
                if not api_key:
                    raise ValueError("2Captcha API key not configured")
            finally:
                db.close()

            # Solve captcha
            solution = await CaptchaHandler._solve_captcha_with_external_service(
                '2Captcha', api_key, site_key, page.url, captcha_type, 120
            )

            if solution:
                await CaptchaHandler._apply_captcha_solution(page, solution, captcha_type)
                return True
            else:
                raise ValueError("Could not solve captcha")

        except Exception as e:
            StatusManager.update_status(f"External captcha service failed: {str(e)}", "error")
            raise

    @staticmethod
    async def _solve_manually(page, step, captcha_type, frame_selector, selector):
        """Handle manual captcha solving"""
        if captcha_type == 'checkbox':
            if frame_selector:
                # Handle iframe captcha
                frame = await page.wait_for_selector(frame_selector)
                frame_content = await frame.content_frame()

                if selector:
                    checkbox = await frame_content.wait_for_selector(selector)
                    await checkbox.click()
                else:
                    # Default reCAPTCHA checkbox
                    checkbox = await frame_content.wait_for_selector('.recaptcha-checkbox-checkmark')
                    await checkbox.click()
            else:
                # Handle direct page captcha
                if selector:
                    checkbox = await page.wait_for_selector(selector)
                    await checkbox.click()

            # Wait for user to complete if manual
            StatusManager.update_status("Waiting for manual captcha completion...", "captcha")
            await asyncio.sleep(30)  # Give user time to complete
            return True

        elif captcha_type == 'image':
            StatusManager.update_status("Image captcha detected - manual intervention required", "captcha")
            await asyncio.sleep(30)
            return True

        else:
            raise ValueError(f"Unsupported captcha type: {captcha_type}")

    @staticmethod
    async def _extract_recaptcha_key(page):
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
                        const match = text.match(/('sitekey'|"sitekey"|sitekey)(\\s*):(\\s*)(['"`])((\\\\.|[^\\\\])*?)\\4/i);
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
                StatusManager.update_status(f"Found reCAPTCHA site key: {site_key[:10]}...", "captcha")
                return site_key

            StatusManager.update_status("Could not find reCAPTCHA site key with JavaScript", "warn")
            return None

        except Exception as e:
            StatusManager.update_status(f"Error extracting reCAPTCHA site key: {str(e)}", "error")
            return None

    @staticmethod
    async def _solve_captcha_with_external_service(service_name, api_key, site_key, page_url, captcha_type, max_wait_time):
        """Solve captcha using an external service"""
        try:
            import aiohttp

            start_time = time.time()
            StatusManager.update_status(f"Starting captcha solution request with {service_name}", "captcha")

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
                raise ValueError(f"Unsupported captcha service: {service_name}")

            # Prepare the request data
            task_data = None
            task_id = None

            # Using aiohttp for non-blocking HTTP requests
            async with aiohttp.ClientSession() as session:
                if service_name == '2Captcha':
                    # Submit task to 2Captcha
                    submit_data = {
                        'key': api_key,
                        'method': 'userrecaptcha',
                        'googlekey': site_key,
                        'pageurl': page_url,
                        'json': 1
                    }

                    async with session.post(service_endpoints[service_name]['submit'], data=submit_data) as response:
                        result = await response.json()
                        if result.get('status') != 1:
                            raise ValueError(f"Failed to submit captcha: {result.get('error_text', 'Unknown error')}")
                        task_id = result.get('request')

                    StatusManager.update_status(f"Captcha submitted to {service_name}, task ID: {task_id}", "captcha")

                    # Wait for solution
                    while time.time() - start_time < max_wait_time:
                        await asyncio.sleep(5)  # Check every 5 seconds

                        retrieve_data = {
                            'key': api_key,
                            'action': 'get',
                            'id': task_id,
                            'json': 1
                        }

                        async with session.get(service_endpoints[service_name]['retrieve'], params=retrieve_data) as response:
                            result = await response.json()

                            if result.get('status') == 1:
                                solution = result.get('request')
                                StatusManager.update_status(f"Captcha solved successfully by {service_name}", "captcha")
                                return solution
                            elif result.get('error_text') == 'CAPCHA_NOT_READY':
                                continue  # Keep waiting
                            else:
                                raise ValueError(f"Captcha solving failed: {result.get('error_text', 'Unknown error')}")

                    raise ValueError(f"Captcha solving timed out after {max_wait_time} seconds")

        except Exception as e:
            StatusManager.update_status(f"Error using external captcha service: {str(e)}", "error")
            return None

    @staticmethod
    async def _apply_captcha_solution(page, solution, captcha_type):
        """Apply the captcha solution to the page"""
        if captcha_type == 'recaptcha_v2':
            try:
                # Inject the solution into the page
                await page.evaluate(f"""
                    () => {{
                        // Find the reCAPTCHA callback function
                        if (window.grecaptcha && window.grecaptcha.getResponse) {{
                            // Set the response
                            document.getElementById('g-recaptcha-response').innerHTML = '{solution}';
                            document.getElementById('g-recaptcha-response').style.display = 'block';

                            // Trigger the callback if it exists
                            if (window.captchaCallback) {{
                                window.captchaCallback('{solution}');
                            }}

                            // Also try to find and trigger any form submission
                            const forms = document.querySelectorAll('form');
                            for (const form of forms) {{
                                const recaptchaResponse = form.querySelector('[name="g-recaptcha-response"]');
                                if (recaptchaResponse) {{
                                    recaptchaResponse.value = '{solution}';
                                    // Trigger change event
                                    recaptchaResponse.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                    break;
                                }}
                            }}
                        }}
                    }}
                """)
                StatusManager.update_status("Captcha solution applied to page", "captcha")
            except Exception as e:
                StatusManager.update_status(f"Error applying captcha solution: {str(e)}", "error")
                raise
        else:
            StatusManager.update_status(f"Unsupported captcha type: {captcha_type}", "error")
            raise ValueError(f"Unsupported captcha type: {captcha_type}")
