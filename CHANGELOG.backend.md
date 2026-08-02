# Backend changelog

## 4.0.0 — 2026-08-02

- Renamed the runtime to DataSetsManager Server without changing `/v1` routes.
- Added canonical `DSM_*` settings with one-major `IVINS_*` compatibility.
- Added canonical profile aliases and safe in-place database normalization.
- New API keys use `dsm_`; existing `ivins_` keys remain valid through 4.x.

## 3.3.0 — 2026-08-02

- Added a validated canonical component-version manifest.
- Added public `GET /versions` and component versions to API status responses.
- Retained `server_version` as a backward-compatible Backend alias.
- Bundled and exposed Process compatibility for automated deployment checks.

## 3.2.0 — 2026-08-02

- Added family-scoped profiles and normalized the default profile to `all`.
