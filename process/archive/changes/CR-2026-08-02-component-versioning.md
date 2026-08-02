# CR-2026-08-02 — Independent component versioning

- Initiator: repository owner
- Owner: Drone-Age
- Priority: High
- Risk: Medium
- Status: Approved by user request; implemented
- Components: Backend, Frontend, Process, Distribution
- Proposed versions: Backend 3.3.0, Frontend 3.3.0, Process 1.0.0, Distribution 1.0.0

## Problem and objective

The project used one aggregate server version. Introduce independent versions
for Backend, Frontend and Process, where Process covers high-level policies,
permissions, prohibitions, standards, releases, testing, request handling,
incident handling and change requests. Add a technology-neutral Distribution
line and a full offline Docker bundle that needs no Git.

## In scope

- Canonical machine-readable version and compatibility manifest.
- Server-side validation and public version endpoint.
- Separate versions in API responses and both Web interfaces.
- Normative Process 1.0.0 and operational templates.
- Separate changelogs, tags and GitHub releases.
- Distribution 1.0.0, component compatibility and package manifest.
- Offline Docker image archive, Compose, checksums and lifecycle scripts.
- Reserved compatible Windows Installer format.
- Backend 3.3.0 production image and deployment.

## Out of scope

- HTTPS termination; HTTP remains the requested application protocol.
- Database schema or BAG storage migration.
- Changes to API-key roles or existing Dataset data.

## Acceptance criteria

- Backend, Frontend, Process and Distribution use independent valid SemVer values.
- Compatibility is declared and server validated.
- `GET /versions` is public and the UI displays all component versions.
- Process contains the requested policies and operating procedures.
- Distribution bundle installs without Git, build or pull.
- Future Windows Installer can reuse the same component/version contract.
- Automated tests, Compose validation, image build and post-deploy smoke tests pass.
- Each changed component receives an immutable component-prefixed release.

## Security, data and compatibility impact

No authentication boundary or stored Dataset/BAG data is changed. The manifest
is public metadata. `server_version` remains a compatibility alias for Backend.
Deployment reuses the existing persistent data volume after backup.

## Test evidence

- Python compile: passed.
- Docker Compose validation: passed.
- Distribution ZIP and sidecar SHA-256 verification: passed.
- Offline install from the extracted bundle: passed without Git/build/pull.
- Backup-first update and rollback lifecycle smoke test: passed.
- Package/runtime versions matched all four canonical versions.
- Production image build: passed.
- Unit/integration/security suite: 40/40 passed.
- JavaScript syntax: passed.
- Critical/High CVE scan: requires explicit authorization for Docker Scout
  external SBOM metadata transfer before the release gate can close.

## Deployment and rollback

Create a fresh backup of the persistent data directory. Deploy the exact
`ivins-mav-dataset-server:3.3.0` image. Verify `/health`, `/versions`,
the public catalog and restart policy. On failure, restore the Backend 3.2.0
container/image and the backup if any persistent data changed.
