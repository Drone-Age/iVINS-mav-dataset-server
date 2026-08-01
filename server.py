#!/usr/bin/env python3
"""Dataset Server v2: authenticated metadata and immutable artifact storage."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import tempfile
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import contextmanager
from pathlib import Path

from flask import Flask, g, jsonify, request, send_file

import api_keys

SCHEMA_VERSION = "1.0"
SERVER_VERSION = "2.0.0"
FORMATS = {"rosbag", "rosbag2"}
ID_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
app = Flask(__name__)


def data_root() -> Path:
    return Path(os.environ.get("IVINS_DATA_ROOT", "var")).resolve()


def database_path() -> Path:
    return Path(os.environ.get("IVINS_DATABASE", data_root() / "catalog.sqlite3")).resolve()


def error(code: str, message: str, status: int, **details):
    payload = {"error": {"code": code, "message": message}}
    if details:
        payload["error"]["details"] = details
    return jsonify(payload), status


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=30000")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS uploads (
          id TEXT PRIMARY KEY, dataset_id TEXT NOT NULL, format TEXT NOT NULL,
          version TEXT NOT NULL, expected_size INTEGER NOT NULL,
          expected_sha256 TEXT NOT NULL, metadata TEXT NOT NULL,
          state TEXT NOT NULL, staged_path TEXT, actual_size INTEGER,
          actual_sha256 TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(dataset_id, format, version)
        );
        CREATE TABLE IF NOT EXISTS artifacts (
          dataset_id TEXT NOT NULL, format TEXT NOT NULL, version TEXT NOT NULL,
          size INTEGER NOT NULL, sha256 TEXT NOT NULL, metadata TEXT NOT NULL,
          storage_path TEXT NOT NULL, published_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY(dataset_id, format, version)
        );
        """
    )
    return db


@contextmanager
def database():
    db = connect()
    try:
        with db:
            yield db
    finally:
        db.close()


class SlidingWindowLimiter:
    def __init__(self, window_seconds: int = 60, max_buckets: int = 10_000):
        self.window_seconds = window_seconds
        self.max_buckets = max_buckets
        self.buckets: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, bucket: str, limit: int) -> tuple[bool, int]:
        if limit <= 0:
            return True, 0
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self.lock:
            if bucket not in self.buckets and len(self.buckets) >= self.max_buckets:
                bucket = "overflow"
            entries = self.buckets[bucket]
            while entries and entries[0] <= cutoff:
                entries.popleft()
            if len(entries) >= limit:
                return False, max(1, math.ceil(entries[0] + self.window_seconds - now))
            entries.append(now)
            return True, 0

    def reset(self) -> None:
        with self.lock:
            self.buckets.clear()


rate_limiter = SlidingWindowLimiter()


