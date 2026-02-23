from pathlib import Path

import requests

from mediabackup.init import BACKUP_DIR_NAME, STATE_DB


def sync_manifest(directory: Path, config: dict) -> bool:
    """Upload state.db to the server. Returns True on success."""
    db_path = directory / BACKUP_DIR_NAME / STATE_DB
    api_endpoint = config["api_endpoint"]
    backup_id = config["backup_id"]

    print("Syncing manifest to server...", end=" ", flush=True)

    try:
        with open(db_path, "rb") as f:
            response = requests.post(
                f"{api_endpoint}/api/manifest",
                data={"backup_id": backup_id},
                files={"file": ("state.db", f)},
            )
    except requests.ConnectionError:
        print("failed (connection error)")
        return False

    if response.ok:
        print("done.")
        return True
    else:
        print(f"failed (status {response.status_code})")
        return False
