package lab;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

import java.time.OffsetDateTime;
import java.util.Optional;
import java.util.UUID;

@Repository
public class ClickEventDao {
    private final JdbcTemplate jdbc;

    public ClickEventDao(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    public boolean insert(ClickEvent event) {
        int rows = jdbc.update("""
                INSERT INTO click_events
                    (event_id, schema_version, occurred_at, session_id, page, element_id)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (event_id) DO NOTHING
                """, event.eventId(), event.schemaVersion(), event.occurredAt(),
                event.sessionId(), event.page(), event.elementId());
        return rows == 1;
    }

    public Optional<ClickEvent> findById(UUID eventId) {
        var events = jdbc.query("""
                SELECT event_id, schema_version, occurred_at, session_id, page, element_id
                FROM click_events WHERE event_id = ?
                """, (rs, rowNumber) -> new ClickEvent(
                rs.getObject("event_id", UUID.class),
                rs.getInt("schema_version"),
                rs.getObject("occurred_at", OffsetDateTime.class),
                rs.getString("session_id"),
                rs.getString("page"),
                rs.getString("element_id")), eventId);
        return events.stream().findFirst();
    }
}
