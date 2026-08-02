# Component versioning

[Українська версія](VERSIONING.uk.md)

The repository contains four independently versioned components:

| Component | Scope | Current version | Git tag |
|---|---|---:|---|
| Backend | HTTP API, authentication, storage, database migrations and server runtime | 4.0.0 | `backend-v4.0.0` |
| Frontend | Public catalog and administration Web interface | 4.0.0 | `frontend-v4.0.0` |
| Process dependency | Canonical policies in `DataSetsManager/DataSetsManager` | 2.0.0 | `process-v2.0.0` |
| Distribution | Offline bundles, installers, package manifests and deployment automation | 2.0.0 | `distribution-v2.0.0` |

`versions.json` is the canonical machine-readable manifest. The Backend
loads and validates it at startup and exposes it at `GET /versions`. The same
values are returned by health, session, catalog and administration responses.

Distribution is technology-neutral. A Distribution version may provide one or
more package formats such as `docker-bundle`, `windows-portable` or
`windows-msi`. Adding a
compatible installer format changes Distribution without forcing Backend,
Frontend or Process to change.

## Semantic versioning

Each component follows SemVer independently:

- MAJOR: an incompatible contract, interface or governance change;
- MINOR: a backward-compatible capability or rule;
- PATCH: a backward-compatible correction with no new contract.

A release changes only the components affected by the approved change. An
unchanged component keeps both its version and its existing tag.

Process versions are immutable normative snapshots. Editorial corrections that
can alter interpretation require at least a PATCH release. New permissions,
prohibitions, mandatory gates or responsibilities require MINOR or MAJOR
according to compatibility.

## Compatibility manifest

Compatibility constraints use npm-style SemVer ranges:

```json
{
  "backend": "4.0.0",
  "frontend": "4.0.0",
  "process": "2.0.0",
  "distribution": "2.0.0",
  "compatibility": {
    "frontend_requires_backend": ">=4.0.0 <5.0.0",
    "process_applies_to_backend": ">=4.0.0 <5.0.0",
    "process_applies_to_frontend": ">=4.0.0 <5.0.0",
    "process_applies_to_distribution": ">=2.0.0 <3.0.0",
    "distribution_packages_backend": ">=4.0.0 <5.0.0",
    "distribution_packages_frontend": ">=4.0.0 <5.0.0",
    "distribution_requires_process": ">=2.0.0 <3.0.0"
  }
}
```

The manifest must be updated in the same reviewed commit as any component
version change. A Frontend/Backend pair outside the declared range must not be
deployed. A Process release applies only to the component ranges it declares.

## Release identifiers

New releases use component-prefixed tags:

- `backend-vMAJOR.MINOR.PATCH`;
- `frontend-vMAJOR.MINOR.PATCH`;
- `process-vMAJOR.MINOR.PATCH`;
- `distribution-vMAJOR.MINOR.PATCH`.

Historical aggregate `vX.Y.Z` tags remain valid historical records but are not
used for new component releases. The Docker image tag follows the Backend
version because the Backend is the runtime. Installable ZIP/MSI artifacts
follow the Distribution version and declare all component versions in
`package-manifest.json`. Runtime versions remain discoverable through `/versions`.

Every component release must link the common commit SHA, its component
changelog and the applicable compatibility manifest.
