import tempfile
import unittest
import zipfile
from pathlib import Path

from dbt_vertex_agent.models import ReviewRequest, SubmissionArtifacts
from dbt_vertex_agent.packaging import create_project_archive, prepare_submission


class CreateProjectArchiveTests(unittest.TestCase):
    def test_create_project_archive_preserves_repo_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir) / "sample"
            (project_root / "models" / "nested").mkdir(parents=True)
            (project_root / "models" / "nested" / "orders.sql").write_text("select 1\n")
            archive_path = Path(tmp_dir) / "project.zip"

            create_project_archive(project_root, archive_path)

            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(archive.namelist(), ["models/nested/orders.sql"])


class PrepareSubmissionTests(unittest.TestCase):
    def test_prepare_submission_returns_uploaded_artifact_uris(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir)
            project_root = temp_path / "sample"
            manifest_path = temp_path / "target" / "manifest.json"
            (project_root / "models").mkdir(parents=True)
            (project_root / "models" / "orders.sql").write_text("select 1\n")
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text('{"nodes": {}}\n')

            request = ReviewRequest(
                project_path=project_root,
                manifest_path=manifest_path,
                project_id="test-project",
                region="us-central1",
                staging_bucket="gs://bucket-name",
                output_dir=Path("runs"),
            )

            uploads = []

            def fake_uploader(source_path: Path, destination: str) -> str:
                uploads.append((source_path.name, destination))
                return f"gs://bucket-name/{destination}"

            submission = prepare_submission(request, fake_uploader, run_id="run-123")

            self.assertEqual(
                submission,
                SubmissionArtifacts(
                    run_id="run-123",
                    project_uri="gs://bucket-name/submissions/run-123/project.zip",
                    manifest_uri="gs://bucket-name/submissions/run-123/manifest.json",
                ),
            )
            self.assertEqual(
                uploads,
                [
                    ("project.zip", "submissions/run-123/project.zip"),
                    ("manifest.json", "submissions/run-123/manifest.json"),
                ],
            )

    def test_prepare_submission_fails_when_manifest_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir)
            project_root = temp_path / "sample"
            (project_root / "models").mkdir(parents=True)
            (project_root / "models" / "orders.sql").write_text("select 1\n")

            request = ReviewRequest(
                project_path=project_root,
                manifest_path=temp_path / "missing" / "manifest.json",
                project_id="test-project",
                region="us-central1",
                staging_bucket="gs://bucket-name",
                output_dir=Path("runs"),
            )

            with self.assertRaisesRegex(FileNotFoundError, "manifest"):
                prepare_submission(request, lambda *_args: "unused")
