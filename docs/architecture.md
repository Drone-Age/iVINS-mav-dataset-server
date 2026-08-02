# Server architecture

[Українська версія](architecture.uk.md)

## System context

```mermaid
flowchart LR
  Guest["Guest"] --> HTTP["Public HTTP site"]
  User["User API key"] --> HTTP
  Admin["Admin API key"] --> HTTP
  Client["DataSetsManager Client"] -->|"/v1"| HTTP
  HTTP --> Mirrors["Verified external mirrors"]
  HTTP --> Runtime["External persistent runtime"]
  Process["DataSetsManager Process"] -->|"policy and compatibility"| HTTP
```

## Components

```mermaid
flowchart TB
  HTTP["Flask HTTP application"] --> Public["Public catalog and bilingual Frontend"]
  HTTP --> Auth["API-key authentication and rate limits"]
  HTTP --> Admin["Controlled Admin CRUD"]
  HTTP --> Upload["Immutable upload and publish lifecycle"]
  Auth --> Keys["Server-side key CLI and digest store"]
  Public --> Catalog["Dataset and mirror service"]
  Admin --> Catalog
  Upload --> Artifacts["Artifact metadata and tickets"]
  Distribution["Docker and Windows packaging"] --> HTTP
```

## Request and storage data flow

```mermaid
sequenceDiagram
  participant Browser
  participant API as HTTP API
  participant DB as SQLite
  participant Bags as Flat bags directory
  Browser->>API: Public catalog request
  API->>DB: Read visible Datasets and verified mirrors
  DB-->>API: Stable IDs and family-scoped profiles
  API-->>Browser: Bilingual catalog model
  Browser->>API: Bearer key and local download-ticket request
  API->>DB: Authenticate digest and store ticket digest
  API-->>Browser: 60-second single-use URL
  Browser->>API: Redeem ticket
  API->>Bags: Resolve verified direct-child artifact
  API-->>Browser: Stream bytes and invalidate ticket
```

## Deployment view

```mermaid
flowchart TB
  subgraph Delivery["Distribution 2.0"]
    Docker["Offline OCI/Docker ZIP"]
    Windows["Portable Windows Service ZIP"]
    MSI["Future windows-msi contract"]
  end
  Docker --> HTTP["Loopback HTTP listener"]
  Windows --> HTTP
  Proxy["Trusted router/reverse proxy or VPN"] --> HTTP
  HTTP --> Var["External var root"]
  Var --> DB["catalog.sqlite3"]
  Var --> Bags["bags: one flat directory"]
  Var --> Staging["staging uploads"]
```

## Repository interactions

```mermaid
flowchart LR
  Central["DataSetsManager Process and compatibility"] --> Server
  Community[".github contribution defaults"] --> Server
  Client -->|"sync, fetch and publish over /v1"| Server
  Server -->|"published snapshot and release manifests"| Client
  Dev["agent-software-development"] -->|"authorized draft PR only"| Server
  Desk["agent-service-desk"] -->|"classified incidents and requests"| Server
```

The HTTP application is stateless except for SQLite, staged uploads, and the
flat BAG directory in the external runtime root. API-key secrets are generated
server-side, returned once, and stored only as digests. The Web UI keeps an
entered credential in page memory only.

Backend owns `/v1`, authentication, validation, and data migrations. Frontend
owns presentation and never weakens server authorization. Distribution owns
offline Docker and Windows packaging. Process is a pinned external dependency.
