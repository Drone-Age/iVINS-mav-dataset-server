# iVINS MAV Dataset Server

Dataset Server v2 is an authenticated catalog and immutable binary store for
iVINS datasets. Published versions cannot be overwritten. Every `/v1/*`
request requires an active server-generated API key.

The application intentionally serves **HTTP**. HTTP does not protect API keys,
metadata, or artifacts from observation or modification in transit. For
Internet use, terminate TLS at a reverse proxy/router or carry HTTP through a
trusted private network or VPN. Do not forward the application port directly
to an untrusted network.

## Docker quick start

```powershell
Copy-Item .env.example .env
New-Item -ItemType Directory -Path var -Force
docker compose build

# Bootstrap the first key locally on the server. The plaintext is shown once.
docker compose run --rm --no-deps server `
  python api_keys.py create --name initial-admin

docker compose up -d
Invoke-RestMethod http://127.0.0.1:8080/health
```

Store the returned `api_key` in a client-side secret store. It is not retained
in plaintext by the server and cannot be recovered later.

## API key administration

Keys can only be created by running the CLI on the server. There is no HTTP key
creation endpoint.

```powershell
# Create and reveal a new key once
docker compose run --rm --no-deps server `
  python api_keys.py create --name publishing-agent

# List ids, labels, creation and revocation timestamps (never secrets)
docker compose run --rm --no-deps server python api_keys.py list

# Revoke immediately without restarting the running server
docker compose run --rm --no-deps server `
  python api_keys.py revoke 0123456789abcdef
```

Keys use 256 bits of CSPRNG entropy. The database stores a key id and SHA-256
digest, not the plaintext token. The legacy `IVINS_API_KEY` environment
variable is ignored by v2 and must be removed from deployments.

## HTTP API

`GET /health` is the only unauthenticated endpoint. It returns minimal liveness,
schema/version and key-store readiness data.

All business requests use the key as a Bearer credential:

```powershell
$headers = @{ Authorization = "Bearer $env:IVINS_CLIENT_API_KEY" }
Invoke-RestMethod http://127.0.0.1:8080/v1/catalog -Headers $headers
```

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Minimal unauthenticated liveness |
| `GET` | `/v1/catalog` | Deterministic published snapshot |
| `POST` | `/v1/uploads` | Create or recover an upload session |
| `PUT` | `/v1/uploads/{id}/content` | Stream and verify declared bytes |
| `POST` | `/v1/uploads/{id}/publish` | Publish a verified immutable version |
| `GET` | `/v1/datasets/{id}/artifacts/{format}/{version}/download` | Download immutable bytes with Range support |

The server returns `401` for a missing, malformed, unknown, or revoked key;
`503` when no active key exists; and `429` with `Retry-After` when a rate limit
is exceeded.

## Security controls

- every `/v1/*` route requires an active key;
- independent per-key and failed-authentication rate limits;
- JSON and streaming upload size enforcement, including `Content-Length`;
- identifiers, metadata, storage paths, checksums and immutable versions are
  validated server-side;
- structured security audit events never include credentials;
- the container is non-root with a read-only root filesystem, no Linux
  capabilities and `no-new-privileges`;
- Compose limits memory, CPU and process count;
- the runtime image contains only Flask and Gunicorn dependencies.

The default limits are configurable in `.env`: `IVINS_MAX_UPLOAD_BYTES`,
`IVINS_MAX_JSON_BYTES`, `IVINS_REQUESTS_PER_MINUTE`,
`IVINS_AUTH_ATTEMPTS_PER_MINUTE`, `IVINS_AUTH_FAILURES_PER_MINUTE`,
`IVINS_MEMORY_LIMIT`, `IVINS_CPU_LIMIT` and `IVINS_PIDS_LIMIT`.

## Storage and backup

The database defaults to `var/catalog.sqlite3`; binaries are below
`var/artifacts/`, and incomplete uploads below `var/staging/`. Back up and
restore the entire `var/` tree as one unit. Restrict host filesystem access to
the service administrator, `SYSTEM`, and the Docker runtime.

Published `(dataset_id, format, version)` identities are immutable. Public
metadata rejects credential, token, secret and internal path fields at any
nesting depth.

## Upgrade from v1

Version 2.0.0 is intentionally breaking:

1. Pull/build the v2 image while the old service remains available.
2. Remove `IVINS_API_KEY` from `.env`; it is not migrated.
3. Preserve and back up the existing `var/` directory.
4. Run `api_keys.py create` against that same data directory.
5. Start v2 and update clients to send `Authorization: Bearer <key>` on every
   `/v1/*` request, including catalog and downloads.
6. Confirm `/health` reports `server_version: 2.0.0` and
   `key_store_ready: true`.

## Verification

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m unittest discover -s tests -v

docker compose config --quiet
docker compose build
docker scout cves ivins-mav-dataset-server:2.0.0 `
  --only-severity critical,high
```

The normative catalog schema and fixture remain in [`contract/`](contract/).
