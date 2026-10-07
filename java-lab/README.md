# Java click-event lab — JDBC storage

This Java 21 application validates clicks and stores them directly in the existing
PostgreSQL `click_events` table on port 8080. It uses a controller, a small service,
and a concrete JDBC DAO.

## Version and running

Spring Boot **3.5.16** is a released Spring Boot 3 version, available from Maven
Central. It is the final OSS release of the 3.5 generation and fits the requested
3.x learning baseline and Java 21. This is a pinned release, not a snapshot or
milestone. See the [official release announcement](https://spring.io/blog/2026/06/25/spring-boot-3-5-16-available-now/).

### PostgreSQL environment

Spring Boot **does not automatically load the repository's `.env`**. Docker
Compose uses that file for its own configuration; it does not export its values
into the shell that starts Java. Export the variables before starting the app:

```sh
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT=5433  # use your actual published PostgreSQL port
export POSTGRES_DB=click_monitoring
export POSTGRES_USER=learner
read -rsp 'PostgreSQL password: ' POSTGRES_PASSWORD; echo
export POSTGRES_PASSWORD
```

Alternatively, if you trust the repository's `.env` and it contains valid shell
assignments, run from the repository root:

```sh
set -a
. ./.env
set +a
```

`set -a` exports the assignments so the child Java process inherits them. Sourcing
executes shell contents, so use this only with a trusted file. Then enter
`java-lab`. The configuration uses these variables to build
`jdbc:postgresql://HOST:PORT/DB` and set the username and password. Host defaults
to `127.0.0.1`, port to `5432`; database, user, and password must be supplied.
Boot also accepts standard overrides such as `SPRING_DATASOURCE_URL`,
`SPRING_DATASOURCE_USERNAME`, and `SPRING_DATASOURCE_PASSWORD`. A Python-style
`DATABASE_URL=postgresql://...` is not automatically converted to a JDBC URL.
WSL uses the published host port (currently this project's Compose maps
`POSTGRES_PORT`); containers on the Compose network use host `postgres`, port 5432.

The existing PostgreSQL server must be running and `click_events` must already
exist, as defined by the repository's `init_db.py`. This Java step runs no DDL
and creates no tables; `spring.sql.init.mode=never` disables script initialization.
The previous datasource exclusion is removed. Boot configures the HikariCP
connection pool and a `JdbcTemplate` bean from the JDBC starter and properties.

With JDK 21 installed:

```sh
cd java-lab
./mvnw test
./mvnw spring-boot:run
```

On Windows use `mvnw.cmd`. The included official Maven Wrapper 3.3.4 scripts and
JAR download the pinned Maven 3.9.9 distribution on first use; Maven need not be
installed separately. First use needs internet access. `./mvnw package` produces
an executable JAR in `target/`, runnable with
`java -jar target/java-lab-0.0.1-SNAPSHOT.jar`.

```sh
curl -i http://localhost:8080/lab/events/click \
  -H 'Content-Type: application/json' \
  -d '{"event_id":"c46de8cb-9280-4db2-9b7e-d00e7c79cb68","schema_version":1,"occurred_at":"2026-10-06T12:00:00+02:00","session_id":"session-1","page":"/products","element_id":"gumb-č"}'
```

POST outcomes are deliberately distinct:

| Outcome | HTTP status | `X-Event-Inserted` | Body |
| --- | --- | --- | --- |
| New ID | 201 Created | `true` | Validated inserted event |
| Existing ID | 200 OK | `false` | Original event read from PostgreSQL |

An existing ID never updates the original row, even if the new payload differs.
Validation still runs on every POST; invalid payloads return 400 before storage.
The header and status reflect the database insert count, rather than a separate
existence check that could race with another request.

```sh
curl -i http://localhost:8080/lab/events/click/c46de8cb-9280-4db2-9b7e-d00e7c79cb68
```

GET returns the stored six-field event with HTTP 200, or HTTP 404 with an empty
body when absent. A malformed UUID path returns 400. Surrounding whitespace in
input strings is stripped. PostgreSQL `TIMESTAMPTZ` stores an instant, not the
original textual offset; the JDBC driver reads it as `OffsetDateTime` in UTC.
PostgreSQL also stores timestamps at microsecond precision. GET/duplicate
responses can therefore format timestamps differently from the initial POST.

## Understanding pom.xml

`pom.xml` is Maven's project configuration. `groupId`, `artifactId`, and
`version` identify this project's artifact. `modelVersion` is the POM format
version, not the Java or application version. The Spring Boot parent supplies
compatible dependency versions and Maven plugin defaults. `<relativePath/>`
resolves that parent from Maven's repositories rather than a local parent POM.
`java.version` sets the Java compilation release to 21.

A dependency adds a library to the project. A **starter** is a curated dependency
bundle: its transitive dependencies bring the libraries for one common feature.
Boot's auto-configuration then configures components based on those libraries,
properties, and existing beans. A starter itself is not an annotation.

- `spring-boot-starter-web`: Spring MVC, Jackson JSON handling, and embedded
  Tomcat, so the application can serve HTTP without a separate servlet server.
- `spring-boot-starter-validation`: Jakarta Bean Validation with Hibernate
  Validator, used to check the event's constraints.
- `spring-boot-starter-jdbc`: Spring JDBC and HikariCP connection pooling.
  Boot creates the datasource and `JdbcTemplate` from the environment-backed
  properties in `application.properties`.
- `postgresql`: PostgreSQL JDBC driver, with `runtime` scope because production
  code does not import driver classes. Boot manages its version.
- `spring-boot-starter-test`: test-only JUnit, Spring Test, and assertion tools.
  `test` scope keeps these libraries out of the executable application's runtime.

The `spring-boot-maven-plugin` supports `spring-boot:run` and repackages the JAR
with dependencies so it can run with `java -jar`. Dependency versions are omitted
because the pinned Boot parent manages them.

## Annotations and validation

`@SpringBootApplication` enables auto-configuration, component scanning, and
configuration support. Its location in package `lab` allows scanning the
controller in that package. `main` calls `SpringApplication.run` to start Spring
and embedded Tomcat.

`@RestController` registers the controller as a Spring bean and writes return
values into HTTP response bodies. `@PostMapping` maps the POST route.
`@RequestBody` asks Jackson to read the JSON body into `ClickEvent`; `@Valid`
asks Spring to run Bean Validation before invoking the controller method.

`ClickEvent` is an immutable Java record. `@JsonProperty` maps Java camelCase
names to the existing snake_case JSON field names. Its compact constructor
strips surrounding whitespace from strings before validation.

- `@NotNull` makes all six fields required. `Integer` rather than primitive `int`
  preserves missing/null values for validation.
- `@Min(1)` and `@Max(1)` require `schema_version` to equal 1. Jackson coercion
  settings also reject `"1"`, `1.0`, and booleans.
- `UUID` makes malformed UUID text fail during JSON conversion; no UUID version
  restriction is applied.
- `OffsetDateTime` requires an ISO timestamp containing `Z` or an offset such as
  `+02:00`. A local timestamp without an offset fails conversion.
- Hibernate Validator's `@CodePointLength` requires 1–128 Unicode characters for
  `session_id` and `element_id`, and 1–2048 for `page`. Unlike Java `String.length`
  and `@Size`, it counts supplementary characters such as emoji once, matching
  the existing Python model's character limits. Stripped empty strings fail.

`@Bean` in the application registers a small Jackson customizer that rejects
numeric/boolean coercion into strings. The properties also reject unknown fields. It also retains the supplied timestamp offset during deserialization.

## JDBC, DAO, Optional, and SQL execution

**JDBC** is Java's database API: a connection creates a prepared statement,
parameters are bound, the statement executes, and queries return a `ResultSet`.
The PostgreSQL JDBC driver implements that API for PostgreSQL. HikariCP keeps a
pool of reusable connections rather than opening a new physical connection for
every request.

**JdbcTemplate** handles borrowing/releasing connections, creating and closing
statements and result sets, and translating JDBC exceptions into Spring's
`DataAccessException` hierarchy. We still write the SQL and the row mapping.
See [Spring's JDBC documentation](https://docs.spring.io/spring-framework/reference/6.2/data-access/jdbc/core.html).

**DAO** means Data Access Object. `ClickEventDao` is the concrete class containing
the two SQL operations; it has no extra interface or implementation layer.
`@Repository` registers it as a Spring bean. `@Service` registers the small
service. Constructor injection supplies DAO → service → controller and supplies
Boot's `JdbcTemplate` to the DAO. A single constructor needs no `@Autowired`.
The service chooses whether to return the new event or read the original row.
Its nested `StoreResult` record carries the boolean outcome and event to the
controller; it is not a separate persistence model.

`insert` calls `jdbc.update` with six `?` placeholders and six values in column
order. These are parameters, not string concatenation: quotes and SQL-looking
text in `page` remain data. The driver binds UUID, integer, offset timestamp,
and strings, sends the command, and returns the affected-row count. The SQL is
`INSERT ... ON CONFLICT (event_id) DO NOTHING`: 1 means a new row, 0 means the
primary key already exists. PostgreSQL performs conflict handling atomically.
Other failures, such as a missing table or unavailable database, are not treated
as duplicates or 404s. See [PostgreSQL INSERT](https://www.postgresql.org/docs/17/sql-insert.html).

`findById` executes an explicit six-column `SELECT ... WHERE event_id = ?`.
Its row-mapping lambda reads each column by name using `getObject`, `getInt`, or
`getString` and constructs a `ClickEvent`. No reflection mapper or JPA is used.
The primary key guarantees at most one result. `Optional<ClickEvent>` represents
that result: present means found, empty means no row, rather than returning null.
The controller uses `ResponseEntity.of` to translate present/empty to 200/404.

There is no multi-statement transaction in this step. With the pool's default
auto-commit, each INSERT completes and commits before the DAO returns; the
optional duplicate lookup is a separate SELECT. If another client deletes that
row between the two statements, the service throws rather than claiming that
the submitted duplicate was stored.

## Request flow

1. Tomcat receives the request on port 8080; Spring MVC selects the route.
2. POST: Jackson converts JSON into `ClickEvent` and `@Valid` checks constraints.
   Invalid JSON or validation returns 400 before the controller method runs.
3. The controller calls the injected service, which calls `dao.insert`.
4. `JdbcTemplate` binds parameters and executes the INSERT through the pool and
   PostgreSQL driver. A new row produces 201/`true`; a duplicate causes the
   service to read the original and produces 200/`false`. Jackson writes the event.
5. GET: MVC converts the path to UUID, then controller → service → DAO runs the
   parameterized SELECT. The row mapper builds the event; Optional yields 200
   with JSON or 404 when absent.

## Verification

`./mvnw test` runs MVC tests with a mocked service, checking validation, inserted
and duplicate responses, GET, missing IDs, and malformed UUIDs. These tests do
not need PostgreSQL. The DAO test is skipped unless `JDBC_TEST_URL` is supplied:

```sh
export JDBC_TEST_URL="jdbc:postgresql://${POSTGRES_HOST:-127.0.0.1}:${POSTGRES_PORT:-5432}/${POSTGRES_DB}"
export JDBC_TEST_USER="$POSTGRES_USER"
export JDBC_TEST_PASSWORD="$POSTGRES_PASSWORD"
./mvnw test
```

That test uses a single PostgreSQL connection and a session-local temporary
`click_events` table that shadows the real table and disappears on disconnect.
It checks all mapped fields, timestamp instant, missing IDs, duplicate payload
preservation, and parameter binding with SQL-looking strings without changing
application rows. No JPA or Redis is involved.
