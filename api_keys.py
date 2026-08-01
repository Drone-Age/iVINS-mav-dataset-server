#!/usr/bin/env python3
"""Server-local API key administration for iVINS Dataset Server."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import sys
from contextlib import contextmanager
from pathlib import Path

KEY_RE = re.compile(r"^ivins_([0-9a-f]{16})_([A-Za-z0-9_-]{43})$")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,63}$")


def data_root() -> Path:
    return Path(os.environ.get("IVINS_DATA_ROOT", "var")).resolve()


def database_path() -> Path:
    return Path(os.environ.get("IVINS_DATABASE", data_root() / "catalog.sqlite3")).resolve()


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout=30000")
    db.execute("PRAGMA foreign_keys=ON")
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS api_keys (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          secret_digest TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          revoked_at TEXT
        )
        """
    )
    return db


@contextmanager
def connection():
    db = connect()
    try:
        with db:
            yield db
    finally:
        db.close()


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_api_key(name: str) -> tuple[str, str]:
    """Create a high-entropy key and return (key_id, plaintext_token) once."""
    if not NAME_RE.fullmatch(name):
        raise ValueError("name must be 1-64 safe characters")
    with connection() as db:
        for _ in range(10):
            key_id = secrets.token_hex(8)
            token = f"ivins_{key_id}_{secrets.token_urlsafe(32)}"
            try:
                db.execute(
                    "INSERT INTO api_keys(id,name,secret_digest) VALUES(?,?,?)",
                    (key_id, name, _digest(token)),
                )
            except sqlite3.IntegrityError:
                continue
            return key_id, token
    raise RuntimeError("could not allocate a unique key id")


def list_api_keys() -> list[dict[str, object]]:
    with connection() as db:
        rows = db.execute(
            "SELECT id,name,created_at,revoked_at FROM api_keys ORDER BY created_at,id"
        ).fetchall()
    return [dict(row) for row in rows]


def revoke_api_key(key_id: str) -> bool:
    if not re.fullmatch(r"[0-9a-f]{16}", key_id):
        return False
    with connection() as db:
        result = db.execute(
            "UPDATE api_keys SET revoked_at=CURRENT_TIMESTAMP "
            "WHERE id=? AND revoked_at IS NULL",
            (key_id,),
        )
    return result.rowcount == 1


def active_key_count() -> int:
    with connection() as db:
        row = db.execute(
            "SELECT COUNT(*) AS count FROM api_keys WHERE revoked_at IS NULL"
        ).fetchone()
    return int(row["count"])


def verify_api_key(token: str) -> str | None:
    match = KEY_RE.fullmatch(token)
    if not match:
        return None
    key_id = match.group(1)
    with connection() as db:
        row = db.execute(
            "SELECT secret_digest FROM api_keys WHERE id=? AND revoked_at IS NULL",
            (key_id,),
        ).fetchone()
    candidate = _digest(token)
    expected = row["secret_digest"] if row else "0" * 64
    return key_id if row and hmac.compare_digest(candidate, expected) else None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage Dataset Server API keys locally on the server."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="create and reveal a new key once")
    create.add_argument("--name", required=True, help="administrative key label")
    commands.add_parser("list", help="list key metadata without secrets")
    revoke = commands.add_parser("revoke", help="revoke a key immediately")
    revoke.add_argument("key_id", help="16-character key id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "create":
        try:
            key_id, token = create_api_key(args.name)
        except ValueError as exc:
            print(json.dumps({"error": str(exc)}), file=sys.stderr)
            return 2
        print(json.dumps({
            "key_id": key_id,
            "api_key": token,
            "warning": "The API key is shown once and is not stored in plaintext.",
        }))
        return 0
    if args.command == "list":
        print(json.dumps({"keys": list_api_keys()}))
        return 0
    if args.command == "revoke":
        if not revoke_api_key(args.key_id):
            print(json.dumps({"error": "active key not found"}), file=sys.stderr)
            return 1
        print(json.dumps({"revoked": args.key_id}))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
