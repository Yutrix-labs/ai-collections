package labs.yutrix.uw.worklist;

/**
 * DTO for worklist table display.
 * Contains essential customer information for the collections worklist UI.
 */
public record WorklistItemDTO(
        String agreementId,
        String name,
        String mobile,
        String loanType,
        String outstanding,
        String overdue,
        Integer dpd,
        String priority,
        String lastContactDate,
        String lastContactSummary
) {
    /**
     * Calculate priority based on DPD (Days Past Due).
     */
    public static String calculatePriority(int dpd) {
        if (dpd >= 60) return "HIGH";
        if (dpd >= 30) return "MEDIUM";
        return "LOW";
    }
}
