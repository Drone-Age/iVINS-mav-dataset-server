# Дистрибутив DataSetsManager

[English version](DISTRIBUTION.md)

Поточна версія Distribution: **2.0.0**. Вона пакує сумісні Backend 4.0.0,
Frontend 4.0.0 і залежність Process 2.0.0 без включення робочих даних або
секретів.

Підтримуються два автономні формати:

- `docker-bundle` — OCI image, Compose, маніфест, checksums та PowerShell tools;
- `windows-portable` — standalone EXE, Windows Service tools, маніфест і
  checksums без залежності від Git чи Docker.

`windows-msi` зарезервований для майбутнього підписаного MSI. База,
API-ключі та `.bag` завжди зберігаються поза пакетом. Стандартний Windows data
root — `%ProgramData%\DataSetsManager\Server\var`; `.bag` є прямими дочірніми
файлами каталогу `bags`.

Docker-пакет будується `tools/build-release-bundle.ps1`, Windows-пакет —
`tools/build-windows-package.ps1`. Обидва містять `package-manifest.json`,
`versions.json`, SHA-256 і server-side інструмент створення admin key.
