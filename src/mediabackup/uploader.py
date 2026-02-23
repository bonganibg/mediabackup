import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from mediabackup.init import BACKUP_DIR_NAME, STATE_DB

MAX_RETRIES = 3
RETRY_DELAYS = [2, 5, 10]  # seconds


def _get_db(directory: Path) -> sqlite3.Connection:
    return sqlite3.connect(directory / BACKUP_DIR_NAME / STATE_DB)


def _set_status(conn: sqlite3.Connection, path: str, status: str):
    uploaded_at = None
    if status == "complete":
        uploaded_at = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE files SET status = ?, uploaded_at = COALESCE(?, uploaded_at) WHERE path = ?",
        (status, uploaded_at, path),
    )
    conn.commit()


def _post_with_retry(url, data, files):
    """POST with retry and backoff. Returns response or raises ConnectionError."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = requests.post(url, data=data, files=files)
            if response.ok:
                return response
            # Server error (5xx) — worth retrying
            if response.status_code >= 500 and attempt < MAX_RETRIES:
                delay = RETRY_DELAYS[attempt]
                print(f" (server error {response.status_code}, retrying in {delay}s...)", end="", flush=True)
                time.sleep(delay)
                continue
            return response
        except requests.ConnectionError:
            if attempt < MAX_RETRIES:
                delay = RETRY_DELAYS[attempt]
                print(f" (connection error, retrying in {delay}s...)", end="", flush=True)
                time.sleep(delay)
                continue
            raise
    return response


def simple_upload(file_path: Path, backup_name: str, backup_id: str, api_endpoint: str) -> bool:
    """Upload a file < 5MB as a single request. Returns True on success."""
    with open(file_path, "rb") as f:
        response = _post_with_retry(
            f"{api_endpoint}/api/upload",
            data={"backup_id": backup_id, "backup_name": backup_name},
            files={"file": (backup_name, f)},
        )
    return response.ok


def chunked_upload(
    file_path: Path,
    backup_name: str,
    backup_id: str,
    api_endpoint: str,
    chunks_total: int,
    chunks_uploaded: int,
    chunk_size: int,
    conn: sqlite3.Connection,
    rel_path: str,
    progress_prefix: str,
) -> bool:
    """Upload a file >= 5MB in chunks. Returns True on success."""
    with open(file_path, "rb") as f:
        f.seek(chunks_uploaded * chunk_size)

        for chunk_index in range(chunks_uploaded, chunks_total):
            chunk_data = f.read(chunk_size)
            print(f"\r{progress_prefix} chunk {chunk_index + 1}/{chunks_total}...", end="", flush=True)

            response = _post_with_retry(
                f"{api_endpoint}/api/chunk",
                data={
                    "backup_id": backup_id,
                    "backup_name": backup_name,
                    "chunk_index": chunk_index,
                    "chunks_total": chunks_total,
                },
                files={"chunk": (f"chunk_{chunk_index:03d}", chunk_data)},
            )

            if not response.ok:
                print(f"\r{progress_prefix} chunk {chunk_index + 1}/{chunks_total} - failed")
                return False

            conn.execute(
                "UPDATE files SET chunks_uploaded = ? WHERE path = ?",
                (chunk_index + 1, rel_path),
            )
            conn.commit()

    print(f"\r{progress_prefix} {chunks_total}/{chunks_total} chunks ✓")
    return True


def upload_pending(directory: Path, config: dict):
    """Upload all pending files, smallest first."""
    api_endpoint = config["api_endpoint"]
    backup_id = config["backup_id"]
    conn = _get_db(directory)

    # Count remaining for progress display
    total_remaining = conn.execute(
        "SELECT COUNT(*) FROM files WHERE status IN ('pending', 'uploading')"
    ).fetchone()[0]

    if total_remaining == 0:
        print("All files already uploaded.")
        conn.close()
        return

    print(f"Uploading (smallest first)...")
    uploaded = 0

    chunk_size = config.get("chunk_size", 5 * 1024 * 1024)

    # Resume any interrupted upload first
    interrupted = conn.execute(
        "SELECT path, backup_name, size, chunks_total, chunks_uploaded FROM files "
        "WHERE status = 'uploading' LIMIT 1"
    ).fetchone()

    while True:
        if interrupted is not None:
            row = interrupted
            interrupted = None
        else:
            row = conn.execute(
                "SELECT path, backup_name, size, chunks_total, chunks_uploaded FROM files "
                "WHERE status = 'pending' ORDER BY size ASC LIMIT 1"
            ).fetchone()

        if row is None:
            break

        rel_path, backup_name, size, chunks_total, chunks_uploaded = row
        file_path = directory / rel_path
        uploaded += 1
        prefix = f"[{uploaded}/{total_remaining}] {backup_name} ({_fmt_size(size)})"

        if not file_path.exists():
            print(f"{prefix} - file not found, skipping")
            _set_status(conn, rel_path, "failed")
            continue

        _set_status(conn, rel_path, "uploading")

        try:
            if chunks_total is not None:
                ok = chunked_upload(
                    file_path, backup_name, backup_id, api_endpoint,
                    chunks_total, chunks_uploaded, chunk_size,
                    conn, rel_path, prefix,
                )
            else:
                ok = simple_upload(file_path, backup_name, backup_id, api_endpoint)
        except requests.ConnectionError:
            print(f"\n{prefix} - connection lost, exiting (re-run to resume)")
            conn.close()
            return

        if ok:
            _set_status(conn, rel_path, "complete")
            if chunks_total is None:
                print(f"{prefix} ✓")
        else:
            print(f"{prefix} - upload failed")
            _set_status(conn, rel_path, "pending")

    conn.close()
    print("Done.")


def _fmt_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
