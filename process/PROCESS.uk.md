# Залежність від Process

[English version](PROCESS.md)

Цей реліз сервера залежить від **DataSetsManager Process 2.0.0**.
Канонічні політики, дозволи, заборони, ITSM-регламенти, release gates і записи
Incident/Change ведуться у
[`DataSetsManager/DataSetsManager`](https://github.com/DataSetsManager/DataSetsManager).

Незмінний snapshot Process 1.0.0, який раніше містився в цьому репозиторії,
збережено в [`archive/PROCESS-v1.0.0.md`](archive/PROCESS-v1.0.0.md) для аудиту й
rollback. Він більше не є поточним джерелом політик.

Необхідна версія Process та діапазон сумісності визначені у
[`versions.json`](../versions.json).
