"""Real-time speech-to-speech translation layer (Gemini Live Translate).

Opt-in via TRANSLATION_MODE=on. When disabled (default) this package is never
imported and the existing transcription flow is completely unaffected.
"""

from translation.manager import TranslationManager

__all__ = ["TranslationManager"]
