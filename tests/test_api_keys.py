#!/usr/bin/env python3
"""Tests for the server-local API key CLI."""

import io
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import api_keys


class ApiKeyCliTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / "catalog.sqlite3"
        os.environ["IVINS_DATA_ROOT"] = self.temporary.name
        os.environ["IVINS_DATABASE"] = str(self.database)

    def tearDown(self):
        self.temporary.cleanup()

    def run_cli(self, *arguments):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = api_keys.main(list(arguments))
        return code, output.getvalue(), errors.getvalue()

    def test_create_list_revoke_lifecycle(self):
        code, output, errors = self.run_cli("create", "--name", "release-admin")
        self.assertEqual(0, code, errors)
        created = json.loads(output)
        token, key_id = created["api_key"], created["key_id"]
        self.assertEqual("admin", created["role"])
        self.assertTrue(token.startswith(f"dsm_{key_id}_"))

        code, output, errors = self.run_cli("list")
        self.assertEqual(0, code, errors)
        listed = json.loads(output)
        self.assertEqual(key_id, listed["keys"][0]["id"])
        self.assertEqual("admin", listed["keys"][0]["role"])
        self.assertNotIn("api_key", output)
        self.assertNotIn(token.encode(), self.database.read_bytes())

        code, output, errors = self.run_cli("revoke", key_id)
        self.assertEqual(0, code, errors)
        self.assertEqual(key_id, json.loads(output)["revoked"])
        self.assertIsNone(api_keys.verify_api_key(token))

    def test_rejects_unsafe_name(self):
        code, _, errors = self.run_cli("create", "--name", "../unsafe")
        self.assertEqual(2, code)
        self.assertIn("safe characters", errors)

    def test_migrates_v2_key_table_to_admin_role(self):
        database = sqlite3.connect(self.database)
        database.execute(
            "CREATE TABLE api_keys (id TEXT PRIMARY KEY,name TEXT NOT NULL,"
            "secret_digest TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
            "revoked_at TEXT)"
        )
        database.execute(
            "INSERT INTO api_keys(id,name,secret_digest) VALUES(?,?,?)",
            ("0123456789abcdef", "legacy", "0" * 64),
        )
        database.commit()
        database.close()

        keys = api_keys.list_api_keys()
        self.assertEqual("admin", keys[0]["role"])

    def test_cli_creates_scoped_key(self):
        code, output, errors = self.run_cli(
            "create", "--name", "download-client", "--role", "user"
        )
        self.assertEqual(0, code, errors)
        created = json.loads(output)
        self.assertEqual("user", created["role"])
        identity = api_keys.authenticate_api_key(created["api_key"])
        self.assertEqual("user", identity.role)

    def test_migrates_reader_and_publisher_roles_to_user(self):
        api_keys.create_api_key("old-reader", "admin")
        with api_keys.connection() as database:
            database.execute("UPDATE api_keys SET role='reader'")
        self.assertEqual("user", api_keys.list_api_keys()[0]["role"])

    def test_legacy_ivins_token_remains_valid(self):
        key_id, token = api_keys.create_api_key("compatibility")
        legacy_token = token.replace("dsm_", "ivins_", 1)
        with api_keys.connection() as database:
            database.execute(
                "UPDATE api_keys SET secret_digest=? WHERE id=?",
                (api_keys._digest(legacy_token), key_id),
            )
        self.assertEqual("admin", api_keys.authenticate_api_key(legacy_token).role)


if __name__ == "__main__":
    unittest.main()
