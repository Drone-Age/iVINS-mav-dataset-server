#!/usr/bin/env python3
"""Public catalog and guest/user/admin access tests."""

import hashlib
import os
import sqlite3
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
        html = page.get_data(as_text=True)
        self.assertIn("Backend 3.3.0", html)
        self.assertIn("Frontend 3.3.0", html)
        self.assertIn("Process 1.0.0", html)
        self.assertIn("Distribution 1.0.0", html)
        response = self.client.get("/public/api/datasets")
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            {"backend": "3.3.0", "frontend": "3.3.0", "process": "1.0.0", "distribution": "1.0.0"},
            response.json["versions"],
        )
        self.assertEqual(57, response.json["total"])
        self.assertEqual(
            [
                "EuRoC MAV", "iVINS", "KAIST Urban", "KAIST VIO",
                "RPNG AR Table", "RPNG OpenVINS", "TUM-VI", "UZH-FPV",
            ],
            response.json["families"],
        )
        self.assertEqual(["all", "dev_04"], response.json["profiles"])
        self.assertEqual(["all"], response.json["profiles_by_family"]["EuRoC MAV"])
        self.assertEqual(["dev_04"], response.json["profiles_by_family"]["iVINS"])
        euroc = next(item for item in response.json["datasets"] if item["id"] == "e.1.1.e")
        ivins = next(
            item for item in response.json["datasets"] if item["id"] == "iv.dev.4.ff.1"
        )
        self.assertEqual("all", euroc["profile"])
        self.assertEqual("dev_04", ivins["profile"])
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
        self.assertIn("profileFilter", source)
        self.assertIn("profiles_by_family", source)
        self.assertIn('item.profile === "all"', source)
        self.assertIn("siteEditMode", source)

        page = self.client.get("/")
        html = page.get_data(as_text=True)
        page.close()
        self.assertNotIn("Увійти за API-ключем", html)
        self.assertNotIn("Адмін-панель", html)
        self.assertIn("data-language-selector", html)
        self.assertIn("Режим редагування", html)

        translations = self.client.get("/static/i18n.js")
        i18n_source = translations.get_data(as_text=True)
        translations.close()
        self.assertIn("Дані для", i18n_source)
        self.assertIn("Sign in", i18n_source)
        self.assertIn("setLanguage", i18n_source)
        self.assertNotIn("localStorage", i18n_source)
        self.assertNotIn("sessionStorage", i18n_source)
        self.assertNotIn("document.cookie", i18n_source)
        self.assertNotIn("innerHTML", i18n_source)

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
        public = self.client.get("/public/api/datasets").json
        item = next(item for item in public["datasets"] if item["id"] == "custom.1")
        self.assertEqual("all", item["profile"])

        dataset_update = {
            "family": "Custom",
            "profile": "dev_01",
            "name": "Flight 01",
            "description": "External recording",
            "measurement": "12 m",
            "homepage_url": "https://example.com/dataset",
            "ground_truth_url": "",
            "config_url": "",
            "visible": True,
        }
        legacy_alias = self.client.patch(
            "/admin/api/datasets/custom.1",
            headers=self.admin,
            json={**dataset_update, "profile": "general"},
        )
        self.assertEqual(200, legacy_alias.status_code, legacy_alias.json)
        alias_catalog = self.client.get("/public/api/datasets").json
        alias_item = next(
            item for item in alias_catalog["datasets"] if item["id"] == "custom.1"
        )
        self.assertEqual("all", alias_item["profile"])
        invalid_profile = self.client.patch(
            "/admin/api/datasets/custom.1",
            headers=self.admin,
            json={**dataset_update, "profile": "DEV 01"},
        )
        self.assertEqual(400, invalid_profile.status_code)
        updated = self.client.patch(
            "/admin/api/datasets/custom.1", headers=self.admin, json=dataset_update
        )
        self.assertEqual(200, updated.status_code, updated.json)
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
        self.assertEqual("dev_01", item["profile"])
        self.assertEqual(["all", "dev_01", "dev_04"], public["profiles"])
        self.assertEqual(["dev_01"], public["profiles_by_family"]["Custom"])
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

    def test_existing_v3_dataset_table_migrates_profiles_without_data_loss(self):
        database = sqlite3.connect(self.database)
        database.executescript(
            """
            CREATE TABLE datasets (
              id TEXT PRIMARY KEY,
              family TEXT NOT NULL,
              name TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              measurement TEXT NOT NULL DEFAULT '',
              homepage_url TEXT,
              ground_truth_url TEXT,
              config_url TEXT,
              visible INTEGER NOT NULL DEFAULT 1 CHECK(visible IN (0,1)),
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO app_settings(key,value)
            VALUES('dataset_seed_version','2026-08-02.1');
            INSERT INTO datasets(id,family,name,description,visible)
            VALUES('legacy.1','Legacy','Legacy flight','must survive',1);
            INSERT INTO datasets(id,family,name,description,visible)
            VALUES('iv.dev.4.ff.1','iVINS','Existing iVINS flight','must survive too',1);
            """
        )
        database.commit()
        database.close()

        migrated = server.connect()
        columns = {row[1] for row in migrated.execute("PRAGMA table_info(datasets)")}
        legacy = migrated.execute(
            "SELECT profile,description FROM datasets WHERE id='legacy.1'"
        ).fetchone()
        ivins = migrated.execute(
            "SELECT profile FROM datasets WHERE id='iv.dev.4.ff.1'"
        ).fetchone()
        migrated.close()

        self.assertIn("profile", columns)
        self.assertEqual(("all", "must survive"), tuple(legacy))
        self.assertEqual("dev_04", ivins["profile"])

    def test_v31_general_profiles_migrate_to_all_but_specific_profiles_survive(self):
        database = sqlite3.connect(self.database)
        database.executescript(
            """
            CREATE TABLE datasets (
              id TEXT PRIMARY KEY,
              family TEXT NOT NULL,
              profile TEXT NOT NULL DEFAULT 'general',
              name TEXT NOT NULL,
              description TEXT NOT NULL DEFAULT '',
              measurement TEXT NOT NULL DEFAULT '',
              homepage_url TEXT,
              ground_truth_url TEXT,
              config_url TEXT,
              visible INTEGER NOT NULL DEFAULT 1 CHECK(visible IN (0,1)),
              created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
              updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO app_settings(key,value)
            VALUES('dataset_seed_version','2026-08-02.2');
            INSERT INTO datasets(id,family,profile,name,visible)
            VALUES('legacy.general','Legacy','general','General flight',1);
            INSERT INTO datasets(id,family,profile,name,visible)
            VALUES('legacy.specific','Legacy','dev_01','Specific flight',1);
            """
        )
        database.commit()
        database.close()

        migrated = server.connect()
        profiles = dict(
            migrated.execute(
                "SELECT id,profile FROM datasets WHERE id LIKE 'legacy.%' ORDER BY id"
            ).fetchall()
        )
        migrated.close()

        self.assertEqual("all", profiles["legacy.general"])
        self.assertEqual("dev_01", profiles["legacy.specific"])

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
