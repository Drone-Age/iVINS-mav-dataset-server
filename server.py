#!/usr/bin/env python3
"""LAN-only HTTP wrapper around the iVINS raw-catalog CLI."""

from __future__ import annotations

import hmac
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import uuid

from flask import Flask, jsonify, request, send_file


REGISTRY_ROOT = Path(os.environ.get("REGISTRY_ROOT", "/registry")).resolve()
RAW_ROOT = Path(os.environ.get("RAW_ROOT", "/data")).resolve()
IMPORT_ROOT = Path(os.environ.get("IMPORT_ROOT", "/imports")).resolve()
CATALOG_SCRIPT = REGISTRY_ROOT / "scripts" / "raw_catalog.py"
FORMATS = {"rosbag", "rosbag2"}

app = Flask(__name__)
jobs: dict[str, dict[str, object]] = {}
jobs_lock = threading.Lock()


def api_key() -> str:
    return os.environ.get("IVINS_API_KEY", "")


@app.before_request
def require_api_key():
    expected = api_key()
    supplied = request.headers.get("X-API-Key", "")
    if not expected:
        return jsonify(error="server API key is not configured"), 503
    if not hmac.compare_digest(supplied, expected):
        return jsonify(error="unauthorized"), 401
    return None


def run_catalog(arguments: list[str]) -> tuple[int, object]:
    command = [
        sys.executable,
        str(CATALOG_SCRIPT),
        "--registry-root",
        str(REGISTRY_ROOT),
        "--raw-root",
        str(RAW_ROOT),
        *arguments,
    ]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=None)
    text = completed.stdout.strip() or completed.stderr.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = {"message": "raw catalog returned non-JSON output"}
    return completed.returncode, payload


def dataset_rows(standard_id: str) -> list[dict[str, object]]:
    code, payload = run_catalog(["status"])
    if code != 0 or not isinstance(payload, list):
        raise RuntimeError("raw catalog status failed")
    return [item for item in payload if item.get("standard_id") == standard_id]


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.get("/v1/datasets/<standard_id>")
def dataset(standard_id: str):
    try:
        rows = dataset_rows(standard_id)
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 502
    if not rows:
        return jsonify(error="unknown standard_id", standard_id=standard_id), 404
    return jsonify(
        standard_id=standard_id,
        dataset=rows[0].get("dataset"),
        formats=[
            {"format": row.get("format"), "registry_status": row.get("registry_status")}
            for row in rows
        ],
    )


@app.get("/v1/datasets/<standard_id>/artifacts")
def artifacts(standard_id: str):
    try:
        rows = dataset_rows(standard_id)
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 502
    if not rows:
        return jsonify(error="unknown standard_id", standard_id=standard_id), 404
    return jsonify(standard_id=standard_id, artifacts=rows)


def perform_fetch(job_id: str, standard_id: str, requested_format: str) -> None:
    with jobs_lock:
        jobs[job_id]["state"] = "running"
    code, payload = run_catalog(["fetch", standard_id, "--format", requested_format])
    with jobs_lock:
        jobs[job_id].update(
            state="completed" if code == 0 else "failed",
            result=payload if code == 0 else None,
            error=payload if code != 0 else None,
        )


def map_import_source(source_path: str) -> Path:
    host_root = os.environ.get("IMPORT_HOST_ROOT", "")
    normalized = source_path.replace("\\", "/")
    normalized_host = host_root.replace("\\", "/").rstrip("/")
    if normalized_host and normalized.casefold().startswith((normalized_host + "/").casefold()):
        relative = normalized[len(normalized_host) + 1:]
        return (IMPORT_ROOT / relative).resolve()
    candidate = Path(source_path).resolve()
    try:
        candidate.relative_to(IMPORT_ROOT)
    except ValueError as exc:
        raise ValueError(
            "source path is not visible in the container; configure IVINS_IMPORT_HOST_ROOT"
        ) from exc
    return candidate


