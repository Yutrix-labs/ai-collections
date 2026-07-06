package labs.yutrix.uw.integration;

import jakarta.mail.internet.MimeMessage;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

/**
 * Sends the customer their LiveKit join link by email when a call starts.
 *
 * <p>Runs asynchronously and swallows all errors: emailing is best-effort and must never affect
 * the {@code /call/start} response or any other call functionality. If SMTP is unconfigured or the
 * recipient is missing, it is a no-op.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class EmailService {

    private final JavaMailSender mailSender;

    @Value("${spring.mail.username:}")
    private String from;

    @Async
    public void sendCustomerJoinLink(String toEmail, String customerName, String joinUrl) {
        if (toEmail == null || toEmail.isBlank() || joinUrl == null || joinUrl.isBlank()) {
            log.info("[Email] Skipping join-link email — missing recipient or joinUrl (to={})", toEmail);
            return;
        }
        if (from == null || from.isBlank()) {
            log.info("[Email] Skipping join-link email — SMTP not configured (MAIL_USERNAME unset)");
            return;
        }
        try {
            MimeMessage message = mailSender.createMimeMessage();
            MimeMessageHelper helper = new MimeMessageHelper(message, false, "UTF-8");
            helper.setFrom(from);
            helper.setTo(toEmail);
            helper.setSubject("Your call link");
            helper.setText(buildBody(customerName, joinUrl), true);
            mailSender.send(message);
            log.info("[Email] Join link sent | to={}", toEmail);
        } catch (Exception e) {
            log.error("[Email] Failed to send join link | to={} error={}", toEmail, e.getMessage());
        }
    }

    private String buildBody(String name, String joinUrl) {
        String greeting = (name == null || name.isBlank()) ? "Hello," : "Hello " + name + ",";
        return "<div style=\"font-family:Arial,sans-serif;font-size:15px;color:#1e293b;line-height:1.6\">"
                + "<p>" + greeting + "</p>"
                + "<p>Your agent is ready to connect with you. Click the button below to join the call:</p>"
                + "<p style=\"margin:24px 0\">"
                + "<a href=\"" + joinUrl + "\" "
                + "style=\"background:#2563eb;color:#ffffff;text-decoration:none;padding:12px 24px;"
                + "border-radius:8px;font-weight:600;display:inline-block\">Join Call</a>"
                + "</p>"
                + "<p style=\"font-size:13px;color:#64748b\">If the button doesn't work, copy and paste this link:<br>"
                + "<a href=\"" + joinUrl + "\">" + joinUrl + "</a></p>"
                + "</div>";
    }
}
