"""Minimal mock API server for testing mediabackup uploads.

Run in a separate terminal:
    python mock_server.py

Listens on http://localhost:9000 and saves uploaded files to ./mock_uploads/
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler


UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "mock_uploads")


class MockHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        if self.path == "/api/upload":
            self._handle_upload(body)
        elif self.path == "/api/chunk":
            self._handle_chunk(body)
        elif self.path == "/api/manifest":
            self._handle_manifest(body)
        else:
            self._respond(404, {"success": False, "error": "not found"})

    def _handle_upload(self, body):
        # Parse multipart to extract backup_id, backup_name, and file data
        info = self._parse_multipart(body)
        if info is None:
            self._respond(400, {"success": False, "error": "bad request"})
            return

        backup_id = info.get("backup_id", "unknown")
        backup_name = info.get("backup_name", "unknown")
        file_data = info.get("file")

        dest_dir = os.path.join(UPLOAD_DIR, backup_id, "complete")
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, backup_name)
        with open(dest, "wb") as f:
            f.write(file_data)

        print(f"  ✓ upload: {backup_id}/complete/{backup_name} ({len(file_data)} bytes)")
        self._respond(200, {"success": True})

    def _handle_chunk(self, body):
        info = self._parse_multipart(body)
        if info is None:
            self._respond(400, {"success": False, "error": "bad request"})
            return

        backup_id = info.get("backup_id", "unknown")
        backup_name = info.get("backup_name", "unknown")
        chunk_index = info.get("chunk_index", "0")
        chunk_data = info.get("chunk")

        dest_dir = os.path.join(UPLOAD_DIR, backup_id, "chunked", backup_name)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, f"chunk_{int(chunk_index):03d}")
        with open(dest, "wb") as f:
            f.write(chunk_data)

        print(f"  ✓ chunk: {backup_id}/chunked/{backup_name}/chunk_{int(chunk_index):03d} ({len(chunk_data)} bytes)")
        self._respond(200, {"success": True})

    def _handle_manifest(self, body):
        info = self._parse_multipart(body)
        if info is None:
            self._respond(400, {"success": False, "error": "bad request"})
            return

        backup_id = info.get("backup_id", "unknown")
        file_data = info.get("file")

        dest_dir = os.path.join(UPLOAD_DIR, backup_id)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, "manifest.db")
        with open(dest, "wb") as f:
            f.write(file_data)

        print(f"  ✓ manifest: {backup_id}/manifest.db ({len(file_data)} bytes)")
        self._respond(200, {"success": True})

    def _parse_multipart(self, body):
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            return None

        # Extract boundary
        for part in content_type.split(";"):
            part = part.strip()
            if part.startswith("boundary="):
                boundary = part[len("boundary="):].encode()
                break
        else:
            return None

        result = {}
        parts = body.split(b"--" + boundary)
        for part in parts:
            if b"Content-Disposition" not in part:
                continue
            # Split headers from body
            header_end = part.find(b"\r\n\r\n")
            if header_end == -1:
                continue
            headers = part[:header_end].decode(errors="replace")
            data = part[header_end + 4:]
            # Strip trailing \r\n
            if data.endswith(b"\r\n"):
                data = data[:-2]

            # Get field name
            for line in headers.split("\r\n"):
                if "Content-Disposition" in line:
                    for attr in line.split(";"):
                        attr = attr.strip()
                        if attr.startswith('name="'):
                            name = attr[6:].rstrip('"')
                            if 'filename="' in line:
                                result[name] = data
                            else:
                                result[name] = data.decode(errors="replace")
                            break
        return result

    def _respond(self, status, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args):
        # Quieter logging — just method + path
        print(f"← {args[0]}")


if __name__ == "__main__":
    port = 9000
    server = HTTPServer(("localhost", port), MockHandler)
    print(f"Mock API server running on http://localhost:{port}")
    print(f"Uploads will be saved to {UPLOAD_DIR}/")
    print("Press Ctrl+C to stop.\n")
    server.serve_forever()
