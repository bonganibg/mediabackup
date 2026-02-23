import sqlite3
from pathlib import Path

from mediabackup.init import BACKUP_DIR_NAME, STATE_DB


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def get_status(directory: Path) -> dict:
    """Query state.db and return a status summary."""
    db_path = directory / BACKUP_DIR_NAME / STATE_DB
    if not db_path.exists():
        return None

    conn = sqlite3.connect(db_path)

    # Total counts and sizes by file type
    rows = conn.execute(
        "SELECT file_type, COUNT(*), SUM(size) FROM files GROUP BY file_type"
    ).fetchall()
    by_type = {row[0]: {"count": row[1], "size": row[2]} for row in rows}

    # Counts by status
    status_rows = conn.execute(
        "SELECT status, COUNT(*), SUM(size) FROM files GROUP BY status"
    ).fetchall()
    by_status = {row[0]: {"count": row[1], "size": row[2]} for row in status_rows}

    conn.close()

    total_files = sum(v["count"] for v in by_type.values())
    total_size = sum(v["size"] for v in by_type.values())

    return {
        "total_files": total_files,
        "total_size": total_size,
        "by_type": by_type,
        "by_status": by_status,
    }


def print_status(directory: Path, backup_id: str):
    """Print a formatted status summary to the console."""
    info = get_status(directory)

    if info is None:
        print("No backup initialized in this directory.")
        return

    if info["total_files"] == 0:
        print("No files tracked yet. Run 'mediabackup run' to scan.")
        return

    print(f"\nTotal: {info['total_files']} files ({_format_size(info['total_size'])})")
    for ftype in ["image", "video", "audio", "document"]:
        if ftype in info["by_type"]:
            entry = info["by_type"][ftype]
            print(f"  - {entry['count']} {ftype}s ({_format_size(entry['size'])})")

    complete = info["by_status"].get("complete", {"count": 0, "size": 0})
    pending = info["by_status"].get("pending", {"count": 0, "size": 0})
    uploading = info["by_status"].get("uploading", {"count": 0, "size": 0})

    print(f"\nUploaded:  {complete['count']} files ({_format_size(complete['size'])})")
    if uploading["count"]:
        print(f"In progress: {uploading['count']} file")
    print(f"Remaining: {pending['count']} files ({_format_size(pending['size'])})")
