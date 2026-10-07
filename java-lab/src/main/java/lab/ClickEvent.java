package lab;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import org.hibernate.validator.constraints.CodePointLength;

import java.time.OffsetDateTime;
import java.util.UUID;

public record ClickEvent(
        @JsonProperty("event_id") @NotNull UUID eventId,
        @JsonProperty("schema_version") @NotNull @Min(1) @Max(1) Integer schemaVersion,
        @JsonProperty("occurred_at") @NotNull OffsetDateTime occurredAt,
        @JsonProperty("session_id") @NotNull @CodePointLength(min = 1, max = 128) String sessionId,
        @NotNull @CodePointLength(min = 1, max = 2048) String page,
        @JsonProperty("element_id") @NotNull @CodePointLength(min = 1, max = 128) String elementId
) {
    public ClickEvent {
        sessionId = sessionId == null ? null : sessionId.strip();
        page = page == null ? null : page.strip();
        elementId = elementId == null ? null : elementId.strip();
    }
}
