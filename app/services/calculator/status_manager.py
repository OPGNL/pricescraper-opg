from typing import Dict, Any, Optional
from datetime import datetime
import logging


class StatusManager:
    """Handles status updates and logging for price calculation operations"""

    # Class variable to store latest status
    latest_status = None

    @classmethod
    def update_status(cls, message: str, step_type: str = None, step_details: dict = None):
        """Update the status of the current operation with detailed logging"""
        # Create the status object
        cls.latest_status = {
            "message": message,
            "step_type": step_type,
            "step_details": step_details,
            "timestamp": datetime.now().isoformat()
        }

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
                    detail_parts.append(f"status={value}")
                elif key == 'value':
                    detail_parts.append(f"value='{value}'")
                elif key == 'unit':
                    detail_parts.append(f"unit={value}")
                elif key == 'price':
                    detail_parts.append(f"price={value}")
                elif key == 'calculation':
                    detail_parts.append(f"calculation='{value}'")
                else:
                    detail_parts.append(f"{key}={value}")

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
