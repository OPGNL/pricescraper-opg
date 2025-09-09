import asyncio
import json
import time
from urllib.parse import urljoin
from .status_manager import StatusManager
from .captcha_handler import CaptchaHandler


class StepHandlers:
    """Handles different types of steps in the price calculation workflow"""

    @staticmethod
    async def handle_navigate(page, step):
        """Handle navigation step"""
        url = step['url']

        # If URL is relative, make it absolute
        if not url.startswith(('http://', 'https://')):
            current_url = page.url
            url = urljoin(current_url, url)

        StatusManager.update_status(f"Navigating to: {url}", "navigate")

        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
            await asyncio.sleep(step.get('delay', 2))

            StatusManager.update_status("Navigation completed", "navigate", {"url": url})
            return True
        except Exception as e:
            if step.get('skip_on_failure', True):
                StatusManager.update_status(f"Navigation failed but continuing: {str(e)}", "warn")
                return False
            StatusManager.update_status(f"Navigation failed: {str(e)}", "error")
            raise

    @staticmethod
    async def handle_wait(page, step):
        """Handle wait step"""
        duration = step.get('duration', 1)
        reason = step.get('reason', 'General delay')

        StatusManager.update_status(f"Waiting {duration}s: {reason}", "wait")
        await asyncio.sleep(duration)

        StatusManager.update_status("Wait completed", "wait", {"duration": duration})
        return True

    @staticmethod
    async def handle_click(page, step):
        """Handle click step"""
        selector = step['selector']
        StatusManager.update_status(f"Clicking element: {selector}", "click")

        try:
            # Wait for element to be available
            await page.wait_for_selector(selector, timeout=10000)

            # Additional wait if specified
            if step.get('wait_before_click'):
                await asyncio.sleep(step['wait_before_click'])

            # Handle different click methods
            click_method = step.get('method', 'click')
            if click_method == 'force':
                await page.click(selector, force=True)
            elif click_method == 'js':
                await page.evaluate(f"document.querySelector('{selector}').click()")
            else:
                await page.click(selector)

            # Wait after click if specified
            if step.get('wait_after_click'):
                await asyncio.sleep(step['wait_after_click'])

            StatusManager.update_status("Click completed", "click", {"selector": selector})
            return True

        except Exception as e:
            if step.get('skip_on_failure', True):
                StatusManager.update_status(f"Click failed but continuing: {str(e)}", "warn")
                return False
            StatusManager.update_status(f"Click failed: {str(e)}", "error")
            raise

    @staticmethod
    async def handle_input(page, step):
        """Handle input step"""
        selector = step['selector']
        value = step['value']
        StatusManager.update_status(f"Filling input: {selector} with value: {value}", "input")

        try:
            # Wait for element
            await page.wait_for_selector(selector, timeout=10000)

            # Clear existing content if specified
            if step.get('clear_first', True):
                await page.fill(selector, '')

            # Fill the input
            input_method = step.get('method', 'fill')
            if input_method == 'type':
                await page.type(selector, value, delay=step.get('typing_delay', 100))
            else:
                await page.fill(selector, value)

            # Trigger events if specified
            if step.get('trigger_change'):
                await page.dispatch_event(selector, 'change')
            if step.get('trigger_blur'):
                await page.dispatch_event(selector, 'blur')

            StatusManager.update_status("Input completed", "input", {"selector": selector, "value": value})
            return True

        except Exception as e:
            if step.get('skip_on_failure', True):
                StatusManager.update_status(f"Input failed but continuing: {str(e)}", "warn")
                return False
            StatusManager.update_status(f"Input failed: {str(e)}", "error")
            raise

    @staticmethod
    async def handle_select(page, step):
        """Handle select dropdown step"""
        selector = step['selector']
        value = step['value']
        StatusManager.update_status(f"Selecting option: {value} in {selector}", "select")

        try:
            # Wait for element
            await page.wait_for_selector(selector, timeout=10000)

            # Select by different methods
            select_method = step.get('method', 'value')
            if select_method == 'value':
                await page.select_option(selector, value=value)
            elif select_method == 'label':
                await page.select_option(selector, label=value)
            elif select_method == 'index':
                await page.select_option(selector, index=int(value))

            StatusManager.update_status("Selection completed", "select", {"selector": selector, "value": value})
            return True

        except Exception as e:
            if step.get('skip_on_failure', True):
                StatusManager.update_status(f"Selection failed but continuing: {str(e)}", "warn")
                return False
            StatusManager.update_status(f"Selection failed: {str(e)}", "error")
            raise

    @staticmethod
    async def handle_wait_for_element(page, step):
        """Handle wait for element step"""
        selector = step['selector']
        timeout = step.get('timeout', 10000)
        state = step.get('state', 'visible')

        StatusManager.update_status(f"Waiting for element: {selector} (state: {state})", "wait_element")

        try:
            if state == 'visible':
                await page.wait_for_selector(selector, state='visible', timeout=timeout)
            elif state == 'hidden':
                await page.wait_for_selector(selector, state='hidden', timeout=timeout)
            elif state == 'attached':
                await page.wait_for_selector(selector, state='attached', timeout=timeout)
            elif state == 'detached':
                await page.wait_for_selector(selector, state='detached', timeout=timeout)

            StatusManager.update_status("Element wait completed", "wait_element", {"selector": selector})
            return True

        except Exception as e:
            if step.get('skip_on_failure', True):
                StatusManager.update_status(f"Element wait failed but continuing: {str(e)}", "warn")
                return False
            StatusManager.update_status(f"Element wait failed: {str(e)}", "error")
            raise

    @staticmethod
    async def handle_wait_for_url(page, step):
        """Handle wait for URL step"""
        pattern = step['pattern']
        timeout = step.get('timeout', 10000)

        StatusManager.update_status(f"Waiting for URL pattern: {pattern}", "wait_url")

        try:
            await page.wait_for_url(pattern, timeout=timeout)
            StatusManager.update_status("URL wait completed", "wait_url", {"pattern": pattern})
            return True

        except Exception as e:
            if step.get('skip_on_failure', True):
                StatusManager.update_status(f"URL wait failed but continuing: {str(e)}", "warn")
                return False
            StatusManager.update_status(f"URL wait failed: {str(e)}", "error")
            raise

    @staticmethod
    async def handle_execute_js(page, step):
        """Handle JavaScript execution step"""
        script = step['script']
        StatusManager.update_status("Executing JavaScript", "js")

        try:
            result = await page.evaluate(script)
            StatusManager.update_status("JavaScript executed", "js", {"result": str(result)[:100]})
            return result

        except Exception as e:
            if step.get('skip_on_failure', True):
                StatusManager.update_status(f"JavaScript failed but continuing: {str(e)}", "warn")
                return False
            StatusManager.update_status(f"JavaScript execution failed: {str(e)}", "error")
            raise

    @staticmethod
    async def handle_extract_data(page, step):
        """Handle data extraction step"""
        selector = step.get('selector')
        attribute = step.get('attribute', 'textContent')
        variable_name = step.get('variable_name', 'extracted_data')

        StatusManager.update_status(f"Extracting data from: {selector}", "extract")

        try:
            if selector:
                # Extract from specific element
                element = await page.wait_for_selector(selector, timeout=5000)
                if attribute == 'textContent':
                    data = await element.text_content()
                elif attribute == 'innerText':
                    data = await element.inner_text()
                elif attribute == 'innerHTML':
                    data = await element.inner_html()
                else:
                    data = await element.get_attribute(attribute)
            else:
                # Extract using JavaScript
                script = step.get('script', 'document.body.textContent')
                data = await page.evaluate(script)

            StatusManager.update_status("Data extracted", "extract", {
                "variable": variable_name,
                "data": str(data)[:100]
            })
            return {variable_name: data}

        except Exception as e:
            if step.get('skip_on_failure', True):
                StatusManager.update_status(f"Data extraction failed but continuing: {str(e)}", "warn")
                return {}
            StatusManager.update_status(f"Data extraction failed: {str(e)}", "error")
            raise

    @staticmethod
    async def handle_conditional(page, step):
        """Handle conditional step"""
        condition_type = step.get('condition_type', 'element_exists')
        StatusManager.update_status(f"Checking condition: {condition_type}", "conditional")

        try:
            condition_met = False

            if condition_type == 'element_exists':
                selector = step['selector']
                try:
                    await page.wait_for_selector(selector, timeout=step.get('timeout', 5000))
                    condition_met = True
                except:
                    condition_met = False

            elif condition_type == 'url_contains':
                pattern = step['pattern']
                current_url = page.url
                condition_met = pattern in current_url

            elif condition_type == 'text_contains':
                text = step['text']
                page_content = await page.content()
                condition_met = text in page_content

            elif condition_type == 'javascript':
                script = step['script']
                condition_met = bool(await page.evaluate(script))

            # Execute appropriate steps based on condition
            if condition_met:
                StatusManager.update_status("Condition met - executing 'if' steps", "conditional")
                if_steps = step.get('if_steps', [])
                for if_step in if_steps:
                    await StepHandlers.execute_step(page, if_step)
            else:
                StatusManager.update_status("Condition not met - executing 'else' steps", "conditional")
                else_steps = step.get('else_steps', [])
                for else_step in else_steps:
                    await StepHandlers.execute_step(page, else_step)

            return condition_met

        except Exception as e:
            if step.get('skip_on_failure', True):
                StatusManager.update_status(f"Conditional failed but continuing: {str(e)}", "warn")
                return False
            StatusManager.update_status(f"Conditional execution failed: {str(e)}", "error")
            raise

    @staticmethod
    async def handle_loop(page, step):
        """Handle loop step"""
        loop_type = step.get('loop_type', 'count')
        StatusManager.update_status(f"Starting loop: {loop_type}", "loop")

        try:
            if loop_type == 'count':
                iterations = step.get('iterations', 1)
                for i in range(iterations):
                    StatusManager.update_status(f"Loop iteration {i+1}/{iterations}", "loop")
                    for loop_step in step.get('steps', []):
                        await StepHandlers.execute_step(page, loop_step)

            elif loop_type == 'while_element_exists':
                selector = step['selector']
                max_iterations = step.get('max_iterations', 10)
                iteration = 0

                while iteration < max_iterations:
                    try:
                        await page.wait_for_selector(selector, timeout=1000)
                        StatusManager.update_status(f"Loop iteration {iteration+1}", "loop")
                        for loop_step in step.get('steps', []):
                            await StepHandlers.execute_step(page, loop_step)
                        iteration += 1
                    except:
                        break  # Element not found, exit loop

            StatusManager.update_status("Loop completed", "loop")
            return True

        except Exception as e:
            if step.get('skip_on_failure', True):
                StatusManager.update_status(f"Loop failed but continuing: {str(e)}", "warn")
                return False
            StatusManager.update_status(f"Loop execution failed: {str(e)}", "error")
            raise

    @staticmethod
    async def handle_captcha(page, step):
        """Handle captcha step - delegates to CaptchaHandler"""
        return await CaptchaHandler.handle_captcha(page, step)

    @staticmethod
    async def handle_blur(page, step):
        """Handle a blur step by either using the selector from the step or the last interacted element"""
        selector = step.get('selector')

        try:
            if selector:
                # If a selector is provided, use it
                StatusManager.update_status(f"Triggering blur on {selector}", "blur", {"selector": selector})
                element = await page.wait_for_selector(selector, timeout=5000)
                if element:
                    await element.evaluate('(el) => { el.blur(); }')
                    StatusManager.update_status(f"Blur completed on {selector}", "blur", {"selector": selector, "status": "success"})
            else:
                # If no selector is provided, try to blur the active element
                StatusManager.update_status("Triggering blur on active element", "blur")
                await page.evaluate('() => { document.activeElement?.blur(); }')
                StatusManager.update_status("Blur completed on active element", "blur", {"status": "success"})
            return True
        except Exception as e:
            if step.get('skip_on_failure', True):
                StatusManager.update_status(f"Blur failed but continuing: {str(e)}", "warn")
                return False
            StatusManager.update_status(f"Blur failed: {str(e)}", "error")
            raise

    @staticmethod
    async def handle_modify(page, step):
        """Handle a modify_element step that runs JavaScript to modify an element"""
        selector = step['selector']
        script = step.get('script', '')
        add_class = step.get('add_class', '')
        add_attribute = step.get('add_attribute', {})
        value = step.get('value', '')

        StatusManager.update_status(f"Modifying element {selector}", "modify", {"selector": selector, "add_class": add_class})

        try:
            element = await page.wait_for_selector(selector, timeout=5000)
            if not element:
                raise ValueError(f"Element not found: {selector}")

            # Add class if specified
            if add_class:
                await element.evaluate(f'''(el) => {{
                    el.classList.add('{add_class}');
                }}''')
                StatusManager.update_status(f"Added class '{add_class}' to {selector}", "modify", {"status": "success"})

            # Set value if specified
            if value:
                await element.evaluate(f'''(el) => {{
                    if (el.tagName.toLowerCase() === 'input' || el.tagName.toLowerCase() === 'textarea') {{
                        el.value = '{value}';
                    }} else {{
                        el.textContent = '{value}';
                    }}
                }}''')
                StatusManager.update_status(f"Set value of {selector} to '{value}'", "modify", {"status": "success"})

            # Add attributes if specified
            if add_attribute:
                for attr_name, attr_value in add_attribute.items():
                    await element.evaluate(f'''(el) => {{
                        el.setAttribute('{attr_name}', '{attr_value}');
                    }}''')
                StatusManager.update_status(f"Added attributes to {selector}", "modify", {"status": "success"})

            # Execute custom script if specified
            if script:
                await element.evaluate(f'''(el) => {{
                    {script}
                }}''')
                StatusManager.update_status(f"Executed custom script on {selector}", "modify", {"status": "success"})

            return True
        except Exception as e:
            if step.get('skip_on_failure', True):
                StatusManager.update_status(f"Error modifying element: {str(e)}, continuing...", "warn")
                return False
            StatusManager.update_status(f"Error modifying element: {str(e)}", "error")
            raise

    @staticmethod
    async def execute_step(page, step):
        """Execute a single step based on its type"""
        step_type = step.get('type')

        if not step_type:
            StatusManager.update_status("Step missing type, skipping", "warn")
            return False

        # Map step types to handler methods
        handlers = {
            'navigate': StepHandlers.handle_navigate,
            'wait': StepHandlers.handle_wait,
            'click': StepHandlers.handle_click,
            'input': StepHandlers.handle_input,
            'select': StepHandlers.handle_select,
            'wait_for_element': StepHandlers.handle_wait_for_element,
            'wait_for_url': StepHandlers.handle_wait_for_url,
            'execute_js': StepHandlers.handle_execute_js,
            'extract_data': StepHandlers.handle_extract_data,
            'conditional': StepHandlers.handle_conditional,
            'loop': StepHandlers.handle_loop,
            'captcha': StepHandlers.handle_captcha,
            'blur': StepHandlers.handle_blur,
            'modify': StepHandlers.handle_modify,
        }

        handler = handlers.get(step_type)
        if not handler:
            StatusManager.update_status(f"Unknown step type: {step_type}", "error")
            raise ValueError(f"Unknown step type: {step_type}")

        try:
            return await handler(page, step)
        except Exception as e:
            StatusManager.update_status(f"Step execution failed: {str(e)}", "error")
            raise
