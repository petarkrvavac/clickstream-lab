package lab;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.condition.EnabledIfEnvironmentVariable;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.SingleConnectionDataSource;

import java.time.OffsetDateTime;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

@EnabledIfEnvironmentVariable(named = "JDBC_TEST_URL", matches = ".+")
class ClickEventDaoTest {
    @Test
    void storesMapsAndPreservesOriginalOnConflict() {
        var source = new SingleConnectionDataSource(System.getenv("JDBC_TEST_URL"),
                System.getenv("JDBC_TEST_USER"), System.getenv("JDBC_TEST_PASSWORD"), true);
        try {
            var jdbc = new JdbcTemplate(source);
            // Session-local table shadows the real table and disappears on disconnect.
            jdbc.execute("""
                    CREATE TEMPORARY TABLE click_events (
                        event_id UUID PRIMARY KEY,
                        schema_version INTEGER NOT NULL CHECK (schema_version = 1),
                        occurred_at TIMESTAMPTZ NOT NULL,
                        session_id VARCHAR(128) NOT NULL CHECK (length(session_id) > 0),
                        page VARCHAR(2048) NOT NULL CHECK (length(page) > 0),
                        element_id VARCHAR(128) NOT NULL CHECK (length(element_id) > 0)
                    )
                    """);
            var dao = new ClickEventDao(jdbc);
            var service = new ClickEventService(dao);
            var event = new ClickEvent(UUID.randomUUID(), 1,
                    OffsetDateTime.parse("2026-10-07T12:00:00.123456+02:00"),
                    "session-'", "/products?search='; DROP TABLE click_events; --", "gumb-č😀");
            assertTrue(service.findById(event.eventId()).isEmpty());
            assertTrue(service.store(event).inserted());
            var stored = service.findById(event.eventId()).orElseThrow();
            assertEquals(event.eventId(), stored.eventId());
            assertEquals(event.schemaVersion(), stored.schemaVersion());
            assertEquals(event.occurredAt().toInstant(), stored.occurredAt().toInstant());
            assertEquals(event.sessionId(), stored.sessionId());
            assertEquals(event.page(), stored.page());
            assertEquals(event.elementId(), stored.elementId());
            var duplicate = new ClickEvent(event.eventId(), 1, event.occurredAt(),
                    "other-session", "/changed", "other-element");
            var result = service.store(duplicate);
            assertFalse(result.inserted());
            assertEquals(stored, result.event());
            assertEquals(1, jdbc.queryForObject("SELECT count(*) FROM click_events", Integer.class));
        } finally {
            source.destroy();
        }
    }
}
