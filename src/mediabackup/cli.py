import argparse
from pathlib import Path

from mediabackup.init import init_backup
from mediabackup.manifest import sync_manifest
from mediabackup.scanner import scan_directory
from mediabackup.status import print_status
from mediabackup.uploader import upload_pending


def cmd_run(args):
    """Initialize (if needed) and start/resume backup."""
    directory = Path(args.directory).resolve()
    config = init_backup(directory)

    print("Media Backup Tool")
    print(f"Backup ID: {config['backup_id']}\n")

    sync_manifest(directory, config)

    print("\nScanning...", end=" ", flush=True)
    result = scan_directory(directory, config["chunk_size"])
    new = result["new"]
    total_new = sum(new.values())
    total_tracked = total_new + result["skipped"]
    print(f"found {total_tracked} files")
    if total_new:
        for ftype in ["image", "video", "audio", "document"]:
            if new.get(ftype):
                print(f"  + {new[ftype]} new {ftype}s")

    print_status(directory, config["backup_id"])

    print()
    upload_pending(directory, config)

    print()
    sync_manifest(directory, config)


def cmd_status(args):
    """Check backup status without uploading."""
    directory = Path(args.directory).resolve()
    config = init_backup(directory)
    print(f"Backup ID: {config['backup_id']}")
    print_status(directory, config["backup_id"])


def cmd_sync(args):
    """Sync manifest to server without uploading."""
    directory = Path(args.directory).resolve()
    config = init_backup(directory)
    print(f"Backup ID: {config['backup_id']}\n")
    sync_manifest(directory, config)


def main():
    parser = argparse.ArgumentParser(
        prog="mediabackup",
        description="Back up media files to a remote API.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, func, help_text in [
        ("run", cmd_run, "Initialize and start/resume backup"),
        ("status", cmd_status, "Check status without uploading"),
        ("sync", cmd_sync, "Sync manifest to server without uploading"),
    ]:
        sp = subparsers.add_parser(name, help=help_text)
        sp.add_argument("directory", help="Path to the media directory")
        sp.set_defaults(func=func)

    args = parser.parse_args()
    args.func(args)
