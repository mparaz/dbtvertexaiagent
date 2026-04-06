import tempfile
import uuid
import zipfile
from collections.abc import Callable
from pathlib import Path

from dbt_vertex_agent.models import ReviewRequest, SubmissionArtifacts

# A submission uploader takes a local file and a destination object key, then
# returns the final URI of the uploaded object.
Uploader = Callable[[Path, str], str]


def create_project_archive(project_path: Path, archive_path: Path) -> Path:
    if not project_path.exists():
        raise FileNotFoundError(f"Project path does not exist: {project_path}")

    # We archive every file under the project root and preserve relative paths
    # so the uploaded bundle mirrors the original dbt layout.
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(path for path in project_path.rglob("*") if path.is_file()):
            archive.write(file_path, arcname=file_path.relative_to(project_path))

    return archive_path


def prepare_submission(
    request: ReviewRequest, uploader: Uploader, run_id: str | None = None
) -> SubmissionArtifacts:
    # We validate the manifest up front because the manifest is required by the
    # planned hybrid review flow.
    if not request.manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest file: {request.manifest_path}")

    # The caller can pass a run ID during tests for stable assertions.
    # Production code usually lets this default to a random UUID.
    resolved_run_id = run_id or uuid.uuid4().hex

    # The zip file is only an intermediate artifact for upload, so it lives in a
    # temporary directory and disappears after submission completes.
    with tempfile.TemporaryDirectory() as tmp_dir:
        archive_path = Path(tmp_dir) / "project.zip"
        create_project_archive(request.project_path, archive_path)

        # The object layout in GCS is intentionally predictable so later systems
        # can locate all artifacts for one review run under a common prefix.
        project_key = f"submissions/{resolved_run_id}/project.zip"
        manifest_key = f"submissions/{resolved_run_id}/manifest.json"

        project_uri = uploader(archive_path, project_key)
        manifest_uri = uploader(request.manifest_path, manifest_key)

    # The returned object is the handoff from "prepare" into "review".
    return SubmissionArtifacts(
        run_id=resolved_run_id,
        project_uri=project_uri,
        manifest_uri=manifest_uri,
    )
