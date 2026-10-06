import json
import unittest
from unittest.mock import MagicMock, Mock, patch
from uuid import UUID

import psycopg
import redis
from pydantic import ValidationError

import init_db
import storage_consumer as storage


EVENT = {
    "event_id": "c46de8cb-9280-4db2-9b7e-d00e7c79cb68",
    "schema_version": 1,
    "occurred_at": "2026-10-06T12:00:00+02:00",
    "session_id": "session-1",
    "page": "/products",
    "element_id": "gumb-č",
}
FIELDS = {b"payload": json.dumps(EVENT, ensure_ascii=False).encode("utf-8")}


class StorageConsumerTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.connection = MagicMock()
        self.order = []
        transaction = self.connection.transaction.return_value
        transaction.__enter__.side_effect = lambda: self.order.append("BEGIN")
        transaction.__exit__.side_effect = self.finish_transaction
        self.connection.execute.side_effect = lambda *args: self.order.append("INSERT")
        self.client.xack.side_effect = lambda *args: self.order.append("XACK")

    def finish_transaction(self, exc_type, exc_value, traceback):
        self.order.append("ROLLBACK" if exc_type else "COMMIT")
        return False

    def test_commit_precedes_ack_and_sql_is_parameterized(self):
        storage.store_entry(self.client, self.connection, b"1-0", FIELDS)
        self.assertEqual(self.order, ["BEGIN", "INSERT", "COMMIT", "XACK"])
        sql, parameters = self.connection.execute.call_args.args
        self.assertIn("ON CONFLICT (event_id) DO NOTHING", sql)
        self.assertEqual(sql.count("%s"), 6)
        self.assertNotIn(EVENT["element_id"], sql)
        self.assertEqual(parameters[0], UUID(EVENT["event_id"]))
        self.assertIsNotNone(parameters[2].tzinfo)
        self.assertEqual(parameters[3:], ("session-1", "/products", "gumb-č"))
        self.client.xack.assert_called_once_with(storage.STREAM, storage.GROUP, b"1-0")

    def test_duplicate_is_also_committed_and_acknowledged(self):
        self.connection.execute.side_effect = None
        self.connection.execute.return_value.rowcount = 0
        storage.store_entry(self.client, self.connection, b"2-0", FIELDS)
        self.assertEqual(self.order, ["BEGIN", "COMMIT", "XACK"])

    def test_invalid_event_never_starts_transaction_or_acks(self):
        for fields in (
            {b"payload": b"{}"},
            {b"payload": b"not json"},
            {b"payload": json.dumps({**EVENT, "schema_version": 2}).encode()},
            {},
            {b"payload": b"\xff"},
        ):
            with self.subTest(fields=fields):
                with self.assertRaises((ValidationError, KeyError, UnicodeDecodeError)):
                    storage.store_entry(self.client, self.connection, b"1-0", fields)
        self.connection.transaction.assert_not_called()
        self.client.xack.assert_not_called()

    def test_failed_insert_rolls_back_without_ack(self):
        self.connection.execute.side_effect = psycopg.OperationalError("write failed")
        with self.assertRaises(psycopg.OperationalError):
            storage.store_entry(self.client, self.connection, b"1-0", FIELDS)
        self.assertEqual(self.order, ["BEGIN", "ROLLBACK"])
        self.client.xack.assert_not_called()

    def test_failed_commit_does_not_ack(self):
        self.connection.transaction.return_value.__exit__.side_effect = psycopg.OperationalError("commit failed")
        with self.assertRaises(psycopg.OperationalError):
            storage.store_entry(self.client, self.connection, b"1-0", FIELDS)
        self.client.xack.assert_not_called()

    def test_only_busygroup_is_ignored(self):
        storage.create_group(self.client)
        self.client.xgroup_create.assert_called_once_with(storage.STREAM, storage.GROUP, id="0", mkstream=True)
        self.client.xgroup_create.side_effect = redis.ResponseError("BUSYGROUP Consumer Group name already exists")
        storage.create_group(self.client)
        for message in ("ERR invalid ID", "WRONGTYPE wrong kind", "ERR BUSYGROUP", "BUSYGROUP_OTHER"):
            with self.subTest(message=message):
                self.client.xgroup_create.side_effect = redis.ResponseError(message)
                with self.assertRaises(redis.ResponseError):
                    storage.create_group(self.client)

    def test_pending_is_drained_before_reading_new_entries(self):
        self.client.xreadgroup.side_effect = [
            [(storage.STREAM.encode(), [(b"1-0", FIELDS)])],
            [(storage.STREAM.encode(), [(b"2-0", FIELDS)])],
            [(storage.STREAM.encode(), [])],
            [(storage.STREAM.encode(), [(b"3-0", FIELDS)])],
            redis.ConnectionError("stop test"),
        ]
        with self.assertRaises(redis.ConnectionError):
            storage.consume(self.client, self.connection, "worker-test")
        reads = self.client.xreadgroup.call_args_list
        self.assertEqual([call.args[2] for call in reads], [
            {storage.STREAM: cursor} for cursor in ("0", "1-0", "2-0", ">", ">")
        ])
        self.assertTrue(all(call.args[:2] == (storage.GROUP, "worker-test") for call in reads))
        self.assertEqual([call.kwargs["block"] for call in reads], [None, None, None, 2000, 2000])
        self.assertEqual(self.client.xack.call_count, 3)

    def test_failure_is_logged_and_stops_before_next_read(self):
        for failure in (ValidationError, psycopg.OperationalError):
            with self.subTest(failure=failure):
                client = Mock()
                fields = {b"payload": b"{}"} if failure is ValidationError else FIELDS
                client.xreadgroup.return_value = [(storage.STREAM.encode(), [(b"1-0", fields)])]
                self.connection.execute.side_effect = psycopg.OperationalError("write failed")
                with self.assertLogs(storage.logger, level="ERROR"):
                    with self.assertRaises(failure):
                        storage.consume(client, self.connection, "worker-1")
                client.xreadgroup.assert_called_once()
                client.xack.assert_not_called()

    def test_main_configuration_and_nonzero_exit_on_failure(self):
        for config, expected in (({}, "worker-1"), ({"CONSUMER_NAME": "worker-2"}, "worker-2")):
            with self.subTest(config=config), patch.dict("os.environ", {"DATABASE_URL": "postgresql://example", **config}, clear=True):
                with patch.object(storage.redis.Redis, "from_url") as factory, patch.object(storage.psycopg, "connect") as connect, patch.object(storage, "consume", side_effect=psycopg.OperationalError("stop")) as consume:
                    with self.assertLogs(storage.logger, level="ERROR"):
                        self.assertEqual(storage.main(), 1)
                    self.assertEqual(consume.call_args.args[2], expected)
                    connect.assert_called_once_with("postgresql://example", autocommit=True, connect_timeout=5)
                    self.assertEqual(factory.call_args.kwargs["retry"].get_retries(), 0)

    def test_initialization_commits_before_reporting_success(self):
        order = []
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.execute.side_effect = lambda *args: order.append("CREATE")
        connection.__exit__.side_effect = lambda *args: order.append("COMMIT")
        with patch.dict("os.environ", {"DATABASE_URL": "postgresql://example"}), patch.object(init_db.psycopg, "connect", return_value=connection), patch("builtins.print", side_effect=lambda *args: order.append("PRINT")):
            init_db.main()
        self.assertEqual(order, ["CREATE", "COMMIT", "PRINT"])
        connection.execute.assert_called_once_with(init_db.CREATE_TABLE)


if __name__ == "__main__":
    unittest.main()
