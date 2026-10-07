# Java click-event lab — step 1

This independent Java 21 application accepts `POST /lab/events/click` on port
8080, validates the existing six-field event, and returns it with HTTP 200.
Invalid JSON or validation failures return HTTP 400 (Spring MVC's default).
It has three production classes: the application, the event record, and the
controller. There are no service or repository layers and no Redis or database
operations.

## Version and running

Spring Boot **3.5.16** is a released Spring Boot 3 version, available from Maven
Central. It is the final OSS release of the 3.5 generation and fits the requested
3.x learning baseline and Java 21. This is a pinned release, not a snapshot or
milestone. See the [official release announcement](https://spring.io/blog/2026/06/25/spring-boot-3-5-16-available-now/).

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

The response body contains the same six fields. Surrounding whitespace in the
three strings is stripped. UUID and timestamp values are serialized as JSON
strings; timestamp formatting may be normalized while preserving its offset.

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
- `spring-boot-starter-jdbc`: Spring JDBC and HikariCP connection pooling for a
  later lesson. Datasource auto-configuration is explicitly excluded in
  `application.properties`; the application needs no database credentials and
  creates no datasource now.
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

## Request flow

1. Embedded Tomcat receives the HTTP request on port 8080.
2. Spring MVC matches POST `/lab/events/click` to the controller method.
3. Jackson reads JSON into the record, converts UUID/timestamp values, and runs
   the record constructor's whitespace stripping. Invalid conversion returns 400.
4. `@Valid` checks the constraints. A failed constraint returns 400 before the
   controller runs.
5. The controller returns the validated record directly. Jackson serializes it
   into JSON and Spring MVC sends HTTP 200.

The integration tests load the real application configuration with MockMvc and
exercise valid echoes, strict types, missing/null fields, unknown fields,
invalid UUIDs, missing timestamp offsets, whitespace, and string boundaries.
