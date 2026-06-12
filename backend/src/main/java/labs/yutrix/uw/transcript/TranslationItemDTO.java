package labs.yutrix.uw.transcript;

/**
 * Broadcast to the frontend on /topic/call/{sessionId}/translation.
 * Matches the frontend TranslationItem interface.
 */
public record TranslationItemDTO(
        String speaker,          // "agent" | "customer" (who spoke the source)
        String originalText,
        String translatedText,
        String originalLang,
        String translatedLang,
        String ts
) {}
