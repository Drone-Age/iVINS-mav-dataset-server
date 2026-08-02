# Distribution 2.0.0 acceptance evidence

[Українська версія](distribution-2.0.0.uk.md)

Date: 2026-08-02. Source branch: `migration/datasetsmanager-server-4.0.0`.

## Artifacts

| Package | Bytes | SHA-256 |
|---|---:|---|
| `datasetsmanager-server_d2.0.0-b4.0.0-f4.0.0-p2.0.0_docker-linux-amd64.zip` | 18,965,131 | `547571ed8c672f235cefecc8cacb4e3c256e941f24f4df77dcc2bec7f9f075ab` |
| `datasetsmanager-server_d2.0.0-b4.0.0-f4.0.0-p2.0.0_windows-x64.zip` | 17,773,736 | `b2db19889b02f4c2d6038b58eafc03f98509bd2b134b573792155636a9341979` |

Both ZIP files passed their sidecar and internal `SHA256SUMS` checks, package
manifest JSON Schema validation, and an archive scan proving that no `.git`
metadata is present.
Both builders now package the single canonical schema from
`schemas/package-manifest.schema.json`; the obsolete duplicate schema was removed.

## Results

- 50 Backend/Frontend/Distribution/documentation unit and security tests passed.
- Development and release Compose configurations validated successfully.
- The Docker ZIP loaded its local image and deployed without Git on
  `127.0.0.1:18082`; the public catalog returned 57 Datasets, protected `/v1`
  returned `401` without a key, a server-generated admin key authenticated, and
  its plaintext was absent from SQLite.
- The Windows ZIP ran its standalone EXE without Git or Docker on
  `127.0.0.1:18083` with the same version, catalog, authorization, and
  plaintext-key checks.
- Both final smoke tests used independent SQLite Backup API snapshots of the
  working database. The public catalog contained 57 Datasets; the authenticated
  artifact catalog contained 0 local artifacts, matching the current 0 `.bag`
  inventory. The source database remained unchanged at SHA-256
  `ea0ad53e7d8d4f651f4ce30da1be38ce4ba0cd6850869d27e7dfa1298698ea1a`.
- Acceptance runtimes and keys were removed after testing. The existing server
  on port 8081 remained healthy and unchanged.
- Docker Scout analyzed 48 image packages and reported `0 Critical`, `0 High`,
  `0 Medium`, and `0 Low` known vulnerabilities.

## Gates still open

This is local package acceptance, not production approval. A clean Windows VM
test, a clean offline Docker-host test, the verified `F:` runtime migration,
production routing cutover, merge, tags, and GitHub releases remain open. They
require the Change Authority decision recorded for the migration Change.
