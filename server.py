#!/usr/bin/env python3
"""Dataset Server v2: authenticated metadata and immutable artifact storage."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import secrets
import sqlite3
import tempfile
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, g, jsonify, render_template, request, send_file

import api_keys

SCHEMA_VERSION = "1.0"
SERVER_VERSION = "3.1.0"
FORMATS = {"rosbag", "rosbag2"}
ID_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
PROFILE_RE = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")
DATASET_SEED_VERSION = "2026-08-02.2"
app = Flask(__name__)


def data_root() -> Path:
    return Path(os.environ.get("IVINS_DATA_ROOT", "var")).resolve()


def database_path() -> Path:
    return Path(os.environ.get("IVINS_DATABASE", data_root() / "catalog.sqlite3")).resolve()


def bag_root() -> Path:
    return Path(os.environ.get("IVINS_BAG_ROOT", data_root() / "bags")).resolve()


def seed_datasets(db: sqlite3.Connection) -> None:
    current = db.execute(
        "SELECT value FROM app_settings WHERE key='dataset_seed_version'"
    ).fetchone()
    if current and current["value"] == DATASET_SEED_VERSION:
        return
    seed_path = Path(__file__).resolve().parent / "seed" / "datasets.json"
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    if payload.get("version") != DATASET_SEED_VERSION:
        raise RuntimeError("dataset seed version mismatch")
    for item in payload["datasets"]:
        db.execute(
            "INSERT OR IGNORE INTO datasets "
            "(id,family,profile,name,description,measurement,homepage_url,"
            "ground_truth_url,config_url,visible) VALUES(?,?,?,?,?,?,?,?,?,1)",
            (
                item["id"], item["family"], item.get("profile", "general"),
                item["name"], item.get("description", ""), item.get("measurement", ""),
                item.get("homepage_url"),
                item.get("ground_truth_url"), item.get("config_url"),
            ),
        )
        for mirror in item.get("mirrors", []):
            db.execute(
                "INSERT OR IGNORE INTO mirrors(dataset_id,format,label,url,verified) "
                "VALUES(?,?,?,?,?)",
                (
                    item["id"], mirror["format"], mirror["label"], mirror["url"],
                    int(mirror.get("verified", False)),
                ),
            )
    db.execute(
        "INSERT INTO app_settings(key,value) VALUES('dataset_seed_version',?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (DATASET_SEED_VERSION,),
    )


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
        CREATE TABLE IF NOT EXISTS datasets (
          id TEXT PRIMARY KEY,
          family TEXT NOT NULL,
          profile TEXT NOT NULL DEFAULT 'general',
          name TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          measurement TEXT NOT NULL DEFAULT '',
          homepage_url TEXT,
          ground_truth_url TEXT,
          config_url TEXT,
          visible INTEGER NOT NULL DEFAULT 1 CHECK(visible IN (0,1)),
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS mirrors (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
          format TEXT NOT NULL CHECK(format IN ('rosbag','rosbag2')),
          label TEXT NOT NULL,
          url TEXT NOT NULL,
          verified INTEGER NOT NULL DEFAULT 0 CHECK(verified IN (0,1)),
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE(dataset_id, format, url)
        );
        CREATE TABLE IF NOT EXISTS download_tickets (
          token_digest TEXT PRIMARY KEY,
          key_id TEXT NOT NULL,
          dataset_id TEXT NOT NULL,
          format TEXT NOT NULL,
          version TEXT NOT NULL,
          expires_at REAL NOT NULL,
          used_at REAL
        );
        CREATE TABLE IF NOT EXISTS app_settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS mirrors_dataset_idx ON mirrors(dataset_id);
        CREATE INDEX IF NOT EXISTS tickets_expiry_idx ON download_tickets(expires_at);
        """
    )
    dataset_columns = {row[1] for row in db.execute("PRAGMA table_info(datasets)")}
    profile_added = "profile" not in dataset_columns
    if profile_added:
        db.execute(
            "ALTER TABLE datasets ADD COLUMN profile TEXT NOT NULL DEFAULT 'general'"
        )
    db.execute("UPDATE datasets SET profile='general' WHERE profile IS NULL OR profile=''")
    if profile_added:
        db.execute(
            "UPDATE datasets SET profile='dev_04' WHERE id='iv.dev.4.ff.1'"
        )
    seed_datasets(db)
    db.commit()
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
    if request.path.startswith("/public/api/"):
        allowed, retry_after = rate_limiter.check(
            f"public:{request.remote_addr or 'unknown'}",
            int_setting("IVINS_PUBLIC_REQUESTS_PER_MINUTE", 120),
        )
        return None if allowed else rate_limited(retry_after)
    if request.path.startswith("/downloads/"):
        allowed, retry_after = rate_limiter.check(
            f"ticket:{request.remote_addr or 'unknown'}",
            int_setting("IVINS_DOWNLOADS_PER_MINUTE", 30),
        )
        return None if allowed else rate_limited(retry_after)
    protected = request.path.startswith(("/v1/", "/admin/api/", "/auth/"))
    if protected:
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
        identity = api_keys.authenticate_api_key(token)
        if not identity:
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
            f"key:{identity.key_id}", int_setting("IVINS_REQUESTS_PER_MINUTE", 120)
        )
        if not allowed:
            audit_event(
                "key_rate_limited", key_id=identity.key_id, remote=remote, path=request.path
            )
            return rate_limited(retry_after)
        if request.path.startswith("/admin/api/") and identity.role != "admin":
            audit_event(
                "admin_forbidden",
                key_id=identity.key_id,
                role=identity.role,
                remote=remote,
                path=request.path,
            )
            return error("forbidden", "an admin API key is required", 403)
        ticket_request = request.path.endswith("/download-ticket") and request.method == "POST"
        if (
            request.path.startswith("/v1/")
            and request.method not in {"GET", "HEAD", "OPTIONS"}
            and identity.role != "admin"
            and not ticket_request
        ):
            return error("forbidden", "an admin API key is required", 403)
        g.api_key_id = identity.key_id
        g.api_key_role = identity.role
    return None


