# Minimal Spring Data JPA comparison

These are separate teaching snippets, not active application classes. Each Java
block represents a separate file in package `comparison`. Nothing here changes
the JDBC lab's source, dependencies, endpoints, or duplicate handling.

## Entity: ClickEventEntity.java

```java
package comparison;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name = "click_events")
public class ClickEventEntity {
    @Id
    @Column(name = "event_id", nullable = false)
    private UUID eventId;

    @Column(name = "schema_version", nullable = false)
    private Integer schemaVersion;

    @Column(name = "occurred_at", nullable = false)
    private OffsetDateTime occurredAt;

    @Column(name = "session_id", nullable = false, length = 128)
    private String sessionId;

    @Column(name = "page", nullable = false, length = 2048)
    private String page;

    @Column(name = "element_id", nullable = false, length = 128)
    private String elementId;

    protected ClickEventEntity() {} // Required by JPA.

    public ClickEventEntity(UUID eventId, Integer schemaVersion,
                            OffsetDateTime occurredAt, String sessionId,
                            String page, String elementId) {
        this.eventId = eventId;
        this.schemaVersion = schemaVersion;
        this.occurredAt = occurredAt;
        this.sessionId = sessionId;
        this.page = page;
        this.elementId = elementId;
    }

    public UUID getEventId() { return eventId; }
    public Integer getSchemaVersion() { return schemaVersion; }
    public OffsetDateTime getOccurredAt() { return occurredAt; }
    public String getSessionId() { return sessionId; }
    public String getPage() { return page; }
    public String getElementId() { return elementId; }
}
```

`@Entity` makes this a JPA persistence type. `@Table` selects the existing table;
`@Id` identifies its primary key; `@Column` maps each field to its SQL column.
Because the annotations are on fields, Hibernate uses field access and does not
need setters. The no-argument constructor lets it instantiate loaded rows.
The UUID comes from the incoming event, so there is no `@GeneratedValue`.
`schemaVersion` is an event-format field, **not** a JPA `@Version` concurrency field.

This ordinary, non-final class is separate from the HTTP `ClickEvent` record.
Column lengths/nullability are mapping metadata, not substitutes for the current
request validation, trimming, or the database's CHECK constraints. This example
does not implement those HTTP rules.

## Repository: ClickEventRepository.java

```java
package comparison;

import org.springframework.data.jpa.repository.JpaRepository;
import java.util.UUID;

public interface ClickEventRepository
        extends JpaRepository<ClickEventEntity, UUID> {
}
```

The generic arguments mean “entity type ClickEventEntity, primary-key type UUID.”
Inherited operations include `findById`, `save`, `findAll`, and `deleteById`.
`findById(id)` returns `Optional<ClickEventEntity>`: present if found, empty if
absent. The repository does not decide HTTP 404; a controller would do that.

## Constructor injection: ClickEventJpaExampleService.java

```java
package comparison;

import org.springframework.stereotype.Service;
import java.util.Optional;
import java.util.UUID;

@Service
public class ClickEventJpaExampleService {
    private final ClickEventRepository repository;

    public ClickEventJpaExampleService(ClickEventRepository repository) {
        this.repository = repository;
    }

    public Optional<ClickEventEntity> findById(UUID id) {
        return repository.findById(id);
    }

    public ClickEventEntity save(ClickEventEntity event) {
        return repository.save(event);
    }
}
```

For example, a caller could construct the six-field entity, call
`ClickEventEntity saved = service.save(entity)`, then
`service.findById(saved.getEventId())`. Use the returned `saved` instance:
`merge` can return a different managed object rather than attach the original.

## What exists at runtime

In a separately configured Boot application with the JPA starter, entity and
repository scanning enabled for `comparison`, and a datasource:

1. Boot configures the datasource, Hibernate-backed EntityManagerFactory, and
   JPA transaction manager.
2. Spring Data discovers the repository interface and creates a proxy bean that
   implements it. Default CRUD calls delegate to `SimpleJpaRepository`, backed
   by a JPA EntityManager, with repository transaction handling.
