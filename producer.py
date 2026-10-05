import json
import os
from datetime import datetime, timezone
from uuid import uuid4

import redis


def main():
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    event = {
        "event_id": str(uuid4()),
        "schema_version": 1,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "session_id": str(uuid4()),
        "page": "/",
        "element_id": "signup-button",
    }
    payload = json.dumps(event).encode("utf-8")

    with redis.Redis.from_url(redis_url, decode_responses=False) as client:
        entry_id = client.xadd("events:clicks:v1", {"payload": payload})

    print("event_id:", event["event_id"])
    print("stream_entry_id:", entry_id.decode("utf-8"))


if __name__ == "__main__":
    main()