@app.after_request
def secure_response(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.path in {"/", "/admin"} or request.path.startswith(
        ("/static/site", "/static/admin")
    ):
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self'; frame-ancestors 'none'"
        )
    else:
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    response.headers["X-Frame-Options"] = "DENY"
    if response.mimetype == "application/json":
        response.headers["Cache-Control"] = "no-store"
    if (
        request.path.startswith(("/v1/", "/admin/api/", "/auth/"))
        and request.method not in {"GET", "HEAD", "OPTIONS"}
    ):
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


def bounded_text(value: object, field: str, maximum: int, required: bool = False) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise TypeError(f"{field} must be text")
    result = value.strip()
    if required and not result:
        raise ValueError(f"{field} is required")
    if len(result) > maximum or any(ord(char) < 32 for char in result):
        raise ValueError(f"{field} is invalid")
    return result


def external_url(value: object, field: str) -> str | None:
    if value in {None, ""}:
        return None
    url = bounded_text(value, field, 2048, required=True)
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(f"{field} must be an absolute HTTP/HTTPS URL")
    return url


def normalize_profile(value: object) -> str:
    if value is None:
        return "general"
    if not isinstance(value, str):
        raise TypeError("profile must be text")
    profile = value.strip()
    if not profile:
        return "general"
    if len(profile) > 64 or not PROFILE_RE.fullmatch(profile):
        raise ValueError("profile must be a lowercase stable identifier")
    return profile


def dataset_fields(body: object, include_id: bool) -> dict[str, object]:
    if not isinstance(body, dict):
        raise TypeError("JSON object is required")
    values: dict[str, object] = {
        "family": bounded_text(body.get("family"), "family", 80, required=True),
        "profile": normalize_profile(body.get("profile")),
        "name": bounded_text(body.get("name"), "name", 160, required=True),
        "description": bounded_text(body.get("description"), "description", 2000),
        "measurement": bounded_text(body.get("measurement"), "measurement", 64),
        "homepage_url": external_url(body.get("homepage_url"), "homepage_url"),
        "ground_truth_url": external_url(
            body.get("ground_truth_url"), "ground_truth_url"
        ),
        "config_url": external_url(body.get("config_url"), "config_url"),
    }
    visible = body.get("visible", True)
    if not isinstance(visible, bool):
        raise TypeError("visible must be boolean")
    values["visible"] = int(visible)
    if include_id:
        dataset_id = body.get("id")
        if not isinstance(dataset_id, str) or not ID_RE.fullmatch(dataset_id):
            raise ValueError("id must be a lowercase stable identifier")
        values["id"] = dataset_id
    return values


def mirror_fields(body: object) -> dict[str, object]:
    if not isinstance(body, dict):
        raise TypeError("JSON object is required")
    fmt = body.get("format")
    if fmt not in FORMATS:
        raise ValueError("format must be rosbag or rosbag2")
    verified = body.get("verified", False)
    if not isinstance(verified, bool):
        raise TypeError("verified must be boolean")
    url = external_url(body.get("url"), "url")
    if not url:
        raise ValueError("url is required")
    return {
        "format": fmt,
        "label": bounded_text(body.get("label"), "label", 80, required=True),
        "url": url,
        "verified": int(verified),
    }


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
    result = {key: value[key] for key in sorted(value) if key in allowed}
    if "profile" in result:
        result["profile"] = normalize_profile(result["profile"])
    return result


