package labs.yutrix.uw.email;

import jakarta.mail.internet.MimeMessage;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

/**
 * Sends transactional customer emails. Currently a single concern: emailing the customer the
 * secure link they use to join a live call.
 *
 * <p>Runs {@link Async} so a slow/unreachable SMTP server never blocks the call-start request,
 * and swallows failures (logs them) for the same reason — the call must proceed even if the
 * email can't be delivered.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class EmailService {

    // ObjectProvider so the app still starts if mail auto-config is absent (host not set).
    private final ObjectProvider<JavaMailSender> mailSenderProvider;

    @Value("${app.email.enabled:true}")
    private boolean enabled;

    @Value("${app.email.from-name:Collections Assistant}")
    private String fromName;

    @Value("${spring.mail.username:}")
    private String fromAddress;

    /**
     * Email the customer their one-time join link. No-op (with a log line) when disabled, when the
     * recipient is missing/masked, or when SMTP isn't configured.
     */
    @Async
    public void sendCustomerJoinLink(String toEmail, String customerName, String joinUrl) {
        if (!enabled) {
            log.info("[EMAIL] Disabled (app.email.enabled=false) — skipping join link to {}", toEmail);
            return;
        }
        if (!isSendableAddress(toEmail)) {
            log.warn("[EMAIL] Skipping join link — recipient missing/masked/invalid: {}", toEmail);
            return;
        }
        JavaMailSender sender = mailSenderProvider.getIfAvailable();
        if (sender == null) {
            log.warn("[EMAIL] JavaMailSender not configured (spring.mail.host) — skipping join link to {}", toEmail);
            return;
        }

        try {
            MimeMessage message = sender.createMimeMessage();
            MimeMessageHelper helper = new MimeMessageHelper(message, false, "UTF-8");
            helper.setFrom(fromAddress, fromName);
            helper.setTo(toEmail);
            helper.setSubject("Your secure link to join the call");
            helper.setText(buildHtml(customerName, joinUrl), true);
            sender.send(message);
            log.info("[EMAIL] Join link sent to {}", toEmail);
        } catch (Exception e) {
            // Never fail the call because email delivery hiccuped.
            log.error("[EMAIL] Failed to send join link to {}: {}", toEmail, e.getMessage());
        }
    }

    /** Reject blank, obviously-invalid, or masked (contains '*') addresses like "r***a@gmail.com". */
    private boolean isSendableAddress(String email) {
        return email != null
                && !email.isBlank()
                && email.contains("@")
                && !email.contains("*");
    }

    private String buildHtml(String customerName, String joinUrl) {
        String greetingName = (customerName == null || customerName.isBlank()) ? "there" : customerName;
        return """
                <!DOCTYPE html>
                <html>
                  <body style="margin:0;padding:0;background:#f4f5f7;font-family:Arial,Helvetica,sans-serif;">
                    <table role="presentation" width="100%%" cellpadding="0" cellspacing="0" style="background:#f4f5f7;padding:32px 0;">
                      <tr>
                        <td align="center">
                          <table role="presentation" width="480" cellpadding="0" cellspacing="0"
                                 style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.08);">
                            <tr>
                              <td style="background:#1e40af;padding:24px 32px;">
                                <span style="color:#ffffff;font-size:18px;font-weight:bold;">Collections Assistant</span>
                              </td>
                            </tr>
                            <tr>
                              <td style="padding:32px;color:#111827;">
                                <p style="margin:0 0 16px;font-size:16px;">Hello %s,</p>
                                <p style="margin:0 0 24px;font-size:15px;line-height:1.5;color:#374151;">
                                  Your call representative is ready to speak with you. Click the button below to
                                  join the call securely from your browser — no app or download required.
                                </p>
                                <p style="text-align:center;margin:0 0 24px;">
                                  <a href="%s"
                                     style="display:inline-block;background:#1e40af;color:#ffffff;text-decoration:none;
                                            padding:14px 28px;border-radius:8px;font-size:15px;font-weight:bold;">
                                    Join the Call
                                  </a>
                                </p>
                                <p style="margin:0 0 8px;font-size:13px;color:#6b7280;">
                                  This is a one-time link and will stop working once the call ends. Please do not share it.
                                </p>
                                <p style="margin:16px 0 0;font-size:12px;color:#9ca3af;word-break:break-all;">
                                  If the button doesn't work, copy and paste this link into your browser:<br/>%s
                                </p>
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>
                    </table>
                  </body>
                </html>
                """.formatted(escape(greetingName), joinUrl, joinUrl);
    }

    private String escape(String s) {
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
    }
}
