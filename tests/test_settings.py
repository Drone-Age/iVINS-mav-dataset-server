#!/usr/bin/env python3
"""Compatibility tests for DataSetsManager runtime names."""

import os
import unittest
import warnings
from unittest.mock import patch

import server
import settings


class SettingsCompatibilityTest(unittest.TestCase):
    def setUp(self):
        settings._WARNED.clear()

    def test_dsm_value_has_precedence(self):
        with patch.dict(
            os.environ,
            {"DSM_PORT": "9090", "IVINS_PORT": "8080"},
            clear=False,
        ):
            self.assertEqual(9090, settings.integer("PORT", 7000))

    def test_legacy_value_warns_and_remains_supported(self):
        with patch.dict(os.environ, {"IVINS_PORT": "8081"}, clear=False):
            os.environ.pop("DSM_PORT", None)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                self.assertEqual(8081, settings.integer("PORT", 7000))
            self.assertIn("IVINS_PORT is deprecated", str(caught[0].message))

    def test_profile_aliases_are_canonicalized(self):
        expected = {
            None: "all",
            "general": "all",
            "dev_0": "dev_01",
            "dev_2": "dev_02",
            "dev_3": "dev_03",
            "dev_4": "dev_04",
            "dev4": "dev_04",
        }
        self.assertEqual(expected, {name: server.normalize_profile(name) for name in expected})


if __name__ == "__main__":
    unittest.main()
