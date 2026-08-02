# Portable-пакет Windows Service

[English version](windows-portable.md)

Distribution 2.0.0 реалізує `windows-portable` як однофайловий PyInstaller EXE
та PowerShell-інструменти життєвого циклу. EXE запускає Flask через Waitress і
підтримує Windows Service Control Manager через pywin32.

Пакет встановлює службу `DataSetsManagerServer`, тримає змінні дані поза
пакетом, створює ключі лише командою `datasetsmanager-server.exe key` та
перевіряє health/versions. Ключі, база і BAG до пакета не входять.
