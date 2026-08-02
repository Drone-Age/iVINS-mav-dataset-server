# iVINS MAV Dataset Server

The compatible bundle contains **Backend 3.3.0**, **Frontend 3.3.0**,
**Process 1.0.0** and **Distribution 1.0.0**. It is a bilingual public Web
catalog for visual-inertial datasets and an authenticated immutable store for
local iVINS artifacts.

The public site at `/` is available without a key. It presents **Datasets** in
family tables modeled after the
[`Drone-Age/iVINS-mav-dataset`](https://github.com/Drone-Age/iVINS-mav-dataset)
registry: stable ID, dataset name, length/size, ROS Bag, ROS Bag2, ground truth
and configuration links. Each Dataset also has a family-scoped iVINS profile;
the available profile filter values follow the selected family.

## Access model

- **Guest**: no key; can browse public Datasets and follow external HTTP/HTTPS
  BAG mirrors. A guest cannot download any file stored on this server.
- **User**: authenticates with a server-generated API key; can also download
  local artifacts using a short-lived single-use download ticket.
- **Admin**: has user access plus an inline Dataset edit mode in the ordinary
  filtered catalog. The mode is off by default. `/admin` remains available for
  API keys, mirrors, uploads, artifacts and BAG files, and opens on Datasets.

The browser keeps an entered API key only in page memory. It is never placed in
a URL, cookie, local storage or session storage, and is forgotten on reload.

Version 3 intentionally serves **HTTP**. HTTP does not protect API keys or
download tickets from observation in transit. For Internet exposure, terminate
TLS at a reverse proxy/router or use a trusted VPN. Do not expose a bearer key
over an untrusted plain-HTTP path.

## Component versions

Backend, Frontend, Process and Distribution use independent SemVer versions.
The canonical
compatibility manifest is [versions.json](versions.json), is validated by the
Backend at startup and is available from `GET /versions`. The legacy
`server_version` response field remains an alias for the Backend version.

New Git tags and GitHub releases use `backend-vX.Y.Z`,
`frontend-vX.Y.Z`, `process-vX.Y.Z` and `distribution-vX.Y.Z`. The Docker image
tag follows Backend; installable bundles follow Distribution. See
[VERSIONING.md](VERSIONING.md) for compatibility and release rules,
[distribution/DISTRIBUTION.md](distribution/DISTRIBUTION.md) for offline
deployment, and [process/PROCESS.md](process/PROCESS.md) for the normative
Process policies and operating procedures.

## Docker quick start

```powershell
Copy-Item .env.example .env
New-Item -ItemType Directory -Path var -Force
docker compose build

# Bootstrap the first admin key locally. The plaintext is shown once.
docker compose run --rm --no-deps server `
  python api_keys.py create --name initial-admin --role admin

docker compose up -d
Invoke-RestMethod http://127.0.0.1:8080/health
```

Open:

- `http://127.0.0.1:8080/` for the public Datasets catalog;
- `http://127.0.0.1:8080/admin` for administration.

## Offline deployment without Git

Distribution 1.0.0 produces a complete ZIP for a target architecture. The
package contains the saved Docker image, an offline Compose file, integrity
manifests and install/update/rollback scripts. It contains no database,
BAG files or API keys.

```powershell
.\tools\build-release-bundle.ps1
```

Copy the generated ZIP and `.sha256` sidecar to the target, verify the
sidecar, extract the ZIP, then run:

```powershell
Copy-Item .env.example .env
.\install.ps1
.\new-admin-key.ps1 -Name initial-admin
```

Deployment needs Docker Engine and Compose, but needs neither Git nor Internet
access. `compose.release.yaml` has no `build` section and uses
`pull_policy: never`. A future native Windows Installer is reserved as an
additional Distribution format and will use the same component compatibility,
data and API-key rules.

See [the Distribution guide](distribution/DISTRIBUTION.md).

## API keys

New keys are always generated on the server and revealed once. The database
stores only a key ID and SHA-256 digest.

```powershell
# User key for protected local downloads
docker compose run --rm --no-deps server `
  python api_keys.py create --name dataset-user --role user

# List metadata without secrets
docker compose run --rm --no-deps server python api_keys.py list

# Revoke immediately
docker compose run --rm --no-deps server `
  python api_keys.py revoke 0123456789abcdef
```

The first admin key is created by CLI. An authenticated admin can create later
`user` or `admin` keys through the Web interface. The Web API prevents revoking
the last active admin key.

## Public Datasets and mirrors

The SQLite catalog has separate `datasets` and `mirrors` records. Mirrors must
use absolute HTTP/HTTPS URLs and are clearly identified as external links. Only
mirrors marked verified are exposed to guests. The server does not proxy or
fetch them.

The bundled initial catalog contains 57 manifest-derived records from:

- EuRoC MAV;
- TUM-VI;
- RPNG AR Table and RPNG OpenVINS;
- UZH-FPV;
- KAIST Urban and KAIST VIO;
- iVINS.

Seed insertion is idempotent and does not overwrite administrator edits.
Admins can add, edit, hide and delete Datasets, and add or remove external
mirrors, through controlled endpoints. Arbitrary SQL is deliberately absent.

### Dataset profiles

`profile` is a lowercase stable identifier such as `all`, `dev_01` or
`dev_04`. When it is omitted or blank, the server stores `all`, meaning that
the Dataset applies to every profile in its family. Profile names are scoped
to a family: the profile selector is enabled after a family is selected and
then lists only that family's specific profiles. Filtering by a specific
profile also includes the family's `all` Datasets.

The administration interface shows and edits the value explicitly. Artifact
upload and manual BAG metadata may also include `profile`; server-side
validation remains authoritative.

On first v3.2 startup, existing Dataset rows are migrated in place without
deletion: missing, blank and former `general` values become `all`. Specific
profiles are preserved, and the bundled `iv.dev.4.ff.1` record remains
classified as `dev_04`.

## Interface languages

Both the public catalog and administration interface can be switched between
Ukrainian and English. Language selection is presentation-only and never
changes Dataset content or authorization state.

## Local artifact downloads

Direct local download routes require a `user` or `admin` bearer key. For a
browser download, the authenticated site requests a 60-second single-use
ticket. Only the ticket digest is stored, and replay returns `404`.

```powershell
$headers = @{ Authorization = "Bearer $env:IVINS_CLIENT_API_KEY" }
$ticket = Invoke-RestMethod `
  http://127.0.0.1:8080/v1/datasets/iv.dev.4.ff.1/artifacts/rosbag/1/download-ticket `
  -Method Post -Headers $headers -ContentType application/json -Body '{}'

Invoke-WebRequest ("http://127.0.0.1:8080" + $ticket.download_url) -OutFile data.bag
```

## HTTP API

| Access | Method | Path | Purpose |
|---|---|---|---|
| Public | `GET` | `/health` | Minimal liveness |
| Public | `GET` | `/public/api/datasets` | Visible Datasets and external mirrors |
| Public | `GET` | `/versions` | Component versions and compatibility |
| Key | `GET` | `/auth/session` | Resolve API-key role |
| User/Admin | `GET` | `/v1/catalog` | Local artifact catalog |
| User/Admin | `GET` | `/v1/datasets/{id}/artifacts/{format}/{version}/download` | Direct authenticated download |
| User/Admin | `POST` | `/v1/datasets/{id}/artifacts/{format}/{version}/download-ticket` | Browser download ticket |
| Admin | `POST` | `/v1/uploads` | Create or recover upload session |
| Admin | `PUT` | `/v1/uploads/{id}/content` | Stream and verify bytes |
| Admin | `POST` | `/v1/uploads/{id}/publish` | Publish immutable version |
| Admin | `*` | `/admin/api/*` | Controlled administration |

Public catalog and download-ticket redemption endpoints have independent
per-address rate limits.

## Storage and backup

The database defaults to `var/catalog.sqlite3`. Every local `.bag` and `.zip`
artifact is a direct child of `var/bags/`; incomplete uploads are under
`var/staging/`. Back up and restore the complete `var/` tree as one unit.

Published `(dataset_id, format, version)` identities remain immutable. An
admin may migrate legacy nested v2 paths into the flat BAG directory only after
server-side size and SHA-256 verification.

## Upgrade to Backend/Frontend 3.3.0, Process 1.0.0 and Distribution 1.0.0

1. Back up the complete `var/` directory.
2. Deploy the Backend 3.3.0 image against the same data directory.
3. Existing `admin` keys remain admins; `reader` and `publisher` keys are
   migrated to `user`.
4. Existing missing, blank and `general` Dataset profiles become `all`; review
   family-specific profiles in the catalog and assign values such as `dev_01`
   where needed.
5. Review the seeded public Datasets and mirrors in `/admin`.
6. Confirm `/health` reports Backend 3.3.0, Frontend 3.3.0, Process 1.0.0
   and Distribution 1.0.0,
   `schema_version: 1.0` and `key_store_ready: true`.
7. Confirm `/versions` matches `versions.json` and the deployed component
   compatibility ranges.

## Verification

```powershell
docker compose config --quiet
docker compose build
docker run --rm --entrypoint python `
  -v "${PWD}:/src:ro" -w /src ivins-mav-dataset-server:3.3.0 `
  -m unittest discover -s tests -v

.\tools\build-release-bundle.ps1 -SkipBuild

docker scout cves ivins-mav-dataset-server:3.3.0 `
  --only-severity critical,high
```

The normative local-artifact contract remains under [`contract/`](contract/).
