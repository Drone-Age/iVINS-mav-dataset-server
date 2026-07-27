"""Offline integration and security tests for Dataset Server v1."""

import hashlib
import os
from pathlib import Path
import tempfile
import unittest

os.environ["IVINS_API_KEY"] = "offline-test-key"
import server


class ServerTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        os.environ["IVINS_DATA_ROOT"] = self.temporary.name
        os.environ["IVINS_DATABASE"] = str(Path(self.temporary.name) / "catalog.sqlite3")
        self.client = server.app.test_client()
        self.auth = {"Authorization": "Bearer offline-test-key"}

    def tearDown(self):
        self.temporary.cleanup()

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

    def test_public_reads_and_required_write_auth(self):
        self.assertEqual(200, self.client.get("/health").status_code)
        self.assertEqual(200, self.client.get("/v1/catalog").status_code)
        self.assertEqual(401, self.client.post("/v1/uploads", json={}).status_code)

    def test_upload_publish_snapshot_and_range_download(self):
        data = b"0123456789"
        upload_id, sha = self.create(data)
        verified = self.client.put(f"/v1/uploads/{upload_id}/content", headers=self.auth, data=data)
        self.assertEqual(200, verified.status_code, verified.json)
        published = self.client.post(f"/v1/uploads/{upload_id}/publish", headers=self.auth)
        self.assertEqual(200, published.status_code, published.json)
        snapshot = self.client.get("/v1/catalog").json
        self.assertEqual("1.0", snapshot["schema_version"])
        self.assertEqual(sha, snapshot["datasets"][0]["artifacts"][0]["sha256"])
        self.assertNotIn("storage_path", str(snapshot))
        download = self.client.get(
            "/v1/datasets/iv.dev.4.ff.1/artifacts/rosbag/1/download",
            headers={"Range": "bytes=2-5"},
        )
        self.assertEqual(206, download.status_code)
        self.assertEqual(b"2345", download.data)
        download.close()

    def test_checksum_mismatch_never_publishes(self):
        upload_id, _ = self.create(b"right")
        response = self.client.put(f"/v1/uploads/{upload_id}/content", headers=self.auth, data=b"wrong")
        self.assertEqual(422, response.status_code)
        self.assertEqual(409, self.client.post(f"/v1/uploads/{upload_id}/publish", headers=self.auth).status_code)
        self.assertEqual([], self.client.get("/v1/catalog").json["datasets"])

    def test_immutable_version_and_idempotent_session(self):
        upload_id, _ = self.create()
        again, _ = self.create()
        self.assertEqual(upload_id, again)
        self.client.put(f"/v1/uploads/{upload_id}/content", headers=self.auth, data=b"artifact")
        self.client.post(f"/v1/uploads/{upload_id}/publish", headers=self.auth)
        body = {
            "dataset_id": "iv.dev.4.ff.1", "format": "rosbag", "version": "1",
            "size": 0, "sha256": hashlib.sha256(b"").hexdigest(), "metadata": {},
        }
        self.assertEqual(409, self.client.post("/v1/uploads", headers=self.auth, json=body).status_code)

    def test_private_metadata_and_traversal_are_rejected(self):
        body = {
            "dataset_id": "../escape", "format": "rosbag", "version": "1",
            "size": 0, "sha256": hashlib.sha256(b"").hexdigest(), "metadata": {},
        }
        self.assertEqual(400, self.client.post("/v1/uploads", headers=self.auth, json=body).status_code)
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
        self.client.put(f"/v1/uploads/{upload_id}/content", headers=self.auth, data=b"artifact")
        self.client.post(f"/v1/uploads/{upload_id}/publish", headers=self.auth)
        self.assertEqual(self.client.get("/v1/catalog").json, self.client.get("/v1/catalog").json)


if __name__ == "__main__":
    unittest.main()
