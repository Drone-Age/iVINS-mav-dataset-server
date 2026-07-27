# iVINS MAV Dataset Server

A minimal LAN HTTP API around the raw-catalog CLI in the sibling
`iVINS-mav-dataset` registry. It does not duplicate download validation:
registry lookup, resolution, and fetch operations call the existing CLI.

This MVP is for a trusted private LAN only. It binds host port `8080` on
`0.0.0.0` by default and requires `X-API-Key` on every request. Restrict the
port to private-network interfaces/subnets in the host firewall. Never configure
router port forwarding, public cloud exposure, a public reverse proxy, or an
Internet-facing firewall rule. Replace this shared-key design before any wider
network deployment.

## Local configuration

Copy `.env.example` to ignored `.env`. Set:

- `IVINS_REGISTRY_HOST_ROOT`: canonical `iVINS-mav-dataset` checkout.
- `IVINS_RAW_HOST_ROOT`: host DataSets directory.
- `IVINS_IMPORT_HOST_ROOT`: host source subtree mounted read-only at `/imports`.
- `IVINS_BIND_ADDRESS`: host bind address; defaults to `0.0.0.0`.
- `IVINS_PORT`: host port; defaults to `8080`.
- `IVINS_API_KEY`: long random local secret.

Do not commit, print, log, or paste the API key or resolver credentials into
chat. The registry is mounted read-only at `/registry`; only the raw root is
writable at `/data`. Existing raw-root contents are not initialized or reindexed
by starting the service.

Optional OneDrive/Google resolver credentials remain host-provided:

- `IVINS_ONEDRIVE_TOKEN`
- `IVINS_GOOGLE_DRIVE_API_KEY`
- `IVINS_GOOGLE_DRIVE_TOKEN`

## API

All requests require `X-API-Key`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Service health |
| GET | `/v1/datasets/{standard_id}` | Registry format summary |
| GET | `/v1/datasets/{standard_id}/artifacts` | Registry and local artifact states |
| POST | `/v1/datasets/{standard_id}/fetch` | Queue a fetch or supported local conversion with JSON `{"format":"rosbag"}` |
| POST | `/v1/datasets/{standard_id}/import-local` | Queue copy-only ROS1 import with `format` and `source_path` |
| GET | `/v1/jobs/{job_id}` | Inspect in-process job state |
| GET | `/v1/datasets/{standard_id}/artifacts/{format}/download` | Download an already-present file with HTTP Range support |

For a rosbag2 request whose registry artifact is not directly downloadable,
the raw catalog can convert an existing local ROS1 bag with pinned
`rosbags==0.11.3`; the server image includes this non-ROS-runtime dependency.
Conversion uses temporary output, validates the rosbag2 directory, publishes
atomically, preserves the ROS1 source, and refuses overwrite. When the ROS1
source is not local, normal registry fetch rules still apply—local-import and
provenance links are never fetched implicitly.

Fetch returns `409` when neither a directly downloadable artifact nor a usable
conversion source is available. Jobs are held in memory and are lost on restart.
This MVP has no durable queue, cancellation, retry scheduler, or multi-instance
coordination. The container deliberately uses one Gunicorn worker with multiple
threads so all requests see the same in-process job table.

Local import accepts any readable regular `.bag` path in the CLI. Docker cannot
see arbitrary host paths unless they are mounted, so this deployment explicitly
mounts the configured `IVINS_IMPORT_HOST_ROOT` subtree read-only at `/imports`.
The API accepts either a host path below that configured subtree or a container
`/imports/...` path and translates it safely. Broaden/change the mount explicitly
when another source tree is needed; no broader host filesystem is mounted
silently. Import copies through a temporary file, preserves the original,
refuses overwrite, checks free space, hashes the result, and publishes to
`/data/datasets/<family>/<standard-id>/<format>/data.bag`.

The import endpoint is powerful because authenticated LAN clients can request
reads from the configured host subtree. Keep the API key secret, restrict port
8080 to trusted LAN clients, and never expose this endpoint to the Internet.

### curl

Set the key locally without placing it in shell history:

```text
curl -H "X-API-Key: $IVINS_API_KEY" http://SERVER_LAN_IP:8080/health
curl -H "X-API-Key: $IVINS_API_KEY" http://SERVER_LAN_IP:8080/v1/datasets/kv.c
curl -H "X-API-Key: $IVINS_API_KEY" http://SERVER_LAN_IP:8080/v1/datasets/kv.c/artifacts
curl -H "X-API-Key: $IVINS_API_KEY" -H "Content-Type: application/json" -d '{"format":"rosbag"}' http://SERVER_LAN_IP:8080/v1/datasets/kv.c/fetch
curl -H "X-API-Key: $IVINS_API_KEY" -H "Content-Type: application/json" -d '{"format":"rosbag","source_path":"/imports/path/to/data.bag"}' http://SERVER_LAN_IP:8080/v1/datasets/iv.dev.4.ff.1/import-local
curl -H "X-API-Key: $IVINS_API_KEY" -H "Range: bytes=0-1023" http://SERVER_LAN_IP:8080/v1/datasets/kv.c/artifacts/rosbag/download
```

### PowerShell

```text
$headers = @{ "X-API-Key" = $env:IVINS_API_KEY }
Invoke-RestMethod -Headers $headers http://SERVER_LAN_IP:8080/health
Invoke-RestMethod -Headers $headers http://SERVER_LAN_IP:8080/v1/datasets/kv.c
Invoke-RestMethod -Method Post -Headers $headers -ContentType "application/json" -Body '{"format":"rosbag"}' http://SERVER_LAN_IP:8080/v1/datasets/kv.c/fetch
Invoke-RestMethod -Method Post -Headers $headers -ContentType "application/json" -Body '{"format":"rosbag","source_path":"/imports/path/to/data.bag"}' http://SERVER_LAN_IP:8080/v1/datasets/iv.dev.4.ff.1/import-local
```

## Run

```text
docker compose build server
docker compose up -d server
docker compose logs server
docker compose down
```

Run automated tests on the host with:

```text
python -m unittest discover -s tests -p "test_*.py" -v
```

The container runs as UID/GID `10001`, has a read-only root filesystem, drops
all Linux capabilities, enables `no-new-privileges`, and mounts neither the host
home directory nor the Docker socket.
