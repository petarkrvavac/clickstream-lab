# Local backend services in WSL

Python runs directly in WSL through VS Code. Docker Desktop on Windows runs
Redis and PostgreSQL through its WSL integration. This project provides only
those two services, with explicit image versions and no custom networks.

## Start

Start Docker Desktop and enable WSL integration for your distribution. In the
VS Code WSL terminal, from this directory:

```bash
cp .env.example .env
```

Edit `.env` and replace the example password, then run:

```bash
docker compose config --quiet
docker compose up -d
docker compose ps
```

The first start downloads the images and initializes PostgreSQL. A running
container may still be starting its database; inspect the logs if a connection
is initially refused:

```bash
docker compose logs redis postgres
```

## Ports and Python connection addresses

A port mapping has the form `host_address:host_port:container_port`.
`127.0.0.1:5432:5432`, for example, forwards local port 5432 to PostgreSQL's
port 5432 inside its container. Both services publish only on the loopback
address, keeping these ports local to your machine.

With Docker Desktop WSL integration, use these addresses from Python running
directly in WSL:

| Service | Host | Port | Connection settings |
| --- | --- | --- | --- |
| Redis | `127.0.0.1` | `6379` | Database `0`; URL `redis://127.0.0.1:6379/0` |
| PostgreSQL | `127.0.0.1` | `5432` | Database, user and password from `.env` |

The names `redis` and `postgres` are Docker service names, resolved between
containers on Compose's automatically created default network. A Python
process running directly in WSL uses the published host ports instead.
If a host port is already occupied, change the middle number in its mapping
and use that new port from Python; keep the container port unchanged.

## Environment variables

Compose reads `.env` and substitutes its values into the PostgreSQL service's
`environment` settings. Missing or empty values cause configuration validation
to fail. Shell variables with the same names override values in `.env`.

- `POSTGRES_DB` names the database created during initialization.
- `POSTGRES_USER` names the initial PostgreSQL user (a database superuser).
- `POSTGRES_PASSWORD` sets that user's password.

These initialization settings apply when the PostgreSQL data volume is empty.
Editing `.env` later does not rename an existing database or user, or change
their stored password. Make those changes through PostgreSQL itself.

Compose does not automatically load `.env` into a Python process running in
WSL. Supply the corresponding connection settings to Python yourself, or
explicitly load the file in your future application. `.env` is ignored by Git;
`.env.example` is the shareable template. The Python virtual environment and
Python cache files are also ignored.

## Volumes and persistence

Named volumes store data outside the containers, managed by Docker Desktop:

- `redis_data` mounts at `/data` and holds Redis persistence files.
- `postgres_data` mounts at `/var/lib/postgresql/data` and holds PostgreSQL's
  database files, including its write-ahead log for crash recovery.

Compose normally prefixes volume names with the project name, so the actual
names may look like `click-monitoring_redis_data`. Reuse the same project name
to reconnect to the same volumes.

Redis AOF (append-only file) persistence is enabled. Redis records write
operations and replays them when it restarts. `appendfsync everysec` flushes
the log to disk about once per second; a crash can lose roughly the last
second of writes. PostgreSQL persists committed data in its data directory.
Volumes survive container recreation, but they are not backups.

To stop and remove the containers while retaining both volumes:

```bash
docker compose down
```

Running `docker compose up -d` again reuses the stored data. The `--volumes`
(`-v`) option on `docker compose down` deletes these volumes and their data.

## References

- [Official Redis image versions](https://github.com/docker-library/official-images/blob/master/library/redis)
- [Official PostgreSQL image versions](https://github.com/docker-library/official-images/blob/master/library/postgres)
- [PostgreSQL image initialization and storage](https://hub.docker.com/_/postgres)
- [Compose environment variable interpolation](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)
- [Compose service and port settings](https://docs.docker.com/reference/compose-file/services/)
- [Redis persistence](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/)
