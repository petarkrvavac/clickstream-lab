# Standalone Java 21 memory demo

`MemoryDemo.java` has no package or external dependencies and is outside the
Spring Boot source tree. It runs a finite loop, allocates exactly 500 payload
arrays of `256 * 1024` bytes each, fills each array, and sums every byte as an
unsigned value. Both modes allocate **125 MiB of payload in total**. JVM/library
allocations, array headers, and the list are additional overhead.

## Build and run

From `java-lab`, run each mode in its own JVM process:

```sh
mkdir -p target/memory-demo
javac -d target/memory-demo examples/MemoryDemo.java

java -Xms32m -Xmx64m '-Xlog:gc*' \
  -cp target/memory-demo MemoryDemo transient

java -Xms32m -Xmx256m '-Xlog:gc*' \
  -cp target/memory-demo MemoryDemo retained
```

Supply exactly one argument, `transient` or `retained`; other arguments print
usage and exit. Every 50 iterations the demo prints mode, iteration count,
cumulative payload MiB, approximate used heap, current heap size, maximum heap
size, and retained-array count. The final summary prints the processing checksum
and a second checksum from reading all retained arrays.

## What to understand

- A `byte[]` is an object allocated on the Java heap.
- An object reachable through strong references from a live execution path must
  remain available. Without such references, these arrays become eligible for
  garbage collection; eligibility does not mean immediate collection.
- Transient mode processes an array and keeps no references to previous arrays.
  Cumulative allocation grows even when old arrays are collected. Allocated
  bytes over time and currently live objects are different quantities.
- Retained mode puts every array into an `ArrayList<byte[]>`. The list stores
  references, so keeping the list reachable keeps its arrays reachable. The
  demo reads every retained array again for the final checksum, then calls
  `Reference.reachabilityFence(retained)` after printing the summary to ensure
  the list and its arrays remain reachable through that point.
- Transient heap usage can rise as allocations accumulate and fall after GC.
  It need not stay flat, and samples every 50 iterations can miss the peaks.
  The JVM can also grow its current heap without reaching the configured maximum.
- GC timing and exact readings vary with collector behavior, JVM version, JIT
  compilation, heap sizing, machine resources, and other allocations.
- `Runtime.totalMemory() - Runtime.freeMemory()` is an approximate used-heap
  reading, not an exact count of live payload bytes. `totalMemory()` describes
  the current heap size, and `maxMemory()` its maximum. These are **heap readings,
  not total Java process memory**. See [Java 21 Runtime](https://docs.oracle.com/en/java/javase/21/docs/api/java.base/java/lang/Runtime.html).
- Retained mode deliberately gets a larger heap: it must keep 125 MiB of
  payload plus overhead. This bounded exercise is **not a performance benchmark**.
  It does not call `System.gc()`, sleep, or intentionally exhaust the heap.

## Observed run

Both commands were compiled/run successfully using OpenJDK **21.0.12.1** on
2026-10-07, in separate JVM processes. Both exited with status 0. Both logs
reported the G1 collector. Selected actual readings (MiB):

| Iteration | Cumulative payload | Transient used heap | Retained used heap |
| --- | --- | --- | --- |
| 50 | 12.50 | 2.83 | 17.79 |
| 100 | 25.00 | 2.12 | 33.80 |
| 150 | 37.50 | 18.62 | 50.75 |
| 500 | 125.00 | 5.63 | 167.25 |

At iteration 500, transient mode retained 0 arrays, with current heap 37 MiB
and maximum heap 64 MiB. Retained mode held 500 arrays, with current heap
230 MiB and maximum heap 256 MiB. Approximate heap usage includes other objects
and collector allocation/layout overhead; it is not just the payload sum.

Both processing checksums were `16391864320`. Retained mode's final reread also
produced `16391864320`; transient mode's retained checksum was 0 because its
list was empty. A transient GC line showed `19M->1M(34M)`: used heap dropped
from roughly 19 MiB to 1 MiB while heap capacity was 34 MiB. A retained GC line
showed `59M->59M(91M)`, illustrating that GC cannot discard the kept arrays.
These are observations from this run, not expected fixed readings.

## JVM options and the existing Spring Boot JAR

`-Xms32m` sets the initial/minimum heap size to 32 MiB. `-Xmx64m` sets the maximum
heap size to 64 MiB. `'-Xlog:gc*'` enables GC-related logging, including collection
details and heap information; quotes protect the wildcard from the shell.
Logs appear alongside the demo's output. See the [Java 21 launcher options](https://docs.oracle.com/en/java/javase/21/docs/specs/man/java.html).

**Xmx limits the heap, not total Java process memory.** Thread stacks, metaspace,
compiled code, direct buffers, and other native allocations are outside that
heap limit. A process using `-Xmx256m` can therefore consume more than 256 MiB.

The actual existing executable JAR filename was confirmed as
`target/java-lab-0.0.1-SNAPSHOT.jar`; its archive contains the Spring Boot
application and dependencies. From `java-lab`, build and run it with:

```sh
./mvnw package
java -Xms128m -Xmx256m '-Xlog:gc*' \
  -jar target/java-lab-0.0.1-SNAPSHOT.jar
```

Before starting the JAR, **stop the previously running server** so port 8080 is
free, and make the existing database environment variables available in the
launching shell: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and
`POSTGRES_PORT=5433` for the local published port (`POSTGRES_HOST` defaults to
`127.0.0.1`). Spring Boot does not automatically load the repository's `.env`.
PostgreSQL and the existing `click_events` table must be available.

For a trusted `.env` containing shell assignments, export its values from the
repository root before entering `java-lab`:

```sh
set -a
. ./.env
set +a
cd java-lab
```

The commands above document how to build and launch the application. This
exercise ran only the standalone demo; it did not start another Spring server
or rebuild the existing JAR.
