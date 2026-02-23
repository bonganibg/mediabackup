import json
import sqlite3
import uuid
from pathlib import Path

BACKUP_DIR_NAME = ".mediabackup"
CONFIG_FILE = "config.json"
STATE_DB = "state.db"

DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024  # 5MB

SCHEMA = """\
CREATE TABLE IF NOT EXISTS files (
    path TEXT PRIMARY KEY,
    backup_name TEXT NOT NULL,
    file_type TEXT NOT NULL,
    size INTEGER NOT NULL,
    status TEXT NOT NULL,
    chunks_total INTEGER,
    chunks_uploaded INTEGER DEFAULT 0,
    discovered_at TEXT NOT NULL,
    uploaded_at TEXT
);

CREATE TABLE IF NOT EXISTS counters (
    file_type TEXT PRIMARY KEY,
    next_number INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def _generate_backup_id():
    short = uuid.uuid4().hex[:8]
    return f"bkp_{short}"


def _create_config(backup_dir: Path, directory: Path, api_endpoint: str = "https://api.yourapp.com"):
    config = {
        "backup_id": _generate_backup_id(),
        "directory_name": directory.name,
        "api_endpoint": api_endpoint,
        "chunk_size": DEFAULT_CHUNK_SIZE,
    }
    config_path = backup_dir / CONFIG_FILE
    config_path.write_text(json.dumps(config, indent=2))
    return config


def _create_db(backup_dir: Path):
    db_path = backup_dir / STATE_DB
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    conn.close()


def init_backup(directory: Path) -> dict:
    """Initialize .mediabackup/ in the given directory. Returns config dict.

    If already initialized, loads and returns the existing config.
    """
    if not directory.is_dir():
        raise SystemExit(f"Error: '{directory}' is not a directory.")

    backup_dir = directory / BACKUP_DIR_NAME
    config_path = backup_dir / CONFIG_FILE

    if config_path.exists():
        config = json.loads(config_path.read_text())
        return config

    backup_dir.mkdir(exist_ok=True)
    config = _create_config(backup_dir, directory)
    _create_db(backup_dir)
    print(f"Initialized new backup in {backup_dir}")
    return config