def artifact_file(dataset_id: str, fmt: str, version: str) -> Path:
    suffix = ".bag" if fmt == "rosbag" else ".zip"
    return bag_root() / f"{dataset_id}__{fmt}__{version}{suffix}"


@app.get("/health")
def health():
    return jsonify(
        status="ok",
        schema_version=SCHEMA_VERSION,
        server_version=SERVER_VERSION,
        key_store_ready=api_keys.active_key_count() > 0,
    )


@app.get("/admin")
def admin_page():
    return render_template("admin.html", server_version=SERVER_VERSION)


@app.get("/")
def public_page():
    return render_template("site.html", server_version=SERVER_VERSION)


@app.get("/auth/session")
def authenticated_session():
    return jsonify(
        key_id=g.api_key_id,
        role=g.api_key_role,
        user_type="Адмін" if g.api_key_role == "admin" else "Користувач",
        server_version=SERVER_VERSION,
    )


def public_dataset_items(db: sqlite3.Connection) -> list[dict[str, object]]:
    dataset_rows = db.execute(
        "SELECT * FROM datasets WHERE visible=1 "
        "ORDER BY family COLLATE NOCASE,name COLLATE NOCASE,id"
    ).fetchall()
    mirror_rows = db.execute(
        "SELECT id,dataset_id,format,label,url,verified FROM mirrors "
        "WHERE verified=1 ORDER BY dataset_id,format,id"
    ).fetchall()
    artifact_rows = db.execute(
        "SELECT dataset_id,format,version,size,sha256,storage_path FROM artifacts "
        "ORDER BY dataset_id,format,version"
    ).fetchall()
    mirrors: dict[str, list[dict[str, object]]] = defaultdict(list)
    local: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in mirror_rows:
        mirrors[row["dataset_id"]].append({
            "format": row["format"],
            "label": row["label"],
            "url": row["url"],
            "verified": bool(row["verified"]),
        })
    root = bag_root().resolve()
    for row in artifact_rows:
        stored = Path(row["storage_path"])
        resolved = stored.resolve()
        available = not stored.is_symlink() and resolved.parent == root and resolved.is_file()
        local[row["dataset_id"]].append({
            "format": row["format"],
            "version": row["version"],
            "size": row["size"],
            "sha256": row["sha256"],
            "available": available,
            "requires_auth": True,
        })
    return [
        {
            "id": row["id"],
            "family": row["family"],
            "profile": row["profile"],
            "name": row["name"],
            "description": row["description"],
            "measurement": row["measurement"],
            "homepage_url": row["homepage_url"],
            "ground_truth_url": row["ground_truth_url"],
            "config_url": row["config_url"],
            "mirrors": mirrors[row["id"]],
            "local_artifacts": local[row["id"]],
        }
        for row in dataset_rows
    ]


