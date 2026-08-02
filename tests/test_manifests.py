#!/usr/bin/env python3
"""Validate repository and release schemas."""

import json
import unittest
from pathlib import Path

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]


class ManifestTest(unittest.TestCase):
    def test_repository_manifest(self):
        schema = json.loads((ROOT / "schemas/repository-manifest.schema.json").read_text(encoding="utf-8"))
        manifest = yaml.safe_load((ROOT / "manifest/repository.yaml").read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)
        jsonschema.validate(manifest, schema)

    def test_all_schemas_are_valid(self):
        for path in sorted((ROOT / "schemas").glob("*.schema.json")):
            with self.subTest(path=path.name):
                jsonschema.Draft202012Validator.check_schema(
                    json.loads(path.read_text(encoding="utf-8"))
                )


if __name__ == "__main__":
    unittest.main()
