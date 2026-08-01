#!/usr/bin/env python3
"""Tests for the server-local API key CLI."""

import io
import json
import os
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
        self.assertTrue(token.startswith(f"ivins_{key_id}_"))

        code, output, errors = self.run_cli("list")
        self.assertEqual(0, code, errors)
        listed = json.loads(output)
        self.assertEqual(key_id, listed["keys"][0]["id"])
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


if __name__ == "__main__":
    unittest.main()
