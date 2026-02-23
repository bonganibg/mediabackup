import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from mediabackup.init import BACKUP_DIR_NAME, STATE_DB, DEFAULT_CHUNK_SIZE

EXTENSION_TO_TYPE = {}
for _type, _exts in {
    "image": ["jpg", "jpeg", "png", "gif", "webp", "heic", "bmp", "tiff"],
    "video": ["mp4", "mov", "avi", "mkv", "webm", "m4v"],
    "audio": ["mp3", "wav", "flac", "m4a", "aac", "ogg"],
    "document": ["pdf"],
}.items():
    for _ext in _exts:
        EXTENSION_TO_TYPE[f".{_ext}"] = _type

PREFIX_MAP = {
    "image": "IMG",
    "video": "VID",
    "audio": "AUD",
    "document": "DOC",
}


def _get_next_backup_name(conn: sqlite3.Connection, file_type: str, extension: str) -> str:
    """Get the next backup name for a file type and bump the counter."""
    row = conn.execute(
        "SELECT next_number FROM counters WHERE file_type = ?", (file_type,)
    ).fetchone()

    if row is None:
        number = 1
        conn.execute(
            "INSERT INTO counters (file_type, next_number) VALUES (?, 2)", (file_type,)
        )
    else:
        number = row[0]
        conn.execute(
            "UPDATE counters SET next_number = ? WHERE file_type = ?",
            (number + 1, file_type),
        )

    prefix = PREFIX_MAP[file_type]
    return f"{prefix}_{number:06d}{extension}"


def scan_directory(directory: Path, chunk_size: int = DEFAULT_CHUNK_SIZE) -> dict:
    """Scan directory for supported media files and insert new ones into state.db.

    Returns a summary dict with counts.
    """
    db_path = directory / BACKUP_DIR_NAME / STATE_DB
    conn = sqlite3.connect(db_path)
    conn.execute("BEGIN")

    now = datetime.now(timezone.utc).isoformat()
    new_counts = {"image": 0, "video": 0, "audio": 0, "document": 0}
    skipped = 0

    for file_path in sorted(directory.rglob("*")):
        if not file_path.is_file():
            continue

        # Skip anything inside .mediabackup/
        try:
            file_path.relative_to(directory / BACKUP_DIR_NAME)
            continue
        except ValueError:
            pass

        ext = file_path.suffix.lower()
        file_type = EXTENSION_TO_TYPE.get(ext)
        if file_type is None:
            continue

        relative = str(file_path.relative_to(directory))

        # Skip if already tracked
        existing = conn.execute(
            "SELECT 1 FROM files WHERE path = ?", (relative,)
        ).fetchone()
        if existing:
            skipped += 1
            continue

        size = file_path.stat().st_size
        chunks_total = None
        if size >= chunk_size:
            chunks_total = (size + chunk_size - 1) // chunk_size

        backup_name = _get_next_backup_name(conn, file_type, ext)

        conn.execute(
            "INSERT INTO files (path, backup_name, file_type, size, status, chunks_total, discovered_at) "
            "VALUES (?, ?, ?, ?, 'pending', ?, ?)",
            (relative, backup_name, file_type, size, chunks_total, now),
        )
        new_counts[file_type] += 1

    conn.commit()
    conn.close()

    return {"new": new_counts, "skipped": skipped}
