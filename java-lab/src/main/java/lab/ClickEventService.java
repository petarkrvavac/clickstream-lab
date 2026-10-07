package lab;

import org.springframework.stereotype.Service;

import java.util.Optional;
import java.util.UUID;

@Service
public class ClickEventService {
    private final ClickEventDao dao;

    public ClickEventService(ClickEventDao dao) {
        this.dao = dao;
    }

    public StoreResult store(ClickEvent event) {
        boolean inserted = dao.insert(event);
        ClickEvent stored = inserted ? event : dao.findById(event.eventId())
                .orElseThrow(() -> new IllegalStateException("Existing event disappeared after insert"));
        return new StoreResult(inserted, stored);
    }

    public Optional<ClickEvent> findById(UUID eventId) {
        return dao.findById(eventId);
    }

    public record StoreResult(boolean inserted, ClickEvent event) {}
}
