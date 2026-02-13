import json
import logging
import re
from typing import Optional

from livekit.agents import JobContext

logger = logging.getLogger(__name__)


class SIPPayloadExtractor:
    """Extract information from SIP payload and room context"""

    @staticmethod
    def extract_mobile_number(room_name: str, sip_context: dict = None) -> str | None:
        """
        Extract mobile number from room name or SIP context
        
        Args:
            room_name (str): LiveKit room name
            sip_context (dict): SIP context data if available
            
        Returns:
            str: Extracted mobile number (10 digits)
        """
        # First try to get from SIP context if available
        if sip_context:
            # Check various SIP header fields where caller ID might be
            caller_fields = [
                sip_context.get("caller_id"),
                sip_context.get("from_number"),
                sip_context.get("from"),
                sip_context.get("remote_identity"),
                sip_context.get("p_asserted_identity")
            ]

            for field in caller_fields:
                if field:
                    # Extract digits from the field
                    digits = re.findall(r'\d', str(field))
                    if len(digits) >= 10:
                        # Take last 10 digits (removes country code if present)
                        return ''.join(digits[-10:])

        # Fallback to extracting from room name (your existing logic)
        mobile = SIPPayloadExtractor._extract_from_string(room_name)
        if mobile:
            return mobile

        return None  # Default fallback

    @staticmethod
    def extract_mobile_from_room_name(room_name: str) -> Optional[str]:
        """
        Extract mobile number from room name string.

        Args:
            room_name: Room name string in format like "agent_room_125_+919870064932_MtPJucR6L7gn"

        Returns:
            Mobile number as string (e.g., "+919870064932") or None if not found
            :param room_name:
        """
        # Method 1: Using regex to find mobile number pattern
        # Matches +91 followed by 10 digits
        mobile_pattern = r'\+91\d{10}'
        match = re.search(mobile_pattern, room_name)

        if match:
            return match.group()
        return None

    @staticmethod
    def extract_sip_headers(ctx: JobContext) -> dict:
        """
        Extract SIP-related information from LiveKit context
        This needs to be adapted based on how your SIP gateway passes data
        """
        sip_data = {}

        # Method 1: Check if SIP data is in room metadata
        if hasattr(ctx.room, 'metadata') and ctx.room.metadata:
            try:
                metadata = json.loads(ctx.room.metadata)
                sip_data.update(metadata.get('sip', {}))
            except (json.JSONDecodeError, AttributeError):
                pass

        # Method 2: Check room name for SIP trunk info
        room_name = ctx.room.name

        # Method 3: Check if there are data packets with SIP info
        # This would be populated by your SIP gateway sending initial data
        return {
            "caller_id": sip_data.get("caller_id"),
            "from_number": sip_data.get("from"),
            "to_number": sip_data.get("to"),
            "call_id": sip_data.get("call_id", room_name),
            "user_agent": sip_data.get("user_agent"),
            "room_name": room_name
        }

    @staticmethod
    def _extract_from_string(text: str) -> str:
        """
        Extract mobile number from a string, handling country codes

        Args:
            text (str): String containing phone number

        Returns:
            str: 10-digit mobile number or None if not found
        """
        # Remove common separators and spaces
        cleaned = re.sub(r'[^\d+]', '', text)

        # Pattern 1: Look for +91 followed by 10 digits (India)
        india_pattern = r'\+91(\d{10})'
        match = re.search(india_pattern, cleaned)
        if match:
            return match.group(1)

        # Pattern 2: Look for +1 followed by 10 digits (US/Canada)
        us_pattern = r'\+1(\d{10})'
        match = re.search(us_pattern, cleaned)
        if match:
            return match.group(1)

        # Pattern 3: Look for other country codes (2-3 digits) followed by 10+ digits
        intl_pattern = r'\+\d{1,3}(\d{10,})'
        match = re.search(intl_pattern, cleaned)
        if match:
            # Take last 10 digits for standardization
            digits = match.group(1)
            return digits[-10:] if len(digits) >= 10 else None

        # Pattern 4: Just extract all digits and take last 10 (fallback)
        all_digits = re.findall(r'\d', text)
        if len(all_digits) >= 10:
            return ''.join(all_digits[-10:])

        return None
