# Distribution 2.0.0 acceptance evidence

[Українська версія](distribution-2.0.0.uk.md)

Date: 2026-08-02. Source branch: `migration/datasetsmanager-server-4.0.0`.

## Artifacts

| Package | Bytes | SHA-256 |
|---|---:|---|
| `datasetsmanager-server_d2.0.0-b4.0.0-f4.0.0-p2.0.0_docker-linux-amd64.zip` | 18,965,091 | `1fcef9f5d0be5c0fa495568b3a65fed34767f3edccfeeabb4b166c13c579fa49` |
| `datasetsmanager-server_d2.0.0-b4.0.0-f4.0.0-p2.0.0_windows-x64.zip` | 17,774,133 | `710a565cc5c8013cb77c1ac6cd7fa99f6bf30e4c1352b804a5fb072440b7c02e` |

Both ZIP files passed their sidecar and internal `SHA256SUMS` checks, package
manifest JSON Schema validation, and an archive scan proving that no `.git`
metadata is present.

## Results

- 48 Backend/Frontend/Distribution/documentation unit and security tests passed.
- Development and release Compose configurations validated successfully.
- The Docker ZIP loaded its local image and deployed without Git on
  `127.0.0.1:18080`; the public catalog returned 57 Datasets, protected `/v1`
  returned `401` without a key, a server-generated admin key authenticated, and
  its plaintext was absent from SQLite.
- The Windows ZIP ran its standalone EXE without Git or Docker on
  `127.0.0.1:18081` with the same version, catalog, authorization, and
  plaintext-key checks.
- Acceptance runtimes and keys were removed after testing. The existing server
  on port 8081 remained healthy and unchanged.
- Docker Scout analyzed 48 image packages and reported `0 Critical`, `0 High`,
  `0 Medium`, and `0 Low` known vulnerabilities.

## Gates still open

This is local package acceptance, not production approval. A clean Windows VM
test, a clean offline Docker-host test, the verified `F:` runtime migration,
production routing cutover, merge, tags, and GitHub releases remain open. They
require the Change Authority decision recorded for the migration Change.
