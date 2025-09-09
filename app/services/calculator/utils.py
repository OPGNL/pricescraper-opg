import json
import re
import random
import time
import asyncio
from typing import Dict, Any, List, Optional
from .status_manager import StatusManager


class CalculatorUtils:
    """Utility functions for the price calculator"""

    @staticmethod
    def format_step_parameters(parameters: Dict[str, Any], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Format step parameters by replacing placeholders with actual values"""
        if context is None:
            context = {}

        formatted_params = {}

        for key, value in parameters.items():
            if isinstance(value, str):
                # Replace placeholders like {variable_name} with actual values
                formatted_value = value
                for var_name, var_value in context.items():
                    placeholder = f"{{{var_name}}}"
                    if placeholder in formatted_value:
                        formatted_value = formatted_value.replace(placeholder, str(var_value))
                formatted_params[key] = formatted_value
            elif isinstance(value, dict):
                formatted_params[key] = CalculatorUtils.format_step_parameters(value, context)
            elif isinstance(value, list):
                formatted_params[key] = [
                    CalculatorUtils.format_step_parameters(item, context) if isinstance(item, dict)
                    else item for item in value
                ]
            else:
                formatted_params[key] = value

        return formatted_params

    @staticmethod
    def validate_step_config(step: Dict[str, Any]) -> bool:
        """Validate step configuration"""
        required_fields = ['type']

        # Check required fields
        for field in required_fields:
            if field not in step:
                StatusManager.update_status(f"Step missing required field: {field}", "error")
                return False

        step_type = step['type']

        # Type-specific validation
        type_requirements = {
            'navigate': ['url'],
            'click': ['selector'],
            'input': ['selector', 'value'],
            'select': ['selector', 'value'],
            'wait_for_element': ['selector'],
            'wait_for_url': ['pattern'],
            'execute_js': ['script'],
            'captcha': ['captcha_type'],
        }

        if step_type in type_requirements:
            for field in type_requirements[step_type]:
                if field not in step:
                    StatusManager.update_status(f"Step type '{step_type}' missing required field: {field}", "error")
                    return False

        return True

    @staticmethod
    def generate_random_delay(min_delay: float = 1.0, max_delay: float = 3.0) -> float:
        """Generate a random delay to mimic human behavior"""
        return random.uniform(min_delay, max_delay)

    @staticmethod
    def extract_numbers_from_text(text: str) -> List[float]:
        """Extract all numbers from text"""
        if not text:
            return []

        # Pattern to match numbers (including decimals and negatives)
        pattern = r'-?\d+\.?\d*'
        matches = re.findall(pattern, text)

        numbers = []
        for match in matches:
            try:
                if '.' in match:
                    numbers.append(float(match))
                else:
                    numbers.append(float(match))
            except ValueError:
                continue

        return numbers

    @staticmethod
    def clean_price_text(text: str) -> str:
        """Clean price text by removing common currency symbols and formatting"""
        if not text:
            return ""

        # Remove common currency symbols
        text = re.sub(r'[£$€¥₹₽¢₩₪₦₡₨₫₱₹₽]', '', text)

        # Remove common words
        words_to_remove = ['total', 'price', 'cost', 'amount', 'sum', 'fee', 'charge']
        for word in words_to_remove:
            text = re.sub(rf'\b{word}\b', '', text, flags=re.IGNORECASE)

        # Clean whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    @staticmethod
    def parse_currency_amount(text: str) -> Optional[float]:
        """Parse currency amount from text"""
        if not text:
            return None

        # Clean the text first
        cleaned = CalculatorUtils.clean_price_text(text)

        # Extract numbers
        numbers = CalculatorUtils.extract_numbers_from_text(cleaned)

        if not numbers:
            return None

        # Return the largest number found (assuming it's the main price)
        return max(numbers)

    @staticmethod
    def format_currency(amount: float, currency: str = "USD") -> str:
        """Format currency amount for display"""
        if currency.upper() == "USD":
            return f"${amount:.2f}"
        elif currency.upper() == "EUR":
            return f"€{amount:.2f}"
        elif currency.upper() == "GBP":
            return f"£{amount:.2f}"
        else:
            return f"{amount:.2f} {currency}"

    @staticmethod
    def calculate_percentage_difference(old_value: float, new_value: float) -> float:
        """Calculate percentage difference between two values"""
        if old_value == 0:
            return 100.0 if new_value > 0 else 0.0

        return ((new_value - old_value) / old_value) * 100

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename by removing invalid characters"""
        # Remove invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)

        # Remove leading/trailing spaces and dots
        sanitized = sanitized.strip(' .')

        # Limit length
        if len(sanitized) > 255:
            sanitized = sanitized[:255]

        return sanitized

    @staticmethod
    def generate_user_agent() -> str:
        """Generate a random user agent string"""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        ]
        return random.choice(user_agents)

    @staticmethod
    def generate_viewport_size() -> Dict[str, int]:
        """Generate a random viewport size"""
        common_sizes = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1536, "height": 864},
            {"width": 1440, "height": 900},
            {"width": 1280, "height": 720},
        ]
        return random.choice(common_sizes)

    @staticmethod
    def is_valid_url(url: str) -> bool:
        """Check if a URL is valid"""
        url_pattern = re.compile(
            r'^https?://'  # http:// or https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
            r'localhost|'  # localhost...
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return url_pattern.match(url) is not None

    @staticmethod
    def extract_domain_from_url(url: str) -> str:
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except:
            return ""

    @staticmethod
    def deep_merge_dicts(dict1: Dict, dict2: Dict) -> Dict:
        """Deep merge two dictionaries"""
        result = dict1.copy()

        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = CalculatorUtils.deep_merge_dicts(result[key], value)
            else:
                result[key] = value

        return result

    @staticmethod
    def safe_json_loads(json_str: str, default: Any = None) -> Any:
        """Safely load JSON string"""
        try:
            return json.loads(json_str)
        except (json.JSONDecodeError, TypeError):
            return default

    @staticmethod
    def safe_json_dumps(obj: Any, default: str = "{}") -> str:
        """Safely dump object to JSON string"""
        try:
            return json.dumps(obj, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def retry_with_exponential_backoff(max_retries: int = 3, base_delay: float = 1.0):
        """Decorator for retrying functions with exponential backoff"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                last_exception = None

                for attempt in range(max_retries):
                    try:
                        return await func(*args, **kwargs)
                    except Exception as e:
                        last_exception = e
                        if attempt < max_retries - 1:
                            delay = base_delay * (2 ** attempt)
                            StatusManager.update_status(
                                f"Retry attempt {attempt + 1}/{max_retries} after {delay}s delay: {str(e)}",
                                "warn"
                            )
                            await asyncio.sleep(delay)
                        else:
                            StatusManager.update_status(f"All retry attempts failed: {str(e)}", "error")

                raise last_exception
            return wrapper
        return decorator

    @staticmethod
    def get_timestamp() -> str:
        """Get current timestamp as string"""
        return time.strftime("%Y-%m-%d %H:%M:%S")

    @staticmethod
    def get_file_timestamp() -> str:
        """Get timestamp suitable for filenames"""
        return time.strftime("%Y%m%d_%H%M%S")

    @staticmethod
    def mask_sensitive_data(data: str, mask_char: str = "*") -> str:
        """Mask sensitive data like API keys"""
        if not data or len(data) <= 8:
            return mask_char * len(data) if data else ""

        # Show first 4 and last 4 characters
        visible_start = data[:4]
        visible_end = data[-4:]
        masked_middle = mask_char * (len(data) - 8)

        return f"{visible_start}{masked_middle}{visible_end}"

    @staticmethod
    def normalize_whitespace(text: str) -> str:
        """Normalize whitespace in text"""
        if not text:
            return ""

        # Replace multiple whitespace characters with single space
        normalized = re.sub(r'\s+', ' ', text)

        # Strip leading and trailing whitespace
        return normalized.strip()

    @staticmethod
    def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
        """Truncate text to specified length"""
        if not text or len(text) <= max_length:
            return text

        return text[:max_length - len(suffix)] + suffix
