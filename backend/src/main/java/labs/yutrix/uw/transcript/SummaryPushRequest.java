package labs.yutrix.uw.transcript;

import jakarta.validation.constraints.NotBlank;
import labs.yutrix.uw.insight.InsightItemDTO;
import java.util.List;

/**
 * Combined request for pushing both conversation summary and AI insights.
 */
public record SummaryPushRequest(
                @NotBlank String callSid,
                @NotBlank String mobileNumber,
                List<SummaryItemDTO> summaryItems,
                List<InsightItemDTO> insightItems) {
}
