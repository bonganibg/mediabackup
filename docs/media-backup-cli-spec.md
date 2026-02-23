# Media Backup CLI Tool Specification

## Overview

A simple CLI tool for backing up media files from a Windows laptop to a remote API. Designed for unreliable networks - uploads smallest files first and tracks progress so interrupted uploads can resume.

## Design Principles

- **Keep it simple** - avoid unnecessary complexity, the code should be straightforward and readable
- **Memory efficient** - stream files, never load entire files into memory
- **Resilient** - any interruption can be recovered from
- **Minimal dependencies** - use Python standard library where possible

## Core Concept

```
Local Directory          CLI Tool              API              S3
─────────────────       ──────────           ─────            ────
/Photos                     │                  │                │
├── vacation/               │                  │                │
│   ├── IMG_001.jpg   ───►  │  ───► POST ───►  │  ───► store ─► │
│   └── video.mp4     ───►  │  ───► chunks ──► │  ───► store ─► │
└── birthday/               │                  │                │
    └── cake.png      ───►  │  ───► POST ───►  │  ───► store ─► │
```

## Local File Structure

When the CLI runs in a directory, it creates:

```
/Photos                      ← user's media directory
├── .mediabackup/            ← created by CLI
│   ├── config.json          ← identity and settings
│   └── state.db             ← SQLite database tracking all files
├── vacation/
│   └── ...
└── ...
```

### config.json

```json
{
  "backup_id": "bkp_a8f2e3b7",
  "directory_name": "Photos",
  "api_endpoint": "https://api.yourapp.com",
  "chunk_size": 5242880
}
```

### state.db Schema

```sql
-- Tracks all media files
CREATE TABLE files (
    path TEXT PRIMARY KEY,           -- "2024/vacation/beach.mp4"
    backup_name TEXT NOT NULL,       -- "VID_000001.mp4"
    file_type TEXT NOT NULL,         -- "image" | "video" | "audio" | "document"
    size INTEGER NOT NULL,           -- bytes
    status TEXT NOT NULL,            -- "pending" | "uploading" | "complete"
    chunks_total INTEGER,            -- NULL if < 5MB, otherwise number of chunks
    chunks_uploaded INTEGER DEFAULT 0,
    discovered_at TEXT NOT NULL,
    uploaded_at TEXT
);

-- Counters for generating backup_name
CREATE TABLE counters (
    file_type TEXT PRIMARY KEY,      -- "image" | "video" | "audio" | "document"
    next_number INTEGER DEFAULT 1
);

-- Metadata
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
```

## Supported File Types

```python
SUPPORTED_EXTENSIONS = {
    # Images
    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.bmp', '.tiff',
    
    # Videos  
    '.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v',
    
    # Audio
    '.mp3', '.wav', '.flac', '.m4a', '.aac', '.ogg',
    
    # Documents
    '.pdf'
}

FILE_TYPE_MAP = {
    'image': ['jpg', 'jpeg', 'png', 'gif', 'webp', 'heic', 'bmp', 'tiff'],
    'video': ['mp4', 'mov', 'avi', 'mkv', 'webm', 'm4v'],
    'audio': ['mp3', 'wav', 'flac', 'm4a', 'aac', 'ogg'],
    'document': ['pdf']
}

PREFIX_MAP = {
    'image': 'IMG',
    'video': 'VID',
    'audio': 'AUD',
    'document': 'DOC'
}
```

## Backup Name Generation

Original file names may have encoding issues. Generate safe names:

```
2024/vacation/café photo (1).jpg  →  IMG_000042.jpg
wedding/ceremony.mp4              →  VID_000001.mp4
music/song.mp3                    →  AUD_000015.mp3
docs/manual.pdf                   →  DOC_000003.pdf
```

The mapping is stored in the database so original paths can be recovered.

## Chunking Rules

- Files **under 5MB**: upload as single request
- Files **5MB or larger**: split into 5MB chunks

Chunking is just reading bytes at offsets - works on any file type:

```python
CHUNK_SIZE = 5 * 1024 * 1024  # 5MB

# To read chunk N:
with open(file_path, 'rb') as f:
    f.seek(N * CHUNK_SIZE)
    chunk_data = f.read(CHUNK_SIZE)
```

## CLI Commands

```bash
# Initialize and start/resume backup
mediabackup run /path/to/photos

# Check status without uploading
mediabackup status /path/to/photos

# Sync manifest to server without uploading
mediabackup sync /path/to/photos
```

## Application Flow

```
START
  │
  ▼
┌─────────────────────────────────┐
│ 1. CHECK FOR .mediabackup/      │
│                                 │
│    If not exists:               │
│      - Create directory         │
│      - Generate backup_id (UUID)│
│      - Create config.json       │
│      - Create state.db          │
│      - Display backup_id        │
└─────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────┐
│ 2. SYNC MANIFEST TO SERVER      │
│                                 │
│    POST /api/manifest           │
│    - backup_id                  │
│    - state.db file              │
└─────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────┐
│ 3. SCAN DIRECTORY               │
│                                 │
│    Walk directory recursively   │
│    For each supported file:     │
│      - Skip if already in DB    │
│      - Generate backup_name     │
│      - Calculate chunks_total   │
│      - INSERT into files table  │
└─────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────┐
│ 4. CHECK FOR INTERRUPTED UPLOAD │
│                                 │
│    SELECT * FROM files          │
│    WHERE status = 'uploading'   │
│                                 │
│    If found: resume this file   │
└─────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────┐
│ 5. UPLOAD LOOP                  │
│                                 │
│    WHILE pending files exist:   │
│                                 │
│      Get smallest pending file: │
│        SELECT * FROM files      │
│        WHERE status = 'pending' │
│        ORDER BY size ASC        │
│        LIMIT 1                  │
│                                 │
│      Set status = 'uploading'   │
│                                 │
│      IF chunks_total IS NULL:   │
│        → Simple upload          │
│      ELSE:                      │
│        → Chunked upload         │
│                                 │
│      Set status = 'complete'    │
│                                 │
└─────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────┐
│ 6. SYNC MANIFEST TO SERVER      │
│                                 │
│    POST /api/manifest           │
│    - backup_id                  │
│    - state.db file              │
└─────────────────────────────────┘
  │
  ▼
DONE
```

