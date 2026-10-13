import logging
import os

import psycopg
import redis
from redis.backoff import NoBackoff
from redis.retry import Retry

from app.main import ClickEvent


STREAM = "events:clicks:v1"
GROUP = "click-storage"
INSERT_EVENT = """
INSERT INTO click_events
    (event_id, schema_version, occurred_at, session_id, page, element_id)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (event_id) DO NOTHING
"""
logger = logging.getLogger(__name__)


def create_group(client):
    try:
        client.xgroup_create(STREAM, GROUP, id="0", mkstream=True)
    except redis.exceptions.ResponseError as exc:
        if str(exc).partition(" ")[0] != "BUSYGROUP":
            raise


def store_entry(client, connection, entry_id, fields):
    event = ClickEvent.model_validate_json(fields[b"payload"].decode("utf-8"))
    with connection.transaction():
        connection.execute(
            INSERT_EVENT,
            (
                event.event_id,
                event.schema_version,
                event.occurred_at,
                event.session_id,
                event.page,
                event.element_id,
            ),
        )
    # COMMIT completes when the transaction context exits, before XACK.
    client.xack(STREAM, GROUP, entry_id)


def consume(client, connection, consumer_name):
    create_group(client)
    cursor = "0"
    while True:
        response = client.xreadgroup(
            GROUP,
            consumer_name,
            {STREAM: cursor},
            count=1,
            block=2000 if cursor == ">" else None,
        )
        if not response or not response[0][1]:
            # An explicit ID reads only this consumer's pending entries.
            # Once exhausted, '>' reads entries never delivered to the group.
            cursor = ">"
            continue
        for _, entries in response:
            for entry_id, fields in entries:
                try:
                    store_entry(client, connection, entry_id, fields)
                except Exception:
                    logger.exception("Failed to handle stream entry %r", entry_id)
                    raise
                if cursor != ">":
                    cursor = entry_id.decode("utf-8")


def main():
    logging.basicConfig(level=logging.INFO)
    consumer_name = os.environ.get("CONSUMER_NAME", "worker-1")
    try:
        with redis.Redis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            decode_responses=False,
            socket_connect_timeout=2.0,
            socket_timeout=5.0,
            retry=Retry(NoBackoff(), 0),
        ) as client, psycopg.connect(
            os.environ["DATABASE_URL"], autocommit=True, connect_timeout=5
        ) as connection:
            consume(client, connection, consumer_name)
    except KeyboardInterrupt:
        logger.info("Storage consumer stopped.")
    except Exception:
        logger.exception("Storage consumer stopped after an error.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
