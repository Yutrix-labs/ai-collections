package labs.yutrix.uw.transcript;

/**
 * Matches the frontend TranscriptItem interface:
 * { speaker: "agent"|"customer", text: string, ts: string, sentiment: "positive"|"neutral"|"negative" }
 */
public record TranscriptItemDTO(
        String speaker,
        String text,
        String ts,
        String sentiment
) {}
