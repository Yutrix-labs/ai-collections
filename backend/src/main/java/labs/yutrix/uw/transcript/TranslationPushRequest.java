package labs.yutrix.uw.transcript;

import jakarta.validation.constraints.NotBlank;

/**
 * One completed translated turn, pushed by the Python translation bridge.
 * Mirrors what the bridge produces: the original (source) text and its
 * translation, with the language codes for each side.
 */
public record TranslationPushRequest(
        @NotBlank String callSid,
        @NotBlank String mobileNumber,   // used to resolve the session
        @NotBlank String speaker,        // who spoke the SOURCE: "agent" or "customer"
        String originalText,
        String translatedText,
        String originalLang,
        String translatedLang,
        String timestamp
) {}
