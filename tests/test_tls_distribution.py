#!/usr/bin/env python3
"""Static security contracts for the TLS-enabled Docker distribution."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TlsDistributionTest(unittest.TestCase):
    def test_backend_listener_stays_on_loopback_by_default(self):
        env = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertIn("DSM_PUBLIC_HOST=datasetsmanager.drone-age.org", env)
        compose = (ROOT / "compose.release.yaml").read_text(encoding="utf-8")
        backend = compose.split("  caddy:", 1)[0]
        self.assertNotIn("ports:", backend)
        self.assertIn('expose:\n      - "8080"', backend)

    def test_proxy_is_pinned_hardened_and_persists_acme_state(self):
        compose = (ROOT / "compose.release.yaml").read_text(encoding="utf-8")
        self.assertIn("image: caddy:2.11.4-alpine", compose)
        self.assertIn("pull_policy: never", compose)
        self.assertIn("read_only: true", compose)
        self.assertIn("no-new-privileges:true", compose)
        self.assertIn("caddy-data:/data", compose)
        self.assertIn("caddy-config:/config", compose)
        caddyfile = (ROOT / "Caddyfile").read_text(encoding="utf-8")
        self.assertNotIn("log {", caddyfile)
        self.assertNotIn("Authorization", caddyfile)

    def test_bundle_builder_saves_proxy_image_and_config(self):
        builder = (ROOT / "tools" / "build-release-bundle.ps1").read_text(encoding="utf-8")
        self.assertIn('"caddy:2.11.4-alpine"', builder)
        self.assertIn('"Caddyfile"', builder)
        self.assertIn("proxyArchiveRelative", builder)


if __name__ == "__main__":
    unittest.main()
