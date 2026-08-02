# iVINS Distribution

Distribution is the independently versioned delivery layer for iVINS Dataset
Server. It packages compatible Backend, Frontend and Process versions into one
installable artifact without changing their component versions.

Current Distribution version: **1.0.0**

## Package formats

- `docker-bundle`: implemented in Distribution 1.0.0. Deployment requires
  Docker Engine with Compose but does not require Git or Internet access.
- `windows-installer`: reserved for a future native Windows Service installer.
  It will reuse the same package manifest, compatibility rules, persistent data
  contract and server-generated API-key policy.

Adding a compatible package format increments Distribution MINOR. Breaking the
package manifest, installer command contract or upgrade/rollback behavior
increments Distribution MAJOR. Corrections increment PATCH.

## Offline Docker bundle

The generated ZIP contains:

- the complete Docker image as an `images/*.tar` archive;
- `compose.release.yaml` with no `build` section and `pull_policy: never`;
- `package-manifest.json` and the canonical `versions.json`;
- `SHA256SUMS` plus a SHA-256 sidecar for the ZIP;
- `install.ps1`, `update.ps1`, `rollback.ps1`,
  `verify.ps1` and `new-admin-key.ps1`;
- Process, versioning and component changelog documents.

The package never contains API keys, the SQLite database, BAG files or other
runtime data. The data directory remains external and persistent across
Distribution changes.

## Build

From a source tree with Docker Buildx:

```powershell
.\tools\build-release-bundle.ps1
```

The default target is `linux/amd64`. Another single target can be produced with
`-Platform linux/arm64`. The output is under `dist/` and can be copied to an
offline server.

## Install without Git

Extract the ZIP and run:

```powershell
Copy-Item .env.example .env
.\install.ps1
.\new-admin-key.ps1 -Name initial-admin
```

The installer verifies every bundled file, loads the image locally, validates
Compose, starts the service, checks `/health` and `/versions`, and confirms
that the deployed component versions match the package manifest.

Use `update.ps1` for a backup-first update. Use `rollback.ps1` with the
path to a previously extracted bundle. Automatic rollback does not restore
runtime data; restore data only from a separately verified backup when a data
migration requires it.
