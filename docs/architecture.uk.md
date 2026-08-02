# Архітектура Server

[English version](architecture.md)

## Контекст системи

```mermaid
flowchart LR
  Guest["Гість"] --> HTTP["Публічний HTTP site"]
  User["API-ключ User"] --> HTTP
  Admin["API-ключ Admin"] --> HTTP
  Client["DataSetsManager Client"] -->|"/v1"| HTTP
  HTTP --> Mirrors["Перевірені зовнішні mirrors"]
  HTTP --> Runtime["Зовнішній persistent runtime"]
  Process["DataSetsManager Process"] -->|"policy і compatibility"| HTTP
```

## Компоненти

```mermaid
flowchart TB
  HTTP["HTTP application Flask"] --> Public["Публічний каталог і двомовний Frontend"]
  HTTP --> Auth["API-key authentication і rate limits"]
  HTTP --> Admin["Контрольований Admin CRUD"]
  HTTP --> Upload["Незмінний upload/publish lifecycle"]
  Auth --> Keys["Server-side key CLI і digest store"]
  Public --> Catalog["Service Datasets і mirrors"]
  Admin --> Catalog
  Upload --> Artifacts["Artifact metadata і tickets"]
  Distribution["Docker і Windows packaging"] --> HTTP
```

## Потік запитів і даних сховища

```mermaid
sequenceDiagram
  participant Browser
  participant API as HTTP API
  participant DB as SQLite
  participant Bags as Плоский bags-каталог
  Browser->>API: Запит публічного каталогу
  API->>DB: Read видимих Datasets і verified mirrors
  DB-->>API: Стабільні IDs і family-scoped profiles
  API-->>Browser: Двомовна catalog model
  Browser->>API: Bearer key і local download-ticket request
  API->>DB: Authenticate digest і store ticket digest
  API-->>Browser: Одноразовий URL на 60 секунд
  Browser->>API: Redeem ticket
  API->>Bags: Resolve verified direct-child artifact
  API-->>Browser: Stream bytes та invalidate ticket
```

## Схема розгортання

```mermaid
flowchart TB
  subgraph Delivery["Distribution 2.0"]
    Docker["Offline OCI/Docker ZIP"]
    Windows["Portable Windows Service ZIP"]
    MSI["Майбутній contract windows-msi"]
  end
  Docker --> HTTP["Loopback HTTP listener"]
  Windows --> HTTP
  Proxy["Довірений router/reverse proxy або VPN"] --> HTTP
  HTTP --> Var["Зовнішній var root"]
  Var --> DB["catalog.sqlite3"]
  Var --> Bags["bags: один плоский каталог"]
  Var --> Staging["staging uploads"]
```

## Взаємодія репозиторіїв

```mermaid
flowchart LR
  Central["DataSetsManager Process і compatibility"] --> Server
  Community["Contribution defaults .github"] --> Server
  Client -->|"sync, fetch і publish через /v1"| Server
  Server -->|"published snapshot і release manifests"| Client
  Dev["agent-software-development"] -->|"лише authorized draft PR"| Server
  Desk["agent-service-desk"] -->|"класифіковані incidents і requests"| Server
```

HTTP application не має стану, крім SQLite, staged uploads і плоского
BAG-каталогу в зовнішньому runtime root. Секрети API-ключів генеруються на
сервері, показуються один раз і зберігаються лише як digests. Web UI тримає
введений credential лише в пам'яті сторінки.

Backend володіє `/v1`, authentication, validation і data migrations. Frontend
володіє presentation і ніколи не послаблює server authorization. Distribution
володіє offline Docker/Windows packaging. Process є pinned external dependency.
