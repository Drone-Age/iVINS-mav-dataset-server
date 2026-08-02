#!/usr/bin/env python3
"""Contract tests for independent component versioning."""

import json
import re
import tempfile
import unittest
from pathlib import Path

import server


class ComponentVersioningTest(unittest.TestCase):
    def test_manifest_is_canonical_and_matches_runtime(self):
        path = Path(__file__).resolve().parents[1] / "versions.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(
            {"backend": "4.0.0", "frontend": "4.0.0", "process": "2.0.0", "distribution": "2.0.0"},
            {name: manifest[name] for name in ("backend", "frontend", "process", "distribution")},
        )
        self.assertEqual(manifest, server.VERSION_MANIFEST)
        self.assertEqual(manifest["backend"], server.SERVER_VERSION)

    def test_manifest_rejects_invalid_component_or_missing_rule(self):
        valid = dict(server.VERSION_MANIFEST)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "versions.json"
            invalid_version = {**valid, "frontend": "3.3"}
            invalid_distribution = {**valid, "distribution": "v1"}
            path.write_text(json.dumps(invalid_distribution), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "invalid distribution"):
                server.load_version_manifest(path)

            path.write_text(json.dumps(invalid_version), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "invalid frontend"):
                server.load_version_manifest(path)

            invalid_rules = {
                **valid,
                "compatibility": {"frontend_requires_backend": ">=4.0.0 <5.0.0"},
            }
            path.write_text(json.dumps(invalid_rules), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "process_applies_to_backend"):
                server.load_version_manifest(path)

    def test_release_metadata_tracks_each_component(self):
        root = Path(__file__).resolve().parents[1]
        semver = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
        for name, version in server.component_versions().items():
            self.assertRegex(version, semver)
            changelog = (root / f"CHANGELOG.{name}.md").read_text(encoding="utf-8")
            self.assertIn(f"## {version}", changelog)

        process = (root / "process" / "PROCESS.md").read_text(encoding="utf-8")
        self.assertIn("Process 2.0.0", process)
        self.assertIn("DataSetsManager/DataSetsManager", process)

        release_compose = (root / "compose.release.yaml").read_text(encoding="utf-8")
        self.assertNotIn("build:", release_compose)
        self.assertIn("pull_policy: never", release_compose)
        self.assertIn("datasetsmanager-server:4.0.0", release_compose)

        distribution = (root / "distribution" / "DISTRIBUTION.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Distribution version: **2.0.0**", distribution)
        self.assertIn("windows-portable", distribution)
        for name in (
            "install.ps1",
            "update.ps1",
            "rollback.ps1",
            "verify.ps1",
            "new-admin-key.ps1",
        ):
            self.assertTrue((root / "distribution" / "docker" / name).is_file())

        schema = json.loads(
            (root / "schemas" / "package-manifest.schema.json").read_text(encoding="utf-8")
        )
        self.assertEqual(["docker-bundle", "windows-portable", "windows-msi"], schema["properties"]["package_format"]["enum"])

        windows_lock = (root / "requirements-windows.lock").read_text(encoding="utf-8").splitlines()
        self.assertTrue(windows_lock)
        self.assertTrue(all("==" in line for line in windows_lock if line.strip()))
        for name in (
            "install-service.ps1",
            "uninstall-service.ps1",
            "verify.ps1",
            "new-admin-key.ps1",
        ):
            self.assertTrue((root / "distribution" / "windows" / name).is_file())
        self.assertTrue((root / "distribution" / "common" / "verify-integrity.ps1").is_file())

        dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
        compose = (root / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn("server.py api_keys.py settings.py versions.json", dockerfile)
        self.assertIn("datasetsmanager-server:4.0.0", compose)


if __name__ == "__main__":
    unittest.main()
