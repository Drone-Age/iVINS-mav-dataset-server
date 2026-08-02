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
            {"backend": "3.3.0", "frontend": "3.3.0", "process": "1.0.0"},
            {name: manifest[name] for name in ("backend", "frontend", "process")},
        )
        self.assertEqual(manifest, server.VERSION_MANIFEST)
        self.assertEqual(manifest["backend"], server.SERVER_VERSION)

    def test_manifest_rejects_invalid_component_or_missing_rule(self):
        valid = dict(server.VERSION_MANIFEST)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "versions.json"
            invalid_version = {**valid, "frontend": "3.3"}
            path.write_text(json.dumps(invalid_version), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "invalid frontend"):
                server.load_version_manifest(path)

            invalid_rules = {
                **valid,
                "compatibility": {"frontend_requires_backend": ">=3.3.0 <4.0.0"},
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
        self.assertIn("Версія Process: **1.0.0**", process)
        self.assertIn("Обробка інцидентів", process)

        dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
        compose = (root / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn("server.py api_keys.py versions.json", dockerfile)
        self.assertIn("ivins-mav-dataset-server:3.3.0", compose)


if __name__ == "__main__":
    unittest.main()
