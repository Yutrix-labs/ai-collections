"""Factory function that returns the correct copilot based on COPILOT_MODE env var."""

import os
import logging

from copilot.base import BaseCopilot
from copilot.collections import CollectionsCopilot

logger = logging.getLogger(__name__)


def create_copilot(call_sid: str, http_session, mobile_number: str | None = None) -> BaseCopilot:
    """
    Read COPILOT_MODE from environment and return the appropriate copilot instance.
    Default: collections (preserves existing behavior).
    """
    mode = os.getenv("COPILOT_MODE", "collections").lower().strip()

    if mode == "customer_service":
        # Lazy import to avoid loading customer service deps in collections mode
        from copilot.customer_service import CustomerServiceCopilot
        logger.info(f"Creating CustomerServiceCopilot | callSid={call_sid} mobile={mobile_number}")
        return CustomerServiceCopilot(call_sid, http_session, mobile_number)
    elif mode == "collections":
        logger.info(f"Creating CollectionsCopilot | callSid={call_sid} mobile={mobile_number}")
        return CollectionsCopilot(call_sid, http_session, mobile_number)
    else:
        raise ValueError(
            f"Unknown COPILOT_MODE: '{mode}'. Valid values: 'collections', 'customer_service'"
        )
