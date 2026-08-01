#!/usr/bin/env python3
"""Public catalog and guest/user/admin access tests."""

import hashlib
import os
import tempfile
import time
import unittest
from pathlib import Path

import api_keys
import server


class PublicCatalogTest(unittest.TestCase):
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
        os.environ["IVINS_DOWNLOADS_PER_MINUTE"] = "1000"
        server.rate_limiter.reset()
        self.admin_id, self.admin_token = api_keys.create_api_key("public-admin", "admin")
        self.user_id, self.user_token = api_keys.create_api_key("public-user", "user")
        self.admin = {"Authorization": f"Bearer {self.admin_token}"}
        self.user = {"Authorization": f"Bearer {self.user_token}"}
        self.client = server.app.test_client()

    def tearDown(self):
        self.temporary.cleanup()

    def test_guest_can_open_site_and_external_catalog_without_key(self):
        page = self.client.get("/")
        self.assertEqual(200, page.status_code)
        self.assertIn("script-src 'self'", page.headers["Content-Security-Policy"])
        response = self.client.get("/public/api/datasets")
        self.assertEqual(200, response.status_code)
        self.assertEqual(57, response.json["total"])
        self.assertEqual(
            [
                "EuRoC MAV", "iVINS", "KAIST Urban", "KAIST VIO",
                "RPNG AR Table", "RPNG OpenVINS", "TUM-VI", "UZH-FPV",
            ],
            response.json["families"],
        )
        euroc = next(item for item in response.json["datasets"] if item["id"] == "e.1.1.e")
        self.assertTrue(euroc["mirrors"])
        self.assertTrue(all(mirror["url"].startswith(("http://", "https://")) for mirror in euroc["mirrors"]))
        self.assertNotIn("storage_path", response.get_data(as_text=True))
        page.close()

    def test_public_javascript_never_persists_or_places_key_in_url(self):
        script = self.client.get("/static/site.js")
        source = script.get_data(as_text=True)
        script.close()
        self.assertNotIn("localStorage", source)
        self.assertNotIn("sessionStorage", source)
        self.assertNotIn("document.cookie", source)
        self.assertNotIn("innerHTML", source)
        self.assertNotIn("api_key=", source.lower())

    def test_api_key_maps_to_user_or_admin(self):
        self.assertEqual(401, self.client.get("/auth/session").status_code)
        user = self.client.get("/auth/session", headers=self.user)
        admin = self.client.get("/auth/session", headers=self.admin)
        self.assertEqual("user", user.json["role"])
        self.assertEqual("Користувач", user.json["user_type"])
        self.assertEqual("admin", admin.json["role"])
        self.assertEqual("Адмін", admin.json["user_type"])
        self.assertEqual(403, self.client.get("/admin/api/datasets", headers=self.user).status_code)

    def test_admin_controls_dataset_and_mirrors_with_url_validation(self):
        created = self.client.post(
            "/admin/api/datasets",
            headers=self.admin,
            json={
                "id": "custom.1",
                "family": "Custom",
                "name": "Flight 01",
                "description": "External recording",
                "measurement": "12 m",
                "homepage_url": "https://example.com/dataset",
                "ground_truth_url": "",
                "config_url": "",
                "visible": True,
            },
        )
        self.assertEqual(201, created.status_code, created.json)
        invalid = self.client.post(
            "/admin/api/datasets/custom.1/mirrors",
            headers=self.admin,
            json={
                "format": "rosbag",
                "label": "Unsafe",
                "url": "javascript:alert(1)",
                "verified": False,
            },
        )
        self.assertEqual(400, invalid.status_code)
        mirror = self.client.post(
            "/admin/api/datasets/custom.1/mirrors",
            headers=self.admin,
            json={
                "format": "rosbag",
                "label": "Mirror A",
                "url": "https://mirror.example/custom.1.bag",
                "verified": True,
            },
        )
        self.assertEqual(201, mirror.status_code, mirror.json)
        public = self.client.get("/public/api/datasets").json
        item = next(item for item in public["datasets"] if item["id"] == "custom.1")
        self.assertEqual("https://mirror.example/custom.1.bag", item["mirrors"][0]["url"])
        self.assertEqual(
            200,
            self.client.delete(
                f"/admin/api/mirrors/{mirror.json['id']}", headers=self.admin
            ).status_code,
        )
        self.assertEqual(
            200,
            self.client.delete("/admin/api/datasets/custom.1", headers=self.admin).status_code,
        )

    def add_local_artifact(self):
        self.bags.mkdir(exist_ok=True)
        payload = b"private-local-bag"
        path = self.bags / "e.1.1.e__rosbag__local.bag"
        path.write_bytes(payload)
        with server.database() as database:
            database.execute(
                "INSERT INTO artifacts"
                "(dataset_id,format,version,size,sha256,metadata,storage_path) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    "e.1.1.e", "rosbag", "local", len(payload),
                    hashlib.sha256(payload).hexdigest(), "{}", str(path.resolve()),
                ),
            )
        return payload

    def test_guest_cannot_download_local_bag_but_user_gets_single_use_ticket(self):
        payload = self.add_local_artifact()
        direct = "/v1/datasets/e.1.1.e/artifacts/rosbag/local/download"
        ticket_path = f"{direct}-ticket"
        self.assertEqual(401, self.client.get(direct).status_code)
        self.assertEqual(401, self.client.post(ticket_path, json={}).status_code)

        listing = self.client.get("/public/api/datasets").json
        item = next(item for item in listing["datasets"] if item["id"] == "e.1.1.e")
        self.assertTrue(item["local_artifacts"][0]["requires_auth"])
        self.assertNotIn("download_url", item["local_artifacts"][0])

        issued = self.client.post(ticket_path, headers=self.user, json={})
        self.assertEqual(201, issued.status_code, issued.json)
        ticket_url = issued.json["download_url"]
        token = ticket_url.rsplit("/", 1)[1]
        self.assertNotIn(token.encode(), self.database.read_bytes())
        downloaded = self.client.get(ticket_url)
        self.assertEqual(200, downloaded.status_code)
        self.assertEqual(payload, downloaded.data)
        downloaded.close()
        self.assertEqual(404, self.client.get(ticket_url).status_code)

    def test_expired_download_ticket_is_rejected(self):
        self.add_local_artifact()
        issued = self.client.post(
            "/v1/datasets/e.1.1.e/artifacts/rosbag/local/download-ticket",
            headers=self.user,
            json={},
        )
        with server.database() as database:
            database.execute("UPDATE download_tickets SET expires_at=?", (time.time() - 1,))
        self.assertEqual(404, self.client.get(issued.json["download_url"]).status_code)


if __name__ == "__main__":
    unittest.main()
