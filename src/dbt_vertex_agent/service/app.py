import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from dbt_vertex_agent.service.handlers import (
    ModelCallback,
    default_model_callback,
    handle_review_upload,
)

JsonObject = dict[str, object]


def handle_health_request() -> tuple[int, JsonObject]:
    return 200, {"status": "ok"}


def handle_review_http_request(
    project_filename: str,
    project_bytes: bytes,
    manifest_filename: str,
    manifest_bytes: bytes,
    model_callback: ModelCallback = default_model_callback,
    debug_enabled: bool = False,
    output_root: Path = Path("runs"),
) -> tuple[int, JsonObject]:
    try:
        result = handle_review_upload(
            project_filename=project_filename,
            project_bytes=project_bytes,
            manifest_filename=manifest_filename,
            manifest_bytes=manifest_bytes,
            model_callback=model_callback,
            debug_enabled=debug_enabled,
            output_root=output_root,
        )
        return 200, result.to_dict()
    except ValueError as exc:
        return 400, {"error": str(exc)}


def parse_multipart_request(body: bytes, content_type: str) -> dict[str, tuple[str, bytes]]:
    marker = "boundary="
    if marker not in content_type:
        raise ValueError("Multipart request missing boundary.")

    boundary = content_type.split(marker, 1)[1].strip()
    boundary_bytes = f"--{boundary}".encode()
    parsed_parts: dict[str, tuple[str, bytes]] = {}

    for raw_part in body.split(boundary_bytes):
        part = raw_part.strip()
        if not part or part == b"--":
            continue

        header_blob, _, content = part.partition(b"\r\n\r\n")
        headers = header_blob.decode("utf-8", errors="ignore").split("\r\n")
        disposition = next(
            (header for header in headers if header.lower().startswith("content-disposition")), ""
        )
        if not disposition:
            continue

        name = ""
        filename = ""
        for token in disposition.split(";"):
            token = token.strip()
            if token.startswith("name="):
                name = token.split("=", 1)[1].strip('"')
            if token.startswith("filename="):
                filename = token.split("=", 1)[1].strip('"')

        if name:
            parsed_parts[name] = (filename, content.rstrip(b"\r\n"))

    return parsed_parts


def create_app(
    host: str,
    port: int,
    model_callback: ModelCallback = default_model_callback,
    debug_enabled: bool = False,
    output_root: Path = Path("runs"),
) -> ThreadingHTTPServer:
    class ServiceHandler(BaseHTTPRequestHandler):
        # Suppress default noisy request logging; the learning docs will show
        # explicit commands instead.
        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def _write_json(self, status_code: int, payload: JsonObject) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                status_code, payload = handle_health_request()
                self._write_json(status_code, payload)
                return

            self._write_json(404, {"error": "Not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/review":
                self._write_json(404, {"error": "Not found"})
                return

            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self._write_json(400, {"error": "Expected multipart/form-data request"})
                return

            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length)
            parts = parse_multipart_request(body, content_type)
            project_file = parts.get("project")
            manifest_file = parts.get("manifest")
            debug_field = parts.get("debug")
            if project_file is None or manifest_file is None:
                self._write_json(400, {"error": "Expected project and manifest file uploads"})
                return

            request_debug_enabled = False
            if debug_field is not None:
                request_debug_enabled = debug_field[1].decode("utf-8").strip().lower() == "true"

            status_code, payload = handle_review_http_request(
                project_filename=project_file[0] or "project.zip",
                project_bytes=project_file[1],
                manifest_filename=manifest_file[0] or "manifest.json",
                manifest_bytes=manifest_file[1],
                model_callback=model_callback,
                debug_enabled=debug_enabled or request_debug_enabled,
                output_root=output_root,
            )
            self._write_json(status_code, payload)

    return ThreadingHTTPServer((host, port), ServiceHandler)
