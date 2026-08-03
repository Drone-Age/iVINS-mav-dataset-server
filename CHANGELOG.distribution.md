# Distribution changelog

[Українська версія](CHANGELOG.distribution.uk.md)

## 2.1.0 — 2026-08-03

- Added pinned Caddy 2.11.4 to Docker bundles with automatic HTTPS, HTTP
  redirects and HSTS while keeping Gunicorn private to the Compose network.
- Added TLS qualification and dedicated one-time `user` key tools.
- Added proxy image/config integrity metadata and secret-safe logging defaults.

## 2.0.0 — 2026-08-02

- Renamed OCI and bundle artifacts to `datasetsmanager-server`.
- Added the `windows-portable` package format and reserved `windows-msi`.
- Preserved the legacy OCI tag as a compatibility alias through Distribution 2.x.

## 1.0.0 — 2026-08-02

- Established Distribution as an independently versioned component.
- Added an offline Docker bundle with a saved image and no Git dependency.
- Added a package manifest, SHA-256 integrity inventory and ZIP sidecar digest.
- Added PowerShell install, update, rollback, verification and admin-key tools.
- Reserved additional package formats, including a native Windows Installer.
