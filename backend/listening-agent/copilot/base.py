"""Abstract base interface for all copilot implementations."""

from abc import ABC, abstractmethod


class BaseCopilot(ABC):
    """
    Abstract interface that both Collections and Customer Service copilots implement.
    The calling code (LiveKit event handlers, transcript callbacks) uses this interface
    so it doesn't need to know which copilot is active.
    """

    @abstractmethod
    async def initialize(self):
        """Called once after construction. Fetch customer profile, generate pre-call data, etc."""
        pass

    @abstractmethod
    async def process_utterance(self, speaker: str, text: str, timestamp: str):
        """Called for every transcript turn (both agent and customer)."""
        pass

    @abstractmethod
    async def on_call_end(self):
        """Called on SIP disconnect. Generate disposition if applicable."""
        pass
