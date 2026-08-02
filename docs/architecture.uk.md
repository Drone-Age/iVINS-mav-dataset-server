# Архітектура сервера

[English version](architecture.md)

```mermaid
flowchart LR
  Guest["Гість"] --> Web["Публічний Web UI"]
  User["API key користувача"] --> API["Flask /v1 API"]
  Admin["Admin API key"] --> AdminUI["Admin UI і контрольований CRUD"]
  Web --> Catalog["Публічний каталог"]
  AdminUI --> API
  API --> DB["SQLite catalog.sqlite3"]
  API --> Bags["Єдиний плоский каталог bags"]
  Catalog --> Mirrors["Перевірені зовнішні mirrors"]
  Client["DataSetsManager/client"] --> API
  Process["DataSetsManager Process"] --> API
```

HTTP-застосунок зберігає стан лише у SQLite, staging і плоскому каталозі BAG у
зовнішньому runtime root. Ключі генеруються сервером, показуються один раз і
зберігаються тільки як SHA-256 digest. Web UI тримає введений ключ лише в
пам’яті.

Backend володіє `/v1`, авторизацією, валідацією і міграціями. Frontend відповідає
за представлення та не послаблює серверні права. Distribution пакує автономні
Docker/Windows артефакти. Process є зафіксованою зовнішньою залежністю.
