package labs.yutrix.uw.transcript;

import labs.yutrix.uw.insight.InsightItemDTO;
import java.util.List;

/**
 * Unified DTO for sending the combined conversation summary and AI insights to
 * the frontend.
 */
public record SummaryCombinedDTO(
        List<SummaryItemDTO> summaryItems,
        List<InsightItemDTO> insightItems) {
}
