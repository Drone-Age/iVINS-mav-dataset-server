# Свідчення приймання Distribution 2.0.0

[English version](distribution-2.0.0.md)

Дата: 2026-08-02. Вихідна гілка: `migration/datasetsmanager-server-4.0.0`.

## Артефакти

| Пакет | Байтів | SHA-256 |
|---|---:|---|
| `datasetsmanager-server_d2.0.0-b4.0.0-f4.0.0-p2.0.0_docker-linux-amd64.zip` | 18 965 091 | `1fcef9f5d0be5c0fa495568b3a65fed34767f3edccfeeabb4b166c13c579fa49` |
| `datasetsmanager-server_d2.0.0-b4.0.0-f4.0.0-p2.0.0_windows-x64.zip` | 17 774 133 | `710a565cc5c8013cb77c1ac6cd7fa99f6bf30e4c1352b804a5fb072440b7c02e` |

Обидва ZIP пройшли перевірку sidecar і внутрішнього `SHA256SUMS`, валідацію
package manifest за JSON Schema та сканування архіву, яке підтвердило відсутність
метаданих `.git`.

## Результати

- Пройдено 48 модульних, документаційних і безпекових тестів
  Backend/Frontend/Distribution.
- Конфігурації Compose для розробки й релізу успішно валідовані.
- Docker ZIP завантажив локальний image і розгорнувся без Git на
  `127.0.0.1:18080`; публічний каталог повернув 57 Datasets, захищений `/v1`
  без ключа повернув `401`, згенерований сервером admin-ключ автентифікувався,
  а його відкритий текст був відсутній у SQLite.
- Windows ZIP запустив standalone EXE без Git або Docker на
  `127.0.0.1:18081` з тими самими перевірками версій, каталогу, авторизації та
  відсутності відкритого ключа.
- Після тестування acceptance-runtime і ключі видалено. Чинний сервер на порту
  8081 залишився працездатним і незмінним.
- Docker Scout проаналізував 48 пакетів image і не виявив відомих
  вразливостей: `0 Critical`, `0 High`, `0 Medium`, `0 Low`.

## Ще відкриті контрольні точки

Це локальне приймання пакетів, а не production-схвалення. Ще потрібні тест на
чистій Windows VM, тест на чистому offline Docker-host, перевірена міграція
runtime на диску `F:`, production cutover маршрутизації, merge, теги та GitHub
Releases. Вони потребують рішення Change Authority, зафіксованого у
міграційному Change.