def perform_import(
    job_id: str, standard_id: str, requested_format: str, source_path: Path
) -> None:
    with jobs_lock:
        jobs[job_id]["state"] = "running"
    code, payload = run_catalog(
        ["import-local", standard_id, "--format", requested_format, "--path", str(source_path)]
    )
    with jobs_lock:
        jobs[job_id].update(
            state="completed" if code == 0 else "failed",
            result=payload if code == 0 else None,
            error=payload if code != 0 else None,
        )


@app.post("/v1/datasets/<standard_id>/fetch")
def fetch(standard_id: str):
    body = request.get_json(silent=True) or {}
    requested_format = body.get("format")
    if requested_format not in FORMATS:
        return jsonify(error="format must be rosbag or rosbag2"), 400
    try:
        rows = dataset_rows(standard_id)
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 502
    if not rows:
        return jsonify(error="unknown standard_id", standard_id=standard_id), 404
    selected = next((row for row in rows if row.get("format") == requested_format), None)
    status = selected.get("registry_status") if selected else "not-available"
    if status not in {"verified", "resolvable"}:
        return jsonify(
            error="artifact is not externally downloadable",
            standard_id=standard_id,
            format=requested_format,
            registry_status=status,
        ), 409
    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {
            "job_id": job_id,
            "state": "queued",
            "standard_id": standard_id,
            "format": requested_format,
        }
    threading.Thread(
        target=perform_fetch,
        args=(job_id, standard_id, requested_format),
        daemon=True,
    ).start()
    return jsonify(jobs[job_id]), 202


@app.post("/v1/datasets/<standard_id>/import-local")
def import_local(standard_id: str):
    body = request.get_json(silent=True) or {}
    requested_format = body.get("format")
    source_value = body.get("source_path")
    if requested_format != "rosbag":
        return jsonify(error="local import supports only rosbag"), 400
    if not isinstance(source_value, str) or not source_value:
        return jsonify(error="source_path is required"), 400
    try:
        source_path = map_import_source(source_value)
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    if source_path.suffix.lower() != ".bag" or not source_path.is_file():
        return jsonify(error="source_path must be an existing regular .bag file"), 400
    try:
        rows = dataset_rows(standard_id)
    except RuntimeError as exc:
        return jsonify(error=str(exc)), 502
    if not rows:
        return jsonify(error="unknown standard_id", standard_id=standard_id), 404
    selected = next((row for row in rows if row.get("format") == requested_format), None)
    status = selected.get("registry_status") if selected else "not-available"
    if status != "local-import":
        return jsonify(
            error="artifact is not registered for local import",
            registry_status=status,
        ), 409
    job_id = uuid.uuid4().hex
    with jobs_lock:
        jobs[job_id] = {
            "job_id": job_id,
            "state": "queued",
            "standard_id": standard_id,
            "format": requested_format,
            "operation": "local-import",
        }
    threading.Thread(
        target=perform_import,
        args=(job_id, standard_id, requested_format, source_path),
        daemon=True,
    ).start()
    return jsonify(jobs[job_id]), 202


@app.get("/v1/jobs/<job_id>")
def job(job_id: str):
    with jobs_lock:
        value = jobs.get(job_id)
        if value is None:
            return jsonify(error="unknown job_id"), 404
        return jsonify(value)


@app.get("/v1/datasets/<standard_id>/artifacts/<requested_format>/download")
def download(standard_id: str, requested_format: str):
    if requested_format not in FORMATS:
        return jsonify(error="unknown format"), 404
    code, payload = run_catalog(["resolve", standard_id, "--format", requested_format])
    if code != 0 or not isinstance(payload, dict) or payload.get("local_status") != "available":
        return jsonify(
            error="artifact is not locally available",
            standard_id=standard_id,
            format=requested_format,
            details=payload,
        ), 404
    path = Path(str(payload.get("path"))).resolve()
    try:
        path.relative_to(RAW_ROOT)
    except ValueError:
        return jsonify(error="resolved artifact path escapes raw root"), 500
    if not path.is_file():
        return jsonify(error="resolved artifact file is missing"), 404
    return send_file(path, as_attachment=True, conditional=True)


def main() -> None:
    if not api_key():
        raise SystemExit("IVINS_API_KEY is required")
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, threaded=True)


if __name__ == "__main__":
    main()
