package labs.yutrix.uw.worklist;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ClassPathResource;
import org.springframework.stereotype.Service;

import java.io.File;
import java.io.IOException;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Service for managing customer worklist data from JSON file.
 */
@Service
@Slf4j
public class WorklistService {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private List<Map<String, Object>> customersData;

    /**
     * Writable copy of the dataset (see {@code app.customers-file}). When set and present, the
     * service loads from — and persists PTP predictions back to — this file so the model is only
     * called once per account. Blank => fall back to the read-only classpath resource.
     */
    @Value("${app.customers-file:}")
    private String customersFile;

    @PostConstruct
    public void loadCustomersData() {
        try {
            File file = customersFile == null || customersFile.isBlank() ? null : new File(customersFile);
            if (file != null && file.exists()) {
                customersData = objectMapper.readValue(file, new TypeReference<List<Map<String, Object>>>() {});
                log.info("Loaded {} customer records from {}", customersData.size(), file.getPath());
            } else {
                ClassPathResource resource = new ClassPathResource("data/customers.json");
                customersData = objectMapper.readValue(
                        resource.getInputStream(),
                        new TypeReference<List<Map<String, Object>>>() {}
                );
                log.info("Loaded {} customer records from classpath customers.json", customersData.size());
            }
        } catch (IOException e) {
            log.error("Failed to load customers.json", e);
            customersData = List.of();
        }
    }

    /**
     * Get all customers for the worklist table.
     * Returns simplified DTO with only fields needed for the table.
     */
    public List<WorklistItemDTO> getWorklist() {
        return customersData.stream()
                .map(this::mapToWorklistItem)
                .sorted((a, b) -> Integer.compare(b.dpd(), a.dpd())) // Sort by DPD descending
                .collect(Collectors.toList());
    }

    /**
     * Get full customer context by agreement ID.
     * Used when starting a call to load complete customer profile.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> getCustomerContext(String agreementId) {
        log.info("Looking for customer with agreementId: {}", agreementId);
        log.info("Total customers loaded: {}", customersData != null ? customersData.size() : "null");

        if (customersData == null || customersData.isEmpty()) {
            log.error("customersData is null or empty!");
            return null;
        }

        Map<String, Object> result = customersData.stream()
                .filter(data -> {
                    Map<String, Object> customer = (Map<String, Object>) data.get("customer");
                    String id = (String) customer.get("agreementId");
                    log.debug("Checking customer: {} (agreementId: {})", customer.get("name"), id);
                    return agreementId.equals(id);
                })
                .findFirst()
                .orElse(null);

        if (result == null) {
            log.warn("Customer not found for agreementId: {}", agreementId);
        } else {
            log.info("Customer found for agreementId: {}", agreementId);
        }

        return result;
    }

    /**
     * Get full customer context by mobile number.
     * Normalizes both the query and stored mobile to last 10 digits for matching.
     */
    @SuppressWarnings("unchecked")
    public Map<String, Object> getCustomerContextByMobile(String mobile) {
        if (customersData == null || customersData.isEmpty() || mobile == null) {
            return null;
        }

        String normalizedQuery = normalizeMobile(mobile);
        log.info("Looking for customer with mobile: {} (normalized: {})", mobile, normalizedQuery);

        Map<String, Object> result = customersData.stream()
                .filter(data -> {
                    Map<String, Object> customer = (Map<String, Object>) data.get("customer");
                    String storedMobile = normalizeMobile((String) customer.get("mobile"));
                    return normalizedQuery.equals(storedMobile);
                })
                .findFirst()
                .orElse(null);

        if (result == null) {
            log.warn("Customer not found for mobile: {}", mobile);
        } else {
            log.info("Customer found for mobile: {}", mobile);
        }

        return result;
    }

    /**
     * Cache a PTP prediction on the customer record so the model is only called once per account.
     * Mutates the in-memory record and persists the whole dataset back to {@code app.customers-file}
     * (when configured) so the cache survives restarts.
     */
    public synchronized void savePrediction(String agreementId, Map<String, Object> prediction) {
        Map<String, Object> record = getCustomerContext(agreementId);
        if (record == null) {
            return;
        }
        record.put("prediction", prediction);
        persist();
    }

    /** Writes the current dataset back to the configured writable file (no-op if unset). */
    private void persist() {
        if (customersFile == null || customersFile.isBlank()) {
            log.debug("app.customers-file not set — prediction cached in memory only");
            return;
        }
        try {
            objectMapper.writerWithDefaultPrettyPrinter().writeValue(new File(customersFile), customersData);
        } catch (IOException e) {
            log.warn("Failed to persist customers.json predictions: {}", e.getMessage());
        }
    }

    /**
     * Normalize mobile number to last 10 digits for consistent matching.
     */
    private String normalizeMobile(String mobile) {
        if (mobile == null) return "";
        String digits = mobile.replaceAll("[^\\d]", "");
        return digits.length() >= 10 ? digits.substring(digits.length() - 10) : digits;
    }

    @SuppressWarnings("unchecked")
    private WorklistItemDTO mapToWorklistItem(Map<String, Object> data) {
        Map<String, Object> customer = (Map<String, Object>) data.get("customer");
        Map<String, Object> loan = (Map<String, Object>) data.get("loan");
        Map<String, Object> additional = (Map<String, Object>) data.get("additionalDetails");
        List<Map<String, Object>> pastComms = (List<Map<String, Object>>) data.get("pastCommunications");

        String agreementId = (String) customer.get("agreementId");
        String name = (String) customer.get("name");
        String mobile = maskMobile((String) customer.get("mobile"));
        String loanType = (String) customer.get("loanType");
        String outstanding = (String) loan.get("outstanding");
        String overdue = (String) loan.get("overdue");
        Integer dpd = (Integer) additional.get("dpd");

        // Get last communication
        String lastContactDate = "";
        String lastContactSummary = "";
        if (pastComms != null && !pastComms.isEmpty()) {
            Map<String, Object> lastComm = pastComms.get(0);
            lastContactDate = (String) lastComm.get("date");
            lastContactSummary = (String) lastComm.get("summary");
        }

        String priority = WorklistItemDTO.calculatePriority(dpd);

        return new WorklistItemDTO(
                agreementId,
                name,
                mobile,
                loanType,
                outstanding,
                overdue,
                dpd,
                priority,
                lastContactDate,
                lastContactSummary,
                null,   // ptpBand — populated by the controller via PtpPredictionService
                null    // paymentBand — populated by the controller via PtpPredictionService
        );
    }

    /**
     * Mask mobile number for privacy (e.g., 9845894932 → XXXX-XXX-932)
     */
    private String maskMobile(String mobile) {
        if (mobile == null || mobile.length() < 10) {
            return mobile;
        }
        String cleaned = mobile.replaceAll("[^0-9]", "");
        if (cleaned.length() == 10) {
            return "XXXX-XXX-" + cleaned.substring(7);
        }
        return mobile;
    }
}