def int_setting(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return max(0, value)


def audit_event(event: str, **fields: object) -> None:
    payload = {"event": event, **fields}
    app.logger.info("security_audit %s", json.dumps(payload, sort_keys=True))


def rate_limited(retry_after: int):
    response, status = error("rate_limited", "request rate limit exceeded", 429)
    response.headers["Retry-After"] = str(retry_after)
    return response, status


@app.before_request
def require_api_key():
    if request.path == "/health":
        return None
    if request.path.startswith("/v1/"):
        if request.is_json:
            maximum = int_setting("IVINS_MAX_JSON_BYTES", 64 * 1024)
            if request.content_length is None:
                return error("length_required", "Content-Length is required", 411)
            if request.content_length > maximum:
                return error("payload_too_large", "JSON payload exceeds configured limit", 413)

        remote = request.remote_addr or "unknown"
        allowed, retry_after = rate_limiter.check(
            f"preauth:{remote}", int_setting("IVINS_AUTH_ATTEMPTS_PER_MINUTE", 240)
        )
        if not allowed:
            audit_event("preauth_rate_limited", remote=remote, path=request.path)
            return rate_limited(retry_after)
        if api_keys.active_key_count() == 0:
            audit_event("key_store_unavailable", remote=remote, path=request.path)
            return error("server_not_configured", "no active API key is configured", 503)

        authorization = request.headers.get("Authorization", "")
        token = authorization[7:] if authorization.startswith("Bearer ") else ""
        key_id = api_keys.verify_api_key(token)
        if not key_id:
            allowed, retry_after = rate_limiter.check(
                f"invalid:{remote}", int_setting("IVINS_AUTH_FAILURES_PER_MINUTE", 20)
            )
            if not allowed:
                audit_event("auth_rate_limited", remote=remote, path=request.path)
                return rate_limited(retry_after)
            audit_event("auth_failed", remote=remote, path=request.path)
            response, status = error("unauthorized", "a valid API key is required", 401)
            response.headers["WWW-Authenticate"] = "Bearer"
            return response, status

        allowed, retry_after = rate_limiter.check(
            f"key:{key_id}", int_setting("IVINS_REQUESTS_PER_MINUTE", 120)
        )
        if not allowed:
            audit_event("key_rate_limited", key_id=key_id, remote=remote, path=request.path)
            return rate_limited(retry_after)
        g.api_key_id = key_id
    return None


@app.after_request
def secure_response(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if response.mimetype == "application/json":
        response.headers["Cache-Control"] = "no-store"
    if request.path.startswith("/v1/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
        audit_event(
            "write_request",
            key_id=getattr(g, "api_key_id", None),
            remote=request.remote_addr or "unknown",
            method=request.method,
            path=request.path,
            status=response.status_code,
        )
    return response


def validate_identity(dataset_id: object, fmt: object, version: object):
    if not isinstance(dataset_id, str) or not ID_RE.fullmatch(dataset_id):
        return "dataset_id must be a lowercase stable identifier"
    if fmt not in FORMATS:
        return "format must be rosbag or rosbag2"
    if not isinstance(version, str) or not VERSION_RE.fullmatch(version):
        return "version is invalid"
    return None


def public_metadata(value: object) -> dict:
    if not isinstance(value, dict):
        raise TypeError("metadata must be an object")
    forbidden = {"credential", "token", "secret", "storage_path", "internal_path", "private"}
    def contains_forbidden(item: object) -> bool:
        if isinstance(item, dict):
            return any(
                str(key).lower() in forbidden or contains_forbidden(child)
                for key, child in item.items()
            )
        if isinstance(item, list):
            return any(contains_forbidden(child) for child in item)
        return False
    if contains_forbidden(value):
        raise ValueError("metadata contains a private/internal field")
    allowed = {
        "title", "description", "family", "recording", "profile", "calibrations",
        "links", "derivable_formats",
    }
    return {key: value[key] for key in sorted(value) if key in allowed}


def artifact_file(dataset_id: str, fmt: str, version: str) -> Path:
    suffix = ".bag" if fmt == "rosbag" else ".zip"
    return data_root() / "artifacts" / dataset_id / fmt / f"{version}{suffix}"


@app.get("/health")
def health():
    return jsonify(
        status="ok",
        schema_version=SCHEMA_VERSION,
        server_version=SERVER_VERSION,
        key_store_ready=api_keys.active_key_count() > 0,
    )


def snapshot_payload(db: sqlite3.Connection) -> dict:
    rows = db.execute(
        "SELECT * FROM artifacts ORDER BY dataset_id, format, version"
    ).fetchall()
    datasets: dict[str, dict] = {}
    for row in rows:
        metadata = json.loads(row["metadata"])
        item = datasets.setdefault(
            row["dataset_id"],
            {
                "id": row["dataset_id"],
                **metadata,
                "artifacts": [],
            },
        )
        item["artifacts"].append(
            {
                "format": row["format"],
                "version": row["version"],
                "state": "published",
                "size": row["size"],
                "sha256": row["sha256"],
                "download_url": (
                    f"/v1/datasets/{row['dataset_id']}/artifacts/"
                    f"{row['format']}/{row['version']}/download"
                ),
            }
        )
    canonical = list(datasets.values())
    digest = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "schema_version": SCHEMA_VERSION,
        "snapshot_version": digest,
        "datasets": canonical,
    }


@app.get("/v1/catalog")
def catalog():
    with database() as db:
        return jsonify(snapshot_payload(db))


@app.post("/v1/uploads")
def create_upload():
    body = request.get_json(silent=True) or {}
    dataset_id, fmt, version = body.get("dataset_id"), body.get("format"), body.get("version")
    problem = validate_identity(dataset_id, fmt, version)
    if problem:
        return error("invalid_request", problem, 400)
    size, sha = body.get("size"), body.get("sha256")
    if not isinstance(size, int) or size < 0:
        return error("invalid_request", "size must be a non-negative integer", 400)
    if size > int_setting("IVINS_MAX_UPLOAD_BYTES", 50 * 1024**3):
        return error("payload_too_large", "artifact exceeds configured upload limit", 413)
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{64}", sha):
        return error("invalid_request", "sha256 must be 64 lowercase hex characters", 400)
    try:
        metadata = public_metadata(body.get("metadata", {}))
    except (TypeError, ValueError) as exc:
        return error("invalid_request", str(exc), 400)
    upload_id = uuid.uuid4().hex
    try:
        with database() as db:
            if db.execute(
                "SELECT 1 FROM artifacts WHERE dataset_id=? AND format=? AND version=?",
                (dataset_id, fmt, version),
            ).fetchone():
                return error("immutable_version", "published version already exists", 409)
            existing = db.execute(
                "SELECT * FROM uploads WHERE dataset_id=? AND format=? AND version=?",
                (dataset_id, fmt, version),
            ).fetchone()
            if existing:
                return jsonify(upload_id=existing["id"], state=existing["state"]), 200
            db.execute(
                """INSERT INTO uploads
                (id,dataset_id,format,version,expected_size,expected_sha256,metadata,state)
                VALUES(?,?,?,?,?,?,?,'created')""",
                (upload_id, dataset_id, fmt, version, size, sha, json.dumps(metadata, sort_keys=True)),
            )
    except sqlite3.IntegrityError:
        return error("conflict", "upload identity already exists", 409)
    return jsonify(upload_id=upload_id, state="created", upload_url=f"/v1/uploads/{upload_id}/content"), 201


@app.put("/v1/uploads/<upload_id>/content")
def upload_content(upload_id: str):
    limit = int_setting("IVINS_MAX_UPLOAD_BYTES", 50 * 1024**3)
    with database() as db:
        row = db.execute("SELECT * FROM uploads WHERE id=?", (upload_id,)).fetchone()
        if not row:
            return error("not_found", "unknown upload", 404)
        if row["state"] == "published":
            return error("immutable_version", "upload is already published", 409)
        if row["expected_size"] > limit:
            return error("payload_too_large", "artifact exceeds configured upload limit", 413)
        if request.content_length is None:
            return error("length_required", "Content-Length is required", 411)
        if request.content_length > limit:
            return error("payload_too_large", "upload limit exceeded", 413)
        if request.content_length != row["expected_size"]:
            return error(
                "size_mismatch", "Content-Length does not match declared artifact size", 422,
                expected_size=row["expected_size"], content_length=request.content_length,
            )
        staging = data_root() / "staging"
        staging.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f"{upload_id}.", dir=staging)
        digest, count = hashlib.sha256(), 0
        try:
            with os.fdopen(fd, "wb") as stream:
                while True:
                    chunk = request.stream.read(1024 * 1024)
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > limit:
                        raise OverflowError
                    digest.update(chunk)
                    stream.write(chunk)
                stream.flush()
                os.fsync(stream.fileno())
            actual = digest.hexdigest()
            if count != row["expected_size"] or actual != row["expected_sha256"]:
                Path(temporary).unlink(missing_ok=True)
                db.execute("UPDATE uploads SET state='rejected' WHERE id=?", (upload_id,))
                return error(
                    "checksum_mismatch", "uploaded bytes do not match declared size/checksum", 422,
                    expected_size=row["expected_size"], actual_size=count,
                    expected_sha256=row["expected_sha256"], actual_sha256=actual,
                )
            if row["staged_path"]:
                Path(row["staged_path"]).unlink(missing_ok=True)
            db.execute(
                "UPDATE uploads SET state='verified',staged_path=?,actual_size=?,actual_sha256=? WHERE id=?",
                (temporary, count, actual, upload_id),
            )
        except OverflowError:
            Path(temporary).unlink(missing_ok=True)
            return error("payload_too_large", "upload limit exceeded", 413)
        except Exception:
            Path(temporary).unlink(missing_ok=True)
            raise
    return jsonify(upload_id=upload_id, state="verified", size=count, sha256=actual)


@app.post("/v1/uploads/<upload_id>/publish")
def publish(upload_id: str):
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM uploads WHERE id=?", (upload_id,)).fetchone()
        if not row:
            return error("not_found", "unknown upload", 404)
        if row["state"] != "verified":
            return error("not_verified", "only a verified upload can be published", 409)
        if db.execute(
            "SELECT 1 FROM artifacts WHERE dataset_id=? AND format=? AND version=?",
            (row["dataset_id"], row["format"], row["version"]),
        ).fetchone():
            return error("immutable_version", "published version already exists", 409)
        source = Path(row["staged_path"])
        target = artifact_file(row["dataset_id"], row["format"], row["version"])
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            return error("storage_conflict", "artifact target already exists", 409)
        os.replace(source, target)
        db.execute(
            """INSERT INTO artifacts
            (dataset_id,format,version,size,sha256,metadata,storage_path)
            VALUES(?,?,?,?,?,?,?)""",
            (row["dataset_id"], row["format"], row["version"], row["actual_size"],
             row["actual_sha256"], row["metadata"], str(target)),
        )
        db.execute("UPDATE uploads SET state='published',staged_path=NULL WHERE id=?", (upload_id,))
    return jsonify(
        upload_id=upload_id, state="published", dataset_id=row["dataset_id"],
        format=row["format"], version=row["version"], size=row["actual_size"],
        sha256=row["actual_sha256"],
    )


@app.get("/v1/datasets/<dataset_id>/artifacts/<fmt>/<version>/download")
def download(dataset_id: str, fmt: str, version: str):
    if validate_identity(dataset_id, fmt, version):
        return error("not_found", "unknown artifact", 404)
    with database() as db:
        row = db.execute(
            "SELECT * FROM artifacts WHERE dataset_id=? AND format=? AND version=?",
            (dataset_id, fmt, version),
        ).fetchone()
    if not row:
        return error("not_found", "unknown published artifact", 404)
    path = Path(row["storage_path"]).resolve()
    try:
        path.relative_to((data_root() / "artifacts").resolve())
    except ValueError:
        return error("storage_error", "artifact storage path is invalid", 500)
    return send_file(path, as_attachment=True, conditional=True, etag=row["sha256"])


def main() -> None:
    connect().close()
    api_keys.connect().close()
    if api_keys.active_key_count() == 0:
        app.logger.warning(
            "No active API key. /v1 endpoints will return 503; create one with api_keys.py."
        )
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8080")))


if __name__ == "__main__":
    main()