## Simple Upload (files < 5MB)

```python
def simple_upload(file_path, backup_name, backup_id):
    with open(file_path, 'rb') as f:
        data = f.read()
    
    response = requests.post(
        f"{API_ENDPOINT}/api/upload",
        json={
            "backup_id": backup_id,
            "backup_name": backup_name
        },
        files={"file": data}
    )
    
    return response.ok
```

## Chunked Upload (files >= 5MB)

```python
def chunked_upload(file_path, backup_name, backup_id, chunks_total, chunks_uploaded):
    with open(file_path, 'rb') as f:
        # Seek to resume position
        f.seek(chunks_uploaded * CHUNK_SIZE)
        
        for chunk_index in range(chunks_uploaded, chunks_total):
            chunk_data = f.read(CHUNK_SIZE)
            
            response = requests.post(
                f"{API_ENDPOINT}/api/chunk",
                json={
                    "backup_id": backup_id,
                    "backup_name": backup_name,
                    "chunk_index": chunk_index,
                    "chunks_total": chunks_total
                },
                files={"chunk": chunk_data}
            )
            
            if response.ok:
                # Update progress immediately after each chunk
                db.execute(
                    "UPDATE files SET chunks_uploaded = ? WHERE path = ?",
                    [chunk_index + 1, relative_path]
                )
            else:
                # Retry logic here
                raise UploadError(f"Chunk {chunk_index} failed")
```

## API Endpoints Required

### POST /api/manifest

Uploads the SQLite database file.

```
Request:
  - backup_id: string
  - file: state.db binary

Response:
  - success: boolean

Server action:
  - Create bucket s3://{backup_id}/ if not exists
  - Store at s3://{backup_id}/manifest.db
```

### POST /api/upload

Uploads a complete file (< 5MB).

```
Request:
  - backup_id: string
  - backup_name: string (e.g., "IMG_000042.jpg")
  - file: binary

Response:
  - success: boolean

Server action:
  - Store at s3://{backup_id}/complete/{backup_name}
```

### POST /api/chunk

Uploads a single chunk of a large file.

```
Request:
  - backup_id: string
  - backup_name: string (e.g., "VID_000001.mp4")
  - chunk_index: integer
  - chunks_total: integer
  - chunk: binary

Response:
  - success: boolean

Server action:
  - Store at s3://{backup_id}/chunked/{backup_name}/chunk_{index:03d}
```

## S3 Storage Structure

Each backup_id is its own bucket:

```
s3://bkp_a8f2e3b7/
├── complete/
│   ├── IMG_000001.jpg
│   ├── IMG_000002.png
│   └── AUD_000001.mp3
│
├── chunked/
│   ├── VID_000001/
│   │   ├── chunk_000
│   │   ├── chunk_001
│   │   ├── chunk_002
│   │   └── chunk_003
│   │
│   └── VID_000002/
│       ├── chunk_000
│       └── ...
│
└── manifest.db
```

## File Retrieval (Server-Side, Future)

To reassemble a chunked file:

1. Query manifest.db for the file's `backup_name` and `chunks_total`
2. If `chunks_total` is NULL: fetch from `complete/`
3. Otherwise: fetch all chunks from `chunked/{backup_name}/` and concatenate
4. Return with original filename from `path` field

## Error Handling

Keep it simple:

- **Network error during chunk upload**: retry a few times with backoff, then exit (user can re-run later)
- **File not found during upload**: mark as failed in DB, continue with next file
- **API returns error**: log it, retry or skip based on error type

The tool should never crash and lose progress. After each successful chunk, progress is saved to the database.

## Memory Constraints

The tool must work on low-spec machines:

- **Never load entire files into memory** - stream in chunks
- **Don't load entire file list into memory** - query DB one file at a time
- **Peak memory should stay under 50MB** regardless of file sizes

## Progress Display

Simple console output:

```
Media Backup Tool
Backup ID: bkp_a8f2e3b7

Scanning... found 1,234 files (8.2 GB)
  - 892 images
  - 45 videos  
  - 290 audio files
  - 7 documents

Already uploaded: 400
Remaining: 834 files (6.1 GB)

Uploading (smallest first)...
[1/834] IMG_000401.jpg (156 KB) ✓
[2/834] IMG_000402.png (203 KB) ✓
[3/834] AUD_000089.mp3 (3.2 MB) ✓
[4/834] VID_000023.mp4 (1.2 GB) chunk 12/240...
```

## Implementation Notes

1. Use `pathlib` for cross-platform path handling
2. Use `sqlite3` from standard library (no external dependency)
3. Use `requests` for HTTP (single external dependency)
4. Generate backup_id using `uuid.uuid4()` with a `bkp_` prefix
5. Store all timestamps as ISO 8601 strings
6. Use zero-padded numbers for backup names: `IMG_000001` not `IMG_1`
7. Chunk index also zero-padded: `chunk_000`, `chunk_001`, etc.
