"""Offline tests for the LAN API."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ["IVINS_API_KEY"] = "offline-test-key"

import server


ROWS = [
    {
        "standard_id": "x.test",
        "dataset": "fixture",
        "format": "rosbag",
        "registry_status": "verified",
        "local_status": "missing",
        "path": None,
    },
    {
        "standard_id": "x.test",
        "dataset": "fixture",
        "format": "rosbag2",
        "registry_status": "not-published",
        "local_status": "missing",
        "path": None,
    },
    {
        "standard_id": "x.catalog",
        "dataset": "fixture",
        "format": "rosbag",
        "registry_status": "catalog-only",
        "local_status": "missing",
        "path": None,
    },
    {
        "standard_id": "x.import",
        "dataset": "fixture",
        "format": "rosbag",
        "registry_status": "local-import",
        "local_status": "missing",
        "path": None,
    },
]


class ImmediateThread:
    def __init__(self, target, args, daemon):
        self.target = target
        self.args = args

    def start(self):
        self.target(*self.args)


class ServerTest(unittest.TestCase):
    def setUp(self):
        server.jobs.clear()
        self.client = server.app.test_client()
        self.headers = {"X-API-Key": "offline-test-key"}

    def test_health_and_authentication(self):
        self.assertEqual(401, self.client.get("/health").status_code)
        response = self.client.get("/health", headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual("ok", response.json["status"])

    @patch("server.run_catalog", return_value=(0, ROWS))
    def test_registry_lookup_and_missing(self, _run):
        response = self.client.get("/v1/datasets/x.test", headers=self.headers)
        self.assertEqual(200, response.status_code)
        self.assertEqual("fixture", response.json["dataset"])
        missing = self.client.get("/v1/datasets/unknown", headers=self.headers)
        self.assertEqual(404, missing.status_code)

    @patch("server.run_catalog", return_value=(0, ROWS))
    def test_catalog_only_fetch_is_rejected(self, _run):
        response = self.client.post(
            "/v1/datasets/x.catalog/fetch",
            headers=self.headers,
            json={"format": "rosbag"},
        )
        self.assertEqual(409, response.status_code)
        self.assertEqual("catalog-only", response.json["registry_status"])

    def test_fetch_job_state_with_mocked_catalog(self):
        calls = []

        def operation(arguments):
            calls.append(arguments)
            if arguments == ["status"]:
                return 0, ROWS
            return 0, {"standard_id": "x.test", "format": "rosbag", "sha256": "fixture"}

        with patch("server.run_catalog", side_effect=operation), patch(
            "server.threading.Thread", ImmediateThread
        ):
            response = self.client.post(
                "/v1/datasets/x.test/fetch",
                headers=self.headers,
                json={"format": "rosbag"},
            )
        self.assertEqual(202, response.status_code)
        job_id = response.json["job_id"]
        state = self.client.get(f"/v1/jobs/{job_id}", headers=self.headers)
        self.assertEqual("completed", state.json["state"])
        self.assertIn(["fetch", "x.test", "--format", "rosbag"], calls)

    def test_range_download(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            artifact = root / "datasets" / "fixture" / "x.test" / "rosbag" / "data.bag"
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b"0123456789")
            previous = server.RAW_ROOT
            server.RAW_ROOT = root
            try:
                with patch(
                    "server.run_catalog",
                    return_value=(0, {"local_status": "available", "path": str(artifact)}),
                ):
                    response = self.client.get(
                        "/v1/datasets/x.test/artifacts/rosbag/download",
                        headers={**self.headers, "Range": "bytes=2-5"},
                    )
                    self.assertEqual(206, response.status_code)
                    self.assertEqual(b"2345", response.data)
                    self.assertEqual("bytes 2-5/10", response.headers["Content-Range"])
                    response.close()
            finally:
                server.RAW_ROOT = previous

    def test_authenticated_local_ingest_job(self):
        with tempfile.TemporaryDirectory() as temporary:
            import_root = Path(temporary).resolve()
            source = import_root / "flight" / "data.bag"
            source.parent.mkdir()
            source.write_bytes(b"ingest fixture")
            previous_root = server.IMPORT_ROOT
            previous_host = os.environ.get("IMPORT_HOST_ROOT")
            server.IMPORT_ROOT = import_root
            os.environ["IMPORT_HOST_ROOT"] = str(import_root)
            calls = []

            def operation(arguments):
                calls.append(arguments)
                if arguments == ["status"]:
                    return 0, ROWS
                return 0, {"standard_id": "x.import", "import_mode": "copied"}

            try:
                with patch("server.run_catalog", side_effect=operation), patch(
                    "server.threading.Thread", ImmediateThread
                ):
                    response = self.client.post(
                        "/v1/datasets/x.import/import-local",
                        headers=self.headers,
                        json={"format": "rosbag", "source_path": str(source)},
                    )
            finally:
                server.IMPORT_ROOT = previous_root
                if previous_host is None:
                    os.environ.pop("IMPORT_HOST_ROOT", None)
                else:
                    os.environ["IMPORT_HOST_ROOT"] = previous_host
            self.assertEqual(202, response.status_code)
            job_id = response.json["job_id"]
            state = self.client.get(f"/v1/jobs/{job_id}", headers=self.headers)
            self.assertEqual("completed", state.json["state"])
            self.assertEqual("local-import", state.json["operation"])
            self.assertTrue(any(call[0] == "import-local" for call in calls))


if __name__ == "__main__":
    unittest.main()
