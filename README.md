# iVINS MAV Dataset Server

Dataset Server v1 is the authoritative catalog and binary store for the public
iVINS dataset storefront. Published versions are immutable. Draft uploads and
internal storage details never appear in the anonymous public projection.

## Run locally

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
$env:IVINS_API_KEY = "replace-with-a-long-random-value"
$env:IVINS_DATA_ROOT = "var"
.venv\Scripts\python server.py
```

The database defaults to `var/catalog.sqlite3`; binaries are stored below
`var/artifacts/`, and incomplete uploads below `var/staging/`. Back up the
database and artifact tree together. `var/` and `.env` are ignored. The service
binds to `127.0.0.1` unless `HOST` is explicitly configured. TLS and publisher
credential rotation belong at the deployment boundary.

## Dataset Server v1 contract

Anonymous:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Health and schema version |
| `GET` | `/v1/catalog` | Deterministic published-only snapshot |
| `GET` | `/v1/datasets/{id}/artifacts/{format}/{version}/download` | Immutable bytes with Range support |

Publisher (`Authorization: Bearer …`, with `X-API-Key` retained as a local
compatibility header):

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/uploads` | Create/idempotently recover an upload session |
| `PUT` | `/v1/uploads/{id}/content` | Stream bytes and verify declared size/SHA-256 |
| `POST` | `/v1/uploads/{id}/publish` | Atomically move a verified draft into the public catalog |

`POST /v1/uploads` accepts `dataset_id`, `format`, `version`, `size`, `sha256`,
and public `metadata`. Identifiers are validated, the maximum streaming size is
controlled by `IVINS_MAX_UPLOAD_BYTES`, checksum failures become rejected
drafts, and an existing published `(dataset_id, format, version)` is never
overwritten. Errors use `{"error":{"code":"…","message":"…","details":{…}}}`.
Credentials are neither returned nor logged by application code.

The normative public schema and interoperable fixture are in [`contract/`](contract/).
The fixture represents `iv.dev.4.ff.1`; its tiny artifact digest is deliberately
test data, not a claim about the production recording.

## Verification

```powershell
.venv\Scripts\python -m unittest discover -s tests -v
```

The suite covers anonymous reads, authentication failure, streamed upload,
checksum rejection, atomic publication, immutable versions, deterministic
snapshots, private-field exclusion, traversal/identifier validation, HTTP Range,
and byte-identical download. Production deployment is intentionally outside v1.
