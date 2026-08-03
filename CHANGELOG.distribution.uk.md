# Журнал змін Distribution

[English version](CHANGELOG.distribution.md)

## 2.1.0 — 2026-08-03

- До Docker bundle додано зафіксований Caddy 2.11.4 з automatic HTTPS,
  перенаправленням HTTP та HSTS; Gunicorn залишено у приватній Compose-мережі.
- Додано перевірку TLS та інструмент одноразового створення окремого `user`-ключа.
- До integrity manifest додано образ і конфігурацію proxy; access log вимкнено.

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