@app.get("/public/api/datasets")
def public_datasets():
    with database() as db:
        items = public_dataset_items(db)
    return jsonify(
        datasets=items,
        families=sorted({item["family"] for item in items}, key=str.casefold),
        profiles=sorted({item["profile"] for item in items}, key=str.casefold),
        total=len(items),
        server_version=SERVER_VERSION,
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
        metadata = json.loads(row["metadata"])
        db.execute(
            "INSERT OR IGNORE INTO datasets"
            "(id,family,profile,name,description,visible) VALUES(?,?,?,?,?,1)",
            (
                row["dataset_id"], metadata.get("family", "iVINS"),
                normalize_profile(metadata.get("profile")),
                metadata.get("title", row["dataset_id"]), metadata.get("description", ""),
            ),
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
    stored_path = Path(row["storage_path"])
    path = stored_path.resolve()
    if stored_path.is_symlink() or path.parent != bag_root().resolve():
        return error("storage_error", "artifact storage path is invalid", 500)
    return send_file(path, as_attachment=True, conditional=True, etag=row["sha256"])


@app.post("/v1/datasets/<dataset_id>/artifacts/<fmt>/<version>/download-ticket")
def create_download_ticket(dataset_id: str, fmt: str, version: str):
    if validate_identity(dataset_id, fmt, version):
        return error("not_found", "unknown artifact", 404)
    with database() as db:
        row = db.execute(
            "SELECT storage_path FROM artifacts WHERE dataset_id=? AND format=? AND version=?",
            (dataset_id, fmt, version),
        ).fetchone()
        if not row:
            return error("not_found", "unknown published artifact", 404)
        stored = Path(row["storage_path"])
        resolved = stored.resolve()
        if stored.is_symlink() or resolved.parent != bag_root().resolve() or not resolved.is_file():
            return error("storage_error", "artifact storage path is invalid", 409)
        now = time.time()
        db.execute(
            "DELETE FROM download_tickets WHERE expires_at<? OR used_at IS NOT NULL",
            (now - 300,),
        )
        token = secrets.token_urlsafe(32)
        expires_at = now + 60
        db.execute(
            "INSERT INTO download_tickets"
            "(token_digest,key_id,dataset_id,format,version,expires_at) VALUES(?,?,?,?,?,?)",
            (
                hashlib.sha256(token.encode()).hexdigest(), g.api_key_id, dataset_id,
                fmt, version, expires_at,
            ),
        )
    audit_event(
        "download_ticket_created",
        key_id=g.api_key_id,
        dataset_id=dataset_id,
        format=fmt,
        version=version,
    )
    return jsonify(
        download_url=f"/downloads/{token}",
        expires_in=60,
        single_use=True,
    ), 201


@app.get("/downloads/<token>")
def redeem_download_ticket(token: str):
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", token):
        return error("not_found", "download ticket not found", 404)
    digest = hashlib.sha256(token.encode()).hexdigest()
    now = time.time()
    with database() as db:
        row = db.execute(
            "SELECT t.dataset_id,t.format,t.version,a.storage_path,a.sha256 "
            "FROM download_tickets t JOIN artifacts a "
            "ON a.dataset_id=t.dataset_id AND a.format=t.format AND a.version=t.version "
            "WHERE t.token_digest=? AND t.used_at IS NULL AND t.expires_at>=?",
            (digest, now),
        ).fetchone()
        if not row:
            return error("not_found", "download ticket not found", 404)
        stored = Path(row["storage_path"])
        resolved = stored.resolve()
        if stored.is_symlink() or resolved.parent != bag_root().resolve() or not resolved.is_file():
            return error("not_found", "download ticket not found", 404)
        result = db.execute(
            "UPDATE download_tickets SET used_at=? "
            "WHERE token_digest=? AND used_at IS NULL AND expires_at>=?",
            (now, digest, now),
        )
        if result.rowcount != 1:
            return error("not_found", "download ticket not found", 404)
    response = send_file(
        resolved, as_attachment=True, conditional=False, etag=row["sha256"]
    )
    response.headers["Cache-Control"] = "private, no-store"
    return response


def pagination() -> tuple[int, int, int]:
    try:
        page = max(1, int(request.args.get("page", "1")))
        per_page = min(100, max(1, int(request.args.get("per_page", "50"))))
    except ValueError:
        page, per_page = 1, 50
    return page, per_page, (page - 1) * per_page


def direct_bag_path(filename: object) -> Path | None:
    if not isinstance(filename, str) or not filename or Path(filename).name != filename:
        return None
    root = bag_root().resolve()
    candidate = root / filename
    if candidate.is_symlink():
        return None
    resolved = candidate.resolve()
    return resolved if resolved.parent == root else None


def artifact_admin_item(row: sqlite3.Row) -> dict[str, object]:
    stored_path = Path(row["storage_path"])
    symlink = stored_path.is_symlink()
    path = stored_path.resolve()
    root = bag_root().resolve()
    is_flat = path.parent == root and not symlink
    return {
        "dataset_id": row["dataset_id"],
        "format": row["format"],
        "version": row["version"],
        "size": row["size"],
        "sha256": row["sha256"],
        "metadata": json.loads(row["metadata"]),
        "filename": path.name,
        "file_exists": path.is_file(),
        "flat_storage": is_flat,
        "published_at": row["published_at"],
    }


def file_digest(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def copy_file_exclusive(source: Path, target: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    created = False
    try:
        with source.open("rb") as reader, target.open("xb") as writer:
            created = True
            while chunk := reader.read(1024 * 1024):
                writer.write(chunk)
                digest.update(chunk)
                size += len(chunk)
            writer.flush()
            os.fsync(writer.fileno())
    except Exception:
        if created:
            target.unlink(missing_ok=True)
        raise
    return size, digest.hexdigest()


@app.get("/admin/api/session")
def admin_session():
    return jsonify(
        key_id=g.api_key_id,
        role=g.api_key_role,
        server_version=SERVER_VERSION,
    )


@app.get("/admin/api/overview")
def admin_overview():
    root = bag_root()
    root.mkdir(parents=True, exist_ok=True)
    with database() as db:
        uploads = db.execute("SELECT COUNT(*) AS count FROM uploads").fetchone()["count"]
        artifacts = db.execute("SELECT COUNT(*) AS count FROM artifacts").fetchone()["count"]
        datasets = db.execute("SELECT COUNT(*) AS count FROM datasets").fetchone()["count"]
        mirrors = db.execute("SELECT COUNT(*) AS count FROM mirrors").fetchone()["count"]
        storage_rows = db.execute("SELECT storage_path FROM artifacts").fetchall()
    bag_files = [
        item for item in root.iterdir()
        if item.is_file() and not item.is_symlink() and item.suffix.lower() in {".bag", ".zip"}
    ]
    return jsonify(
        server_version=SERVER_VERSION,
        schema_version=SCHEMA_VERSION,
        active_keys=api_keys.active_key_count(),
        uploads=uploads,
        artifacts=artifacts,
        datasets=datasets,
        mirrors=mirrors,
        bag_files=len(bag_files),
        bag_bytes=sum(item.stat().st_size for item in bag_files),
        missing_files=sum(not Path(row["storage_path"]).is_file() for row in storage_rows),
        legacy_files=sum(
            Path(row["storage_path"]).resolve().parent != root.resolve()
            or Path(row["storage_path"]).is_symlink()
            for row in storage_rows
        ),
        bag_root=str(root),
    )


def admin_dataset_item(db: sqlite3.Connection, row: sqlite3.Row) -> dict[str, object]:
    mirrors = db.execute(
        "SELECT id,format,label,url,verified,created_at FROM mirrors "
        "WHERE dataset_id=? ORDER BY format,id",
        (row["id"],),
    ).fetchall()
    local_count = db.execute(
        "SELECT COUNT(*) FROM artifacts WHERE dataset_id=?", (row["id"],)
    ).fetchone()[0]
    item = dict(row)
    item["visible"] = bool(item["visible"])
    item["mirrors"] = [
        {**dict(mirror), "verified": bool(mirror["verified"])} for mirror in mirrors
    ]
    item["local_artifacts"] = local_count
    return item


@app.route("/admin/api/datasets", methods=["GET", "POST"])
def admin_datasets():
    if request.method == "GET":
        page, per_page, offset = pagination()
        with database() as db:
            total = db.execute("SELECT COUNT(*) FROM datasets").fetchone()[0]
            rows = db.execute(
                "SELECT * FROM datasets ORDER BY family COLLATE NOCASE,"
                "name COLLATE NOCASE,id LIMIT ? OFFSET ?",
                (per_page, offset),
            ).fetchall()
            items = [admin_dataset_item(db, row) for row in rows]
        return jsonify(items=items, total=total, page=page, per_page=per_page)
    try:
        values = dataset_fields(request.get_json(silent=True), include_id=True)
    except (TypeError, ValueError) as exc:
        return error("invalid_request", str(exc), 400)
    try:
        with database() as db:
            db.execute(
                "INSERT INTO datasets"
                "(id,family,profile,name,description,measurement,homepage_url,"
                "ground_truth_url,config_url,visible) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    values["id"], values["family"], values["profile"], values["name"],
                    values["description"], values["measurement"], values["homepage_url"],
                    values["ground_truth_url"], values["config_url"], values["visible"],
                ),
            )
    except sqlite3.IntegrityError:
        return error("dataset_exists", "dataset id already exists", 409)
    audit_event("admin_dataset_created", actor_key_id=g.api_key_id, dataset_id=values["id"])
    return jsonify(id=values["id"]), 201


@app.patch("/admin/api/datasets/<dataset_id>")
def admin_update_dataset(dataset_id: str):
    if not ID_RE.fullmatch(dataset_id):
        return error("not_found", "dataset not found", 404)
    try:
        values = dataset_fields(request.get_json(silent=True), include_id=False)
    except (TypeError, ValueError) as exc:
        return error("invalid_request", str(exc), 400)
    with database() as db:
        result = db.execute(
            "UPDATE datasets SET family=?,profile=?,name=?,description=?,measurement=?,"
            "homepage_url=?,ground_truth_url=?,config_url=?,visible=?,"
            "updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (
                values["family"], values["profile"], values["name"], values["description"],
                values["measurement"], values["homepage_url"],
                values["ground_truth_url"], values["config_url"], values["visible"],
                dataset_id,
            ),
        )
    if result.rowcount != 1:
        return error("not_found", "dataset not found", 404)
    audit_event("admin_dataset_updated", actor_key_id=g.api_key_id, dataset_id=dataset_id)
    return jsonify(id=dataset_id)


@app.delete("/admin/api/datasets/<dataset_id>")
def admin_delete_dataset(dataset_id: str):
    if not ID_RE.fullmatch(dataset_id):
        return error("not_found", "dataset not found", 404)
    with database() as db:
        if db.execute(
            "SELECT 1 FROM artifacts WHERE dataset_id=?", (dataset_id,)
        ).fetchone():
            return error(
                "local_artifacts_exist",
                "delete local artifacts before deleting this dataset",
                409,
            )
        result = db.execute("DELETE FROM datasets WHERE id=?", (dataset_id,))
    if result.rowcount != 1:
        return error("not_found", "dataset not found", 404)
    audit_event("admin_dataset_deleted", actor_key_id=g.api_key_id, dataset_id=dataset_id)
    return jsonify(deleted=dataset_id)


@app.post("/admin/api/datasets/<dataset_id>/mirrors")
def admin_create_mirror(dataset_id: str):
    if not ID_RE.fullmatch(dataset_id):
        return error("not_found", "dataset not found", 404)
    try:
        values = mirror_fields(request.get_json(silent=True))
    except (TypeError, ValueError) as exc:
        return error("invalid_request", str(exc), 400)
    try:
        with database() as db:
            if not db.execute("SELECT 1 FROM datasets WHERE id=?", (dataset_id,)).fetchone():
                return error("not_found", "dataset not found", 404)
            cursor = db.execute(
                "INSERT INTO mirrors(dataset_id,format,label,url,verified) VALUES(?,?,?,?,?)",
                (
                    dataset_id, values["format"], values["label"], values["url"],
                    values["verified"],
                ),
            )
            mirror_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return error("mirror_exists", "mirror already exists", 409)
    audit_event(
        "admin_mirror_created",
        actor_key_id=g.api_key_id,
        dataset_id=dataset_id,
        mirror_id=mirror_id,
    )
    return jsonify(id=mirror_id), 201


@app.delete("/admin/api/mirrors/<int:mirror_id>")
def admin_delete_mirror(mirror_id: int):
    with database() as db:
        result = db.execute("DELETE FROM mirrors WHERE id=?", (mirror_id,))
    if result.rowcount != 1:
        return error("not_found", "mirror not found", 404)
    audit_event("admin_mirror_deleted", actor_key_id=g.api_key_id, mirror_id=mirror_id)
    return jsonify(deleted=mirror_id)


@app.route("/admin/api/keys", methods=["GET", "POST"])
def admin_keys():
    if request.method == "GET":
        keys = api_keys.list_api_keys()
        page, per_page, offset = pagination()
        return jsonify(
            items=keys[offset:offset + per_page],
            total=len(keys),
            page=page,
            per_page=per_page,
        )
    body = request.get_json(silent=True) or {}
    try:
        key_id, token = api_keys.create_api_key(body.get("name", ""), body.get("role", "user"))
    except ValueError as exc:
        return error("invalid_request", str(exc), 400)
    audit_event(
        "admin_key_created",
        actor_key_id=g.api_key_id,
        created_key_id=key_id,
        role=body.get("role", "user"),
    )
    return jsonify(
        key_id=key_id,
        role=body.get("role", "user"),
        api_key=token,
        warning="The API key is shown once and is not stored in plaintext.",
    ), 201


@app.post("/admin/api/keys/<key_id>/revoke")
def admin_revoke_key(key_id: str):
    outcome = api_keys.revoke_api_key_guarded(key_id)
    if outcome == "not_found":
        return error("not_found", "active key not found", 404)
    if outcome == "last_admin":
        return error("last_admin", "the last active admin key cannot be revoked", 409)
    audit_event("admin_key_revoked", actor_key_id=g.api_key_id, revoked_key_id=key_id)
    return jsonify(revoked=key_id)


@app.get("/admin/api/uploads")
def admin_uploads():
    page, per_page, offset = pagination()
    with database() as db:
        total = db.execute("SELECT COUNT(*) AS count FROM uploads").fetchone()["count"]
        rows = db.execute(
            "SELECT id,dataset_id,format,version,expected_size,expected_sha256,"
            "metadata,state,actual_size,actual_sha256,created_at FROM uploads "
            "ORDER BY created_at DESC,id LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item["metadata"] = json.loads(item["metadata"])
        items.append(item)
    return jsonify(items=items, total=total, page=page, per_page=per_page)


@app.delete("/admin/api/uploads/<upload_id>")
def admin_delete_upload(upload_id: str):
    with database() as db:
        row = db.execute("SELECT state,staged_path FROM uploads WHERE id=?", (upload_id,)).fetchone()
        if not row:
            return error("not_found", "upload not found", 404)
        if row["state"] == "published":
            return error("immutable_version", "published uploads cannot be deleted", 409)
        staged_path = row["staged_path"]
        db.execute("DELETE FROM uploads WHERE id=?", (upload_id,))
    if staged_path:
        staged_source = Path(staged_path)
        if staged_source.is_symlink():
            audit_event("unsafe_staging_path_ignored", upload_id=upload_id)
            staged_source = None
        staged = staged_source.resolve() if staged_source else None
    else:
        staged = None
    if staged:
        try:
            staged.relative_to((data_root() / "staging").resolve())
        except ValueError:
            audit_event("unsafe_staging_path_ignored", upload_id=upload_id)
        else:
            staged.unlink(missing_ok=True)
    audit_event("admin_upload_deleted", actor_key_id=g.api_key_id, upload_id=upload_id)
    return jsonify(deleted=upload_id)


@app.get("/admin/api/artifacts")
def admin_artifacts():
    page, per_page, offset = pagination()
    with database() as db:
        total = db.execute("SELECT COUNT(*) AS count FROM artifacts").fetchone()["count"]
        rows = db.execute(
            "SELECT * FROM artifacts ORDER BY published_at DESC,dataset_id,format,version "
            "LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
    return jsonify(
        items=[artifact_admin_item(row) for row in rows],
        total=total,
        page=page,
        per_page=per_page,
    )


@app.patch("/admin/api/artifacts/<dataset_id>/<fmt>/<version>")
def admin_update_artifact(dataset_id: str, fmt: str, version: str):
    if validate_identity(dataset_id, fmt, version):
        return error("not_found", "artifact not found", 404)
    body = request.get_json(silent=True) or {}
    try:
        metadata = public_metadata(body.get("metadata"))
    except (TypeError, ValueError) as exc:
        return error("invalid_request", str(exc), 400)
    with database() as db:
        result = db.execute(
            "UPDATE artifacts SET metadata=? WHERE dataset_id=? AND format=? AND version=?",
            (json.dumps(metadata, sort_keys=True), dataset_id, fmt, version),
        )
    if result.rowcount != 1:
        return error("not_found", "artifact not found", 404)
    audit_event(
        "admin_artifact_updated",
        actor_key_id=g.api_key_id,
        dataset_id=dataset_id,
        format=fmt,
        version=version,
    )
    return jsonify(metadata=metadata)


@app.delete("/admin/api/artifacts/<dataset_id>/<fmt>/<version>")
def admin_delete_artifact(dataset_id: str, fmt: str, version: str):
    if validate_identity(dataset_id, fmt, version):
        return error("not_found", "artifact not found", 404)
    body = request.get_json(silent=True) or {}
    delete_file = body.get("delete_file") is True
    with database() as db:
        row = db.execute(
            "SELECT storage_path FROM artifacts WHERE dataset_id=? AND format=? AND version=?",
            (dataset_id, fmt, version),
        ).fetchone()
    if not row:
        return error("not_found", "artifact not found", 404)
    stored_path = Path(row["storage_path"])
    symlink = stored_path.is_symlink()
    path = stored_path.resolve()
    quarantine = None
    if delete_file and path.exists():
        if path.parent != bag_root().resolve() or symlink:
            return error("storage_error", "artifact is outside the flat BAG directory", 409)
        quarantine = path.with_name(f".deleting-{uuid.uuid4().hex}")
        os.replace(path, quarantine)
    try:
        with database() as db:
            result = db.execute(
                "DELETE FROM artifacts WHERE dataset_id=? AND format=? AND version=?",
                (dataset_id, fmt, version),
            )
        if result.rowcount != 1:
            raise RuntimeError("artifact disappeared during deletion")
    except Exception:
        if quarantine and quarantine.exists():
            os.replace(quarantine, path)
        raise
    if quarantine:
        quarantine.unlink(missing_ok=True)
    audit_event(
        "admin_artifact_deleted",
        actor_key_id=g.api_key_id,
        dataset_id=dataset_id,
        format=fmt,
        version=version,
        file_deleted=delete_file,
    )
    return jsonify(deleted={"dataset_id": dataset_id, "format": fmt, "version": version})


@app.get("/admin/api/bags")
def admin_bags():
    root = bag_root()
    root.mkdir(parents=True, exist_ok=True)
    with database() as db:
        registered_rows = db.execute(
            "SELECT dataset_id,format,version,storage_path FROM artifacts"
        ).fetchall()
    registered = {
        str(Path(row["storage_path"]).resolve()): {
            "dataset_id": row["dataset_id"], "format": row["format"], "version": row["version"]
        }
        for row in registered_rows
    }
    items = []
    for path in sorted(root.iterdir(), key=lambda item: item.name.lower()):
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in {".bag", ".zip"}:
            continue
        stat = path.stat()
        items.append({
            "filename": path.name,
            "size": stat.st_size,
            "modified_at": stat.st_mtime,
            "registered": registered.get(str(path.resolve())),
        })
    page, per_page, offset = pagination()
    return jsonify(
        items=items[offset:offset + per_page],
        total=len(items),
        page=page,
        per_page=per_page,
    )


@app.post("/admin/api/bags/migrate")
def admin_migrate_bags():
    root = bag_root().resolve()
    legacy_root = data_root().resolve()
    root.mkdir(parents=True, exist_ok=True)
    with database() as db:
        rows = db.execute(
            "SELECT dataset_id,format,version,size,sha256,storage_path FROM artifacts "
            "ORDER BY dataset_id,format,version"
        ).fetchall()

    migrated = []
    skipped = []
    for row in rows:
        stored = Path(row["storage_path"])
        source = stored.resolve()
        identity = {
            "dataset_id": row["dataset_id"],
            "format": row["format"],
            "version": row["version"],
        }
        if source.parent == root and not stored.is_symlink():
            continue
        try:
            source.relative_to(legacy_root)
        except ValueError:
            skipped.append({**identity, "reason": "source_outside_data_root"})
            continue
        if stored.is_symlink():
            skipped.append({**identity, "reason": "symlink_not_allowed"})
            continue
        if not source.is_file():
            skipped.append({**identity, "reason": "source_missing"})
            continue
        target = artifact_file(row["dataset_id"], row["format"], row["version"])
        try:
            actual_size, actual_sha256 = copy_file_exclusive(source, target)
        except FileExistsError:
            skipped.append({**identity, "reason": "target_exists"})
            continue
        except OSError:
            skipped.append({**identity, "reason": "copy_failed"})
            continue
        if actual_size != row["size"] or actual_sha256 != row["sha256"]:
            target.unlink(missing_ok=True)
            skipped.append({**identity, "reason": "integrity_mismatch"})
            continue
        try:
            with database() as db:
                result = db.execute(
                    "UPDATE artifacts SET storage_path=? "
                    "WHERE dataset_id=? AND format=? AND version=? AND storage_path=?",
                    (
                        str(target), row["dataset_id"], row["format"], row["version"],
                        row["storage_path"],
                    ),
                )
                if result.rowcount != 1:
                    raise RuntimeError("artifact changed during migration")
        except Exception:
            target.unlink(missing_ok=True)
            raise
        warning = None
        try:
            source.unlink()
        except OSError:
            warning = "legacy_source_retained"
        migrated.append({**identity, "filename": target.name, "warning": warning})

    audit_event(
        "admin_bags_migrated",
        actor_key_id=g.api_key_id,
        migrated=len(migrated),
        skipped=len(skipped),
    )
    return jsonify(migrated=migrated, skipped=skipped)


@app.post("/admin/api/bags/register")
def admin_register_bag():
    body = request.get_json(silent=True) or {}
    filename = body.get("filename")
    path = direct_bag_path(filename)
    if not path or not path.is_file():
        return error("not_found", "BAG file not found in the flat storage directory", 404)
    dataset_id, fmt, version = body.get("dataset_id"), body.get("format"), body.get("version")
    problem = validate_identity(dataset_id, fmt, version)
    if problem:
        return error("invalid_request", problem, 400)
    expected_suffix = ".bag" if fmt == "rosbag" else ".zip"
    if path.suffix.lower() != expected_suffix:
        return error("invalid_request", f"{fmt} files must use {expected_suffix}", 400)
    try:
        metadata = public_metadata(body.get("metadata", {}))
    except (TypeError, ValueError) as exc:
        return error("invalid_request", str(exc), 400)
    size, digest = file_digest(path)
    if size > int_setting("IVINS_MAX_UPLOAD_BYTES", 50 * 1024**3):
        return error("payload_too_large", "BAG file exceeds configured limit", 413)
    try:
        with database() as db:
            if db.execute(
                "SELECT 1 FROM artifacts WHERE storage_path=?", (str(path),)
            ).fetchone():
                return error("storage_conflict", "BAG file is already registered", 409)
            db.execute(
                "INSERT INTO artifacts "
                "(dataset_id,format,version,size,sha256,metadata,storage_path) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    dataset_id, fmt, version, size, digest,
                    json.dumps(metadata, sort_keys=True), str(path),
                ),
            )
            db.execute(
                "INSERT OR IGNORE INTO datasets"
                "(id,family,profile,name,description,visible) VALUES(?,?,?,?,?,1)",
                (
                    dataset_id, metadata.get("family", "iVINS"),
                    normalize_profile(metadata.get("profile")),
                    metadata.get("title", dataset_id), metadata.get("description", ""),
                ),
            )
    except sqlite3.IntegrityError:
        return error("immutable_version", "artifact identity already exists", 409)
    audit_event(
        "admin_bag_registered",
        actor_key_id=g.api_key_id,
        filename=filename,
        dataset_id=dataset_id,
        format=fmt,
        version=version,
    )
    return jsonify(
        dataset_id=dataset_id,
        format=fmt,
        version=version,
        filename=filename,
        size=size,
        sha256=digest,
    ), 201


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
