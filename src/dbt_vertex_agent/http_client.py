import json
import uuid
from pathlib import Path
from urllib import request as urllib_request

from dbt_vertex_agent.review_contract import ReviewResult


def normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def build_multipart_body(
    project_path: Path,
    manifest_path: Path,
    boundary: str,
    debug_enabled: bool = False,
) -> bytes:
    parts: list[bytes] = []

    def add_file(field_name: str, file_path: Path, content_type: str) -> None:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{file_path.name}"\r\n'
            ).encode()
        )
        parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
        parts.append(file_path.read_bytes())
        parts.append(b"\r\n")

    def add_field(field_name: str, value: str) -> None:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="{field_name}"\r\n\r\n'.encode()
        )
        parts.append(value.encode())
        parts.append(b"\r\n")

    add_file("project", project_path, "application/zip")
    add_file("manifest", manifest_path, "application/json")
    if debug_enabled:
        add_field("debug", "true")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts)


def default_transport(
    base_url: str,
    project_path: Path,
    manifest_path: Path,
    debug_enabled: bool = False,
) -> dict:
    boundary = f"dbtvertexagent-{uuid.uuid4().hex}"
    body = build_multipart_body(
        project_path,
        manifest_path,
        boundary,
        debug_enabled=debug_enabled,
    )
    request = urllib_request.Request(
        f"{normalize_base_url(base_url)}/review",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib_request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def post_review_to_local_service(
    base_url: str,
    project_path: Path,
    manifest_path: Path,
    debug_enabled: bool = False,
    transport=default_transport,
) -> ReviewResult:
    payload = transport(
        normalize_base_url(base_url),
        project_path,
        manifest_path,
        debug_enabled,
    )
    return ReviewResult.from_model_payload(payload)
