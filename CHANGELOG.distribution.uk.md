# Журнал змін Distribution

[English version](CHANGELOG.distribution.md)

## 2.0.0 — 2026-08-02

- OCI та bundle-артефакти перейменовано на `datasetsmanager-server`.
- Додано формат `windows-portable` і зарезервовано `windows-msi`.
- Застарілий OCI tag збережено як compatibility alias протягом Distribution 2.x.

## 1.0.0 — 2026-08-02

- Distribution встановлено як компонент з незалежною версією.
- Додано offline Docker bundle зі збереженим image без залежності від Git.
- Додано package manifest, SHA-256 inventory і sidecar digest ZIP.
- Додано PowerShell tools install, update, rollback, verification та admin-key.
- Зарезервовано додаткові формати, зокрема нативний Windows Installer.
