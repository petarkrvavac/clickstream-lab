import os

import psycopg


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS click_events (
    event_id UUID PRIMARY KEY,
    schema_version INTEGER NOT NULL CHECK (schema_version = 1),
    occurred_at TIMESTAMPTZ NOT NULL,
    session_id VARCHAR(128) NOT NULL CHECK (length(session_id) > 0),
    page VARCHAR(2048) NOT NULL CHECK (length(page) > 0),
    element_id VARCHAR(128) NOT NULL CHECK (length(element_id) > 0)
)
"""


def main():
    with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=5) as connection:
        connection.execute(CREATE_TABLE)
    # The connection context commits the DDL before reaching this line.
    print("click_events table initialized.")


if __name__ == "__main__":
    main()
