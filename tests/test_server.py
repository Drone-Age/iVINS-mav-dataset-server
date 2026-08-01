#!/usr/bin/env python3
"""Offline integration and security tests for Dataset Server v3."""

import hashlib
import os
import tempfile
import unittest
from pathlib import Path

import api_keys
import server


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Path(self.temporary.name) / "catalog.sqlite3"
        os.environ["IVINS_DATA_ROOT"] = self.temporary.name
        os.environ["IVINS_DATABASE"] = str(self.database)
        os.environ["IVINS_BAG_ROOT"] = str(Path(self.temporary.name) / "bags")
        os.environ["IVINS_REQUESTS_PER_MINUTE"] = "1000"
        os.environ["IVINS_AUTH_ATTEMPTS_PER_MINUTE"] = "1000"
        os.environ["IVINS_AUTH_FAILURES_PER_MINUTE"] = "1000"
        os.environ["IVINS_MAX_JSON_BYTES"] = "65536"
        os.environ["IVINS_MAX_UPLOAD_BYTES"] = str(50 * 1024**3)
        os.environ.pop("IVINS_API_KEY", None)
        server.rate_limiter.reset()
        self.key_id, self.token = api_keys.create_api_key("offline-test")
        self.client = server.app.test_client()
        self.auth = {"Authorization": f"Bearer {self.token}"}

    def tearDown(self):
        self.temporary.cleanup()

    def get(self, path, **kwargs):
        headers = {**self.auth, **kwargs.pop("headers", {})}
        return self.client.get(path, headers=headers, **kwargs)

    def create(self, data=b"artifact", dataset_id="iv.dev.4.ff.1", version="1"):
        sha = hashlib.sha256(data).hexdigest()
        response = self.client.post("/v1/uploads", headers=self.auth, json={
            "dataset_id": dataset_id, "format": "rosbag", "version": version,
            "size": len(data), "sha256": sha,
            "metadata": {
                "title": "iVINS Dev 4 Flight Field 01",
                "description": "Public flight recording.",
                "family": "ivins", "profile": "dev_04",
                "derivable_formats": ["rosbag2"],
            },
        })
        self.assertIn(response.status_code, {200, 201}, response.json)
        return response.json["upload_id"], sha

    def test_health_is_minimal_and_all_v1_reads_require_a_key(self):
        health = self.client.get("/health")
        self.assertEqual(200, health.status_code)
        self.assertEqual("3.1.0", health.json["server_version"])
        self.assertTrue(health.json["key_store_ready"])
        self.assertEqual(401, self.client.get("/v1/catalog").status_code)
        self.assertEqual(200, self.get("/v1/catalog").status_code)

    def test_no_active_key_returns_503_and_health_remains_available(self):
        self.assertTrue(api_keys.revoke_api_key(self.key_id))
        self.assertFalse(self.client.get("/health").json["key_store_ready"])
        response = self.client.get("/v1/catalog", headers=self.auth)
        self.assertEqual(503, response.status_code)

    def test_key_is_hashed_and_revocation_is_immediate(self):
        with api_keys.connection() as db:
            row = db.execute(
                "SELECT secret_digest FROM api_keys WHERE id=?", (self.key_id,)
            ).fetchone()
        self.assertEqual(64, len(row["secret_digest"]))
        self.assertNotEqual(self.token, row["secret_digest"])
        self.assertNotIn(self.token.encode(), self.database.read_bytes())
        api_keys.create_api_key("fallback-admin")
        self.assertTrue(api_keys.revoke_api_key(self.key_id))
        self.assertEqual(401, self.client.get("/v1/catalog", headers=self.auth).status_code)

    def test_rate_limit_returns_429_and_retry_after(self):
        os.environ["IVINS_REQUESTS_PER_MINUTE"] = "2"
        server.rate_limiter.reset()
        self.assertEqual(200, self.get("/v1/catalog").status_code)
        self.assertEqual(200, self.get("/v1/catalog").status_code)
        response = self.get("/v1/catalog")
        self.assertEqual(429, response.status_code)
        self.assertGreaterEqual(int(response.headers["Retry-After"]), 1)

    def test_json_size_limit_and_security_headers(self):
        os.environ["IVINS_MAX_JSON_BYTES"] = "8"
        response = self.client.post(
            "/v1/uploads", headers=self.auth, json={"too": "large"}
        )
        self.assertEqual(413, response.status_code)
        health = self.client.get("/health")
        self.assertEqual("nosniff", health.headers["X-Content-Type-Options"])
        self.assertEqual("no-store", health.headers["Cache-Control"])
        self.assertIn("frame-ancestors 'none'", health.headers["Content-Security-Policy"])

    def test_upload_publish_snapshot_and_range_download(self):
        data = b"0123456789"
        upload_id, sha = self.create(data)
        verified = self.client.put(
            f"/v1/uploads/{upload_id}/content", headers=self.auth, data=data
        )
        self.assertEqual(200, verified.status_code, verified.json)
        published = self.client.post(
            f"/v1/uploads/{upload_id}/publish", headers=self.auth
        )
        self.assertEqual(200, published.status_code, published.json)
        with server.database() as db:
            stored = Path(db.execute("SELECT storage_path FROM artifacts").fetchone()[0])
        self.assertEqual(Path(os.environ["IVINS_BAG_ROOT"]).resolve(), stored.parent)
        self.assertEqual(stored.parent, stored.resolve().parent)
        snapshot = self.get("/v1/catalog").json
        self.assertEqual("1.0", snapshot["schema_version"])
        self.assertEqual(sha, snapshot["datasets"][0]["artifacts"][0]["sha256"])
        self.assertNotIn("storage_path", str(snapshot))
        download = self.get(
            "/v1/datasets/iv.dev.4.ff.1/artifacts/rosbag/1/download",
            headers={"Range": "bytes=2-5"},
        )
        self.assertEqual(206, download.status_code)
        self.assertEqual(b"2345", download.data)
        download.close()

    def test_checksum_mismatch_never_publishes(self):
        upload_id, _ = self.create(b"right")
        response = self.client.put(
            f"/v1/uploads/{upload_id}/content", headers=self.auth, data=b"wrong"
        )
        self.assertEqual(422, response.status_code)
        self.assertEqual(
            409,
            self.client.post(
                f"/v1/uploads/{upload_id}/publish", headers=self.auth
            ).status_code,
        )
        self.assertEqual([], self.get("/v1/catalog").json["datasets"])

    def test_content_length_must_match_declared_size(self):
        upload_id, _ = self.create(b"expected")
        response = self.client.put(
            f"/v1/uploads/{upload_id}/content", headers=self.auth, data=b"short"
        )
        self.assertEqual(422, response.status_code)
        self.assertEqual("size_mismatch", response.json["error"]["code"])

    def test_upload_limit_is_enforced_before_streaming(self):
        os.environ["IVINS_MAX_UPLOAD_BYTES"] = "4"
        response = self.client.post("/v1/uploads", headers=self.auth, json={
            "dataset_id": "safe.id",
            "format": "rosbag",
            "version": "1",
            "size": 5,
            "sha256": hashlib.sha256(b"12345").hexdigest(),
            "metadata": {},
        })
        self.assertEqual(413, response.status_code)
        self.assertEqual("payload_too_large", response.json["error"]["code"])

    def test_immutable_version_and_idempotent_session(self):
        upload_id, _ = self.create()
        again, _ = self.create()
        self.assertEqual(upload_id, again)
        self.client.put(
            f"/v1/uploads/{upload_id}/content", headers=self.auth, data=b"artifact"
        )
        self.client.post(f"/v1/uploads/{upload_id}/publish", headers=self.auth)
        body = {
            "dataset_id": "iv.dev.4.ff.1", "format": "rosbag", "version": "1",
            "size": 0, "sha256": hashlib.sha256(b"").hexdigest(), "metadata": {},
        }
        self.assertEqual(
            409,
            self.client.post("/v1/uploads", headers=self.auth, json=body).status_code,
        )

    def test_private_metadata_and_traversal_are_rejected(self):
        body = {
            "dataset_id": "../escape", "format": "rosbag", "version": "1",
            "size": 0, "sha256": hashlib.sha256(b"").hexdigest(), "metadata": {},
        }
        self.assertEqual(
            400,
            self.client.post("/v1/uploads", headers=self.auth, json=body).status_code,
        )
        body["dataset_id"] = "safe.id"
        body["metadata"] = {"token": "do-not-leak"}
        response = self.client.post("/v1/uploads", headers=self.auth, json=body)
        self.assertEqual(400, response.status_code)
        self.assertNotIn("do-not-leak", response.get_data(as_text=True))
        body["metadata"] = {"links": [{"secret": "nested-do-not-leak"}]}
        response = self.client.post("/v1/uploads", headers=self.auth, json=body)
        self.assertEqual(400, response.status_code)
        self.assertNotIn("nested-do-not-leak", response.get_data(as_text=True))

    def test_snapshot_is_deterministic(self):
        upload_id, _ = self.create()
        self.client.put(
            f"/v1/uploads/{upload_id}/content", headers=self.auth, data=b"artifact"
        )
        self.client.post(f"/v1/uploads/{upload_id}/publish", headers=self.auth)
        self.assertEqual(self.get("/v1/catalog").json, self.get("/v1/catalog").json)


if __name__ == "__main__":
    unittest.main()
