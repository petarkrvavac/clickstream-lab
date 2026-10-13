import json
import unittest
from unittest.mock import MagicMock, Mock, patch

import psycopg
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError, TimeoutError

from app.main import app


EVENT = {
    "event_id": "c46de8cb-9280-4db2-9b7e-d00e7c79cb68",
    "schema_version": 1,
    "occurred_at": "2026-10-06T12:00:00+02:00",
    "session_id": "session-1",
    "page": "/products",
    "element_id": "gumb-č",
}


class ClickEndpointTests(unittest.TestCase):
    def setUp(self):
        self.redis = Mock()
        self.redis.xadd.return_value = b"1234567890-0"
        self.factory = patch("app.main.redis.Redis.from_url", return_value=self.redis)
        self.factory_mock = self.factory.start()
        self.addCleanup(self.factory.stop)
        self.client = TestClient(app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def test_publishes_utf8_json_and_returns_202(self):
        response = self.client.post("/events/click", json=EVENT)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {
            "event_id": EVENT["event_id"], "stream_entry_id": "1234567890-0"
        })
        self.redis.xadd.assert_called_once()
        stream, fields = self.redis.xadd.call_args.args
        self.assertEqual(stream, "events:clicks:v1")
        self.assertEqual(set(fields), {"payload"})
        self.assertIsInstance(fields["payload"], bytes)
        self.assertIn("č".encode("utf-8"), fields["payload"])
        self.assertEqual(json.loads(fields["payload"].decode("utf-8")), EVENT)

    def test_invalid_events_return_422_without_publishing(self):
        invalid = [
            ("event_id", "invalid"),
            ("occurred_at", "2026-10-06T12:00:00"),
            ("occurred_at", "invalid"),
            ("schema_version", 2),
            ("schema_version", True),
            ("schema_version", 1.0),
            ("schema_version", "1"),
        ]
        for field, limit in (("session_id", 128), ("page", 2048), ("element_id", 128)):
            invalid.extend((field, value) for value in ("", "  ", "x" * (limit + 1), 123))
        for field, value in invalid:
            with self.subTest(field=field, value=value):
                response = self.client.post("/events/click", json={**EVENT, field: value})
                self.assertEqual(response.status_code, 422)
        for field in EVENT:
            with self.subTest(missing=field):
                event = EVENT.copy()
                del event[field]
                self.assertEqual(self.client.post("/events/click", json=event).status_code, 422)
        self.assertEqual(self.client.post("/events/click", json={**EVENT, "extra": 1}).status_code, 422)
        self.redis.xadd.assert_not_called()

    def test_string_boundaries_and_whitespace(self):
        event = {**EVENT, "session_id": "x" * 128, "page": "x" * 2048, "element_id": "x" * 128}
        self.assertEqual(self.client.post("/events/click", json=event).status_code, 202)
        event = {**EVENT, "session_id": "  session-1  "}
        self.assertEqual(self.client.post("/events/click", json=event).status_code, 202)
        payload = self.redis.xadd.call_args.args[1]["payload"]
        self.assertEqual(json.loads(payload)["session_id"], "session-1")

    def test_redis_failures_return_503(self):
        for error in (ConnectionError("offline"), TimeoutError("timed out")):
            with self.subTest(error=type(error).__name__):
                self.redis.xadd.side_effect = error
                response = self.client.post("/events/click", json=EVENT)
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("stream_entry_id", response.json())

    def test_shared_client_timeouts_and_cleanup(self):
        options = self.factory_mock.call_args.kwargs
        self.assertEqual(options["socket_connect_timeout"], 2.0)
        self.assertEqual(options["socket_timeout"], 2.0)
        self.assertEqual(options["retry"].get_retries(), 0)
        self.client.post("/events/click", json=EVENT)
        self.client.post("/events/click", json=EVENT)
        self.factory_mock.assert_called_once()
        self.redis.close.assert_not_called()
        self.client.__exit__(None, None, None)
        self.redis.close.assert_called_once()

    def test_serves_html_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        for element_id in ("signup-button", "products-button", "contact-button"):
            self.assertIn(f'<button id="{element_id}"', response.text)
        self.redis.xadd.assert_not_called()

    def test_stats_returns_grouped_counts_and_closes_connection(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.execute.return_value.fetchall.return_value = [
            ("products-button", 3), ("signup-button", 2)
        ]
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://example"}), patch("app.main.psycopg.connect", return_value=connection) as connect:
            response = self.client.get("/stats/clicks")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [
            {"element_id": "products-button", "count": 3},
            {"element_id": "signup-button", "count": 2},
        ])
        connect.assert_called_once_with("postgresql://example", autocommit=True, connect_timeout=5)
        connection.execute.assert_called_once_with(
            "SELECT element_id, COUNT(*) FROM click_events GROUP BY element_id ORDER BY element_id"
        )
        connection.__exit__.assert_called_once()

    def test_empty_stats_returns_empty_list(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.execute.return_value.fetchall.return_value = []
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://example"}), patch("app.main.psycopg.connect", return_value=connection):
            response = self.client.get("/stats/clicks")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_stats_database_failures_return_503(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.execute.side_effect = psycopg.OperationalError("query failed")
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://example"}):
            with patch("app.main.psycopg.connect", side_effect=psycopg.OperationalError("offline")):
                self.assertEqual(self.client.get("/stats/clicks").status_code, 503)
            with patch("app.main.psycopg.connect", return_value=connection):
                response = self.client.get("/stats/clicks")
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("query failed", response.text)
        connection.__exit__.assert_called_once()
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(self.client.get("/stats/clicks").status_code, 503)


if __name__ == "__main__":
    unittest.main()
