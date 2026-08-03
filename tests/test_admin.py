#!/usr/bin/env python3
"""Integration tests for the role-aware Web administration surface."""

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

import api_keys
import server


class AdminWebTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.bags = self.root / "bags"
        self.database = self.root / "catalog.sqlite3"
        os.environ["IVINS_DATA_ROOT"] = str(self.root)
        os.environ["IVINS_BAG_ROOT"] = str(self.bags)
        os.environ["IVINS_DATABASE"] = str(self.database)
        os.environ["IVINS_REQUESTS_PER_MINUTE"] = "1000"
        os.environ["IVINS_AUTH_ATTEMPTS_PER_MINUTE"] = "1000"
        os.environ["IVINS_AUTH_FAILURES_PER_MINUTE"] = "1000"
        os.environ["IVINS_MAX_JSON_BYTES"] = "65536"
        os.environ["IVINS_MAX_UPLOAD_BYTES"] = str(50 * 1024**3)
        server.rate_limiter.reset()
        self.admin_id, self.admin_token = api_keys.create_api_key("admin-test", "admin")
        self.user_id, self.user_token = api_keys.create_api_key("user-test", "user")
        self.admin = {"Authorization": f"Bearer {self.admin_token}"}
        self.user = {"Authorization": f"Bearer {self.user_token}"}
        self.client = server.app.test_client()

    def tearDown(self):
        self.temporary.cleanup()

    def test_admin_page_is_static_safe_and_does_not_persist_key(self):
        page = self.client.get("/admin")
        self.assertEqual(200, page.status_code)
        self.assertIn("script-src 'self'", page.headers["Content-Security-Policy"])
        script = self.client.get("/static/admin.js")
        self.assertEqual(200, script.status_code)
        source = script.get_data(as_text=True)
        script.close()
        page.close()
        self.assertNotIn("localStorage", source)
        self.assertNotIn("sessionStorage", source)
        self.assertNotIn("document.cookie", source)
        self.assertNotIn("innerHTML", source)
        self.assertIn("adminDatasetEditMode", source)
        self.assertIn("adminFamilyFilter", source)
        self.assertIn("adminProfileFilter", source)

        html = self.client.get("/admin").get_data(as_text=True)
        self.assertIn("data-language-selector", html)
        self.assertIn('data-view="datasets"', html)
        self.assertIn("Backend 4.0.0", html)
        self.assertIn("Frontend 4.0.0", html)
        self.assertIn("Process 2.0.0", html)
        self.assertIn("Distribution 2.1.0", html)
        self.assertIn("Режим редагування", html)

    def test_roles_are_enforced_server_side(self):
        self.assertEqual(200, self.client.get("/v1/catalog", headers=self.user).status_code)
        self.assertEqual(
            403,
            self.client.post("/v1/uploads", headers=self.user, json={}).status_code,
        )
        self.assertEqual(
            400,
            self.client.post("/v1/uploads", headers=self.admin, json={}).status_code,
        )
        self.assertEqual(403, self.client.get("/admin/api/session", headers=self.user).status_code)
        session = self.client.get("/admin/api/session", headers=self.admin)
        self.assertEqual(200, session.status_code)
        self.assertEqual("admin", session.json["role"])
        overview = self.client.get("/admin/api/overview", headers=self.admin)
        self.assertEqual("4.0.0", overview.json["backend_version"])
        self.assertEqual("4.0.0", overview.json["frontend_version"])
        self.assertEqual("2.0.0", overview.json["process_version"])
        self.assertEqual("2.1.0", overview.json["distribution_version"])
        self.assertEqual(
            {"backend": "4.0.0", "frontend": "4.0.0", "process": "2.0.0", "distribution": "2.1.0"},
            overview.json["versions"],
        )

    def test_admin_creates_and_revokes_server_generated_key(self):
        response = self.client.post(
            "/admin/api/keys",
            headers=self.admin,
            json={"name": "web-user", "role": "user"},
        )
        self.assertEqual(201, response.status_code, response.json)
        token, key_id = response.json["api_key"], response.json["key_id"]
        self.assertEqual("user", api_keys.authenticate_api_key(token).role)
        self.assertNotIn(token.encode(), self.database.read_bytes())

        listed = self.client.get("/admin/api/keys", headers=self.admin).json
        listed_key = next(item for item in listed["items"] if item["id"] == key_id)
        self.assertEqual("user", listed_key["role"])
        self.assertNotIn("api_key", listed_key)

        revoked = self.client.post(
            f"/admin/api/keys/{key_id}/revoke", headers=self.admin
        )
        self.assertEqual(200, revoked.status_code)
        self.assertIsNone(api_keys.authenticate_api_key(token))

    def test_web_cannot_revoke_last_active_admin(self):
        self.assertTrue(api_keys.revoke_api_key(self.user_id))
        response = self.client.post(
            f"/admin/api/keys/{self.admin_id}/revoke", headers=self.admin
        )
        self.assertEqual(409, response.status_code)
        self.assertEqual("last_admin", response.json["error"]["code"])

    def test_admin_deletes_non_published_upload_and_staging_file(self):
        staging = self.root / "staging"
        staging.mkdir()
        staged = staging / "draft.tmp"
        staged.write_bytes(b"draft")
        with server.database() as database:
            database.execute(
                "INSERT INTO uploads "
                "(id,dataset_id,format,version,expected_size,expected_sha256,metadata,"
                "state,staged_path,actual_size,actual_sha256) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "draft-id", "safe.id", "rosbag", "1", 5,
                    hashlib.sha256(b"draft").hexdigest(), "{}", "verified",
                    str(staged), 5, hashlib.sha256(b"draft").hexdigest(),
                ),
            )
        response = self.client.delete("/admin/api/uploads/draft-id", headers=self.admin)
        self.assertEqual(200, response.status_code)
        self.assertFalse(staged.exists())
        with server.database() as database:
            self.assertIsNone(database.execute("SELECT 1 FROM uploads").fetchone())

    def insert_artifact(self, filename="managed.bag", dataset_id="managed.id"):
        self.bags.mkdir(exist_ok=True)
        path = self.bags / filename
        data = b"managed-bag"
        path.write_bytes(data)
        with server.database() as database:
            database.execute(
                "INSERT INTO artifacts "
                "(dataset_id,format,version,size,sha256,metadata,storage_path) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    dataset_id, "rosbag", "1", len(data), hashlib.sha256(data).hexdigest(),
                    json.dumps({"title": "Old title"}), str(path.resolve()),
                ),
            )
        return path

    def test_artifact_metadata_update_and_record_only_delete(self):
        path = self.insert_artifact()
        update = self.client.patch(
            "/admin/api/artifacts/managed.id/rosbag/1",
            headers=self.admin,
            json={"metadata": {"title": "New title", "description": "Reviewed"}},
        )
        self.assertEqual(200, update.status_code)
        self.assertEqual("New title", update.json["metadata"]["title"])

        deleted = self.client.delete(
            "/admin/api/artifacts/managed.id/rosbag/1",
            headers=self.admin,
            json={"delete_file": False},
        )
        self.assertEqual(200, deleted.status_code)
        self.assertTrue(path.exists())
        with server.database() as database:
            self.assertIsNone(database.execute("SELECT 1 FROM artifacts").fetchone())

    def test_artifact_delete_can_remove_file_transactionally(self):
        path = self.insert_artifact("remove.bag", "remove.id")
        deleted = self.client.delete(
            "/admin/api/artifacts/remove.id/rosbag/1",
            headers=self.admin,
            json={"delete_file": True},
        )
        self.assertEqual(200, deleted.status_code)
        self.assertFalse(path.exists())

    def test_orphan_bag_registration_and_reconciliation(self):
        self.bags.mkdir(exist_ok=True)
        orphan = self.bags / "incoming.bag"
        orphan.write_bytes(b"incoming")
        listing = self.client.get("/admin/api/bags", headers=self.admin).json
        self.assertIsNone(listing["items"][0]["registered"])

        response = self.client.post(
            "/admin/api/bags/register",
            headers=self.admin,
            json={
                "filename": orphan.name,
                "dataset_id": "incoming.id",
                "format": "rosbag",
                "version": "1",
                "metadata": {"title": "Incoming flight"},
            },
        )
        self.assertEqual(201, response.status_code, response.json)
        with server.database() as database:
            stored = Path(database.execute("SELECT storage_path FROM artifacts").fetchone()[0])
        self.assertEqual(self.bags.resolve(), stored.parent)

        listing = self.client.get("/admin/api/bags", headers=self.admin).json
        self.assertEqual("incoming.id", listing["items"][0]["registered"]["dataset_id"])

    def test_legacy_artifact_is_integrity_checked_and_migrated_to_flat_storage(self):
        legacy = self.root / "artifacts" / "legacy.id" / "rosbag" / "1.bag"
        legacy.parent.mkdir(parents=True)
        payload = b"legacy-bag"
        legacy.write_bytes(payload)
        with server.database() as database:
            database.execute(
                "INSERT INTO artifacts "
                "(dataset_id,format,version,size,sha256,metadata,storage_path) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    "legacy.id", "rosbag", "1", len(payload),
                    hashlib.sha256(payload).hexdigest(), "{}", str(legacy),
                ),
            )

        overview = self.client.get("/admin/api/overview", headers=self.admin).json
        self.assertEqual(1, overview["legacy_files"])
        legacy_download = self.client.get(
            "/v1/datasets/legacy.id/artifacts/rosbag/1/download",
            headers=self.admin,
        )
        self.assertEqual(500, legacy_download.status_code)
        response = self.client.post(
            "/admin/api/bags/migrate", headers=self.admin, json={}
        )
        self.assertEqual(200, response.status_code, response.json)
        self.assertEqual(1, len(response.json["migrated"]))
        self.assertFalse(legacy.exists())
        with server.database() as database:
            stored = Path(
                database.execute("SELECT storage_path FROM artifacts").fetchone()[0]
            )
        self.assertEqual(self.bags.resolve(), stored.parent)
        self.assertEqual(payload, stored.read_bytes())
        migrated_download = self.client.get(
            "/v1/datasets/legacy.id/artifacts/rosbag/1/download",
            headers=self.admin,
        )
        self.assertEqual(200, migrated_download.status_code)
        migrated_download.close()

    def test_legacy_migration_does_not_move_integrity_mismatch(self):
        legacy = self.root / "artifacts" / "changed.bag"
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b"changed")
        with server.database() as database:
            database.execute(
                "INSERT INTO artifacts "
                "(dataset_id,format,version,size,sha256,metadata,storage_path) "
                "VALUES(?,?,?,?,?,?,?)",
                ("changed.id", "rosbag", "1", 7, "0" * 64, "{}", str(legacy)),
            )
        response = self.client.post(
            "/admin/api/bags/migrate", headers=self.admin, json={}
        )
        self.assertEqual("integrity_mismatch", response.json["skipped"][0]["reason"])
        self.assertTrue(legacy.exists())

    def test_bag_traversal_and_missing_file_are_rejected(self):
        response = self.client.post(
            "/admin/api/bags/register",
            headers=self.admin,
            json={
                "filename": "../outside.bag",
                "dataset_id": "safe.id",
                "format": "rosbag",
                "version": "1",
                "metadata": {},
            },
        )
        self.assertEqual(404, response.status_code)

    def test_overview_and_artifacts_report_missing_file(self):
        self.bags.mkdir(exist_ok=True)
        missing = self.bags / "missing.bag"
        with server.database() as database:
            database.execute(
                "INSERT INTO artifacts "
                "(dataset_id,format,version,size,sha256,metadata,storage_path) "
                "VALUES(?,?,?,?,?,?,?)",
                ("missing.id", "rosbag", "1", 1, "0" * 64, "{}", str(missing)),
            )
        overview = self.client.get("/admin/api/overview", headers=self.admin).json
        self.assertEqual(1, overview["missing_files"])
        artifacts = self.client.get("/admin/api/artifacts", headers=self.admin).json
        self.assertFalse(artifacts["items"][0]["file_exists"])


if __name__ == "__main__":
    unittest.main()
