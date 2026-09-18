package labs.yutrix.uw.transcript;

/**
 * Matches the frontend TranscriptItem interface:
 * { speaker, text, textAr?, ts, sentiment } — textAr is the Arabic (Kuwait) rendering
 * shown alongside the English in the live transcript; null outside the scripted demo.
 */
public record TranscriptItemDTO(
        String speaker,
        String text,
        String textAr,
        String ts,
        String sentiment
) {}
