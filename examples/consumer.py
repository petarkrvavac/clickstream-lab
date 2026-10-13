import json
import os

import redis


def main():
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    last_id = "0-0"

    try:
        with redis.Redis.from_url(redis_url, decode_responses=False) as client:
            while True:
                response = client.xread(
                    {"events:clicks:v1": last_id}, count=10, block=2000
                )
                for stream_name, entries in response:
                    for entry_id, fields in entries:
                        event = json.loads(fields[b"payload"].decode("utf-8"))
                        print(entry_id.decode("utf-8"), event)
                        last_id = entry_id
    except KeyboardInterrupt:
        print("Consumer stopped.")


if __name__ == "__main__":
    main()