3. Spring detects the `@Service` class and supplies that repository proxy to its
   constructor. A single constructor does not require `@Autowired`.
4. Hibernate reads entity metadata, generates parameterized SQL, and maps results
   into entity instances. JDBC and the PostgreSQL driver still carry out the SQL.

JPA is the persistence specification; Hibernate is its implementation here;
Spring Data JPA supplies the repository abstraction on top. A repository proxy
is an actual object implementing the interface, not an interface instantiated
with `new`. An entity is a per-row persistence object, not a singleton service
bean created merely because it has `@Entity`.

`findById` ultimately uses `EntityManager.find`; it may generate a SELECT or use
an entity already available in the persistence context. Hibernate does the
column-to-field mapping instead of our explicit JDBC row mapper. Writes are
synchronized at flush, normally before transaction commit; a `save` call is not
always the exact moment the SQL INSERT or UPDATE is sent.

## save is not INSERT ON CONFLICT DO NOTHING

Spring Data's default newness detection checks a nullable JPA version field,
then the ID. This entity has no `@Version` and receives a non-null UUID, so
`save` calls **EntityManager.merge**, even for an ID not yet in the database.
For this mapping, merging an absent ID can lead to INSERT; merging an existing
ID can copy the supplied state and lead to UPDATE. It may first issue a SELECT.
The newness decision does not itself query whether the database row exists.

| Existing JDBC DAO | This JPA example |
| --- | --- |
| You write INSERT and SELECT SQL | Hibernate supplies SQL for repository operations |
| Explicit ResultSet-to-record mapper | Entity annotations describe column-to-field mapping |
| Insert count distinguishes new/duplicate | save returns an entity, not an insertion boolean |
| Duplicate ID preserves the original row atomically | save may update existing data; no DO NOTHING guarantee |

`persist` is not a conflict-ignore operation either: inserting a duplicate can
fail. Checking `existsById` before `save` would not reproduce the atomic SQL
behavior because another request can insert between the two calls. Exact
PostgreSQL conflict-ignore semantics require explicit SQL, such as the existing
DAO or a deliberately defined native repository query; that is outside this
comparison.

## Interface versus abstract class

An interface defines a contract. It can inherit multiple interfaces, and can
have default, static, and private methods, but has no per-instance fields or
constructors. A class can implement multiple interfaces. Here, `extends` means
the repository interface inherits the JpaRepository contract.

An abstract class can contain instance fields, constructors, abstract methods,
and implemented methods. It cannot be directly instantiated; a concrete
subclass is needed, and a class can extend only one class. Making an arbitrary
abstract class does not trigger Spring Data repository implementation creation.

In the JDBC lab, we wrote the concrete DAO class and Spring creates its bean.
In the JPA example, Spring Data creates the repository proxy bean from the
interface. Both can be injected through a constructor by their declared type.

## Dependencies/configuration for a separate runnable application

These are illustrative only; they have **not** been added to the working lab.
Use the same Boot 3.5.16 parent and Java 21, the PostgreSQL runtime driver, and:

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-data-jpa</artifactId>
</dependency>
```

Use the existing environment-based datasource settings. To verify the existing
schema without creating or updating it, and to display Hibernate SQL:

```properties
spring.jpa.hibernate.ddl-auto=validate
spring.jpa.open-in-view=false
spring.jpa.show-sql=true
spring.sql.init.mode=never
```

A separate `@SpringBootApplication` in package `comparison` would provide the
default scanning scope for these classes. No new application, controller,
database, or project build is created by this documentation example.

Sources: [Spring Data 3.5 save/newness](https://docs.spring.io/spring-data/jpa/reference/3.5/jpa/entity-persistence.html),
[SimpleJpaRepository implementation](https://github.com/spring-projects/spring-data-jpa/blob/3.5.x/spring-data-jpa/src/main/java/org/springframework/data/jpa/repository/support/SimpleJpaRepository.java),
[Hibernate 6.6 mapping and flushing](https://docs.hibernate.org/orm/6.6/userguide/html_single/),
[Spring constructor injection](https://docs.spring.io/spring-framework/reference/core/beans/annotation-config/autowired.html).
