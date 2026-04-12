import tempfile
import unittest
from pathlib import Path

from dbt_vertex_agent.cli import (
    build_review_request,
    parse_args,
    prepare_local_run,
    run_review,
)
from dbt_vertex_agent.config import Config
from dbt_vertex_agent.models import ReviewRequest, SubmissionArtifacts
from dbt_vertex_agent.review_contract import ReviewResult


class ParseArgsTests(unittest.TestCase):
    def test_parse_args_reads_project_and_manifest_paths(self) -> None:
        args = parse_args(["review", "--project", "sample", "--manifest", "target/manifest.json"])

        self.assertEqual(args.command, "review")
        self.assertEqual(args.project, Path("sample"))
        self.assertEqual(args.manifest, Path("target/manifest.json"))

    def test_parse_args_rejects_serve_command(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["serve"])

    def test_parse_args_rejects_unknown_flags(self) -> None:
        with self.assertRaises(SystemExit):
            parse_args(["review", "--project", "sample", "--manifest", "manifest.json", "--debug"])


class BuildReviewRequestTests(unittest.TestCase):
    def test_build_review_request_combines_cli_args_and_config(self) -> None:
        args = parse_args(["review", "--project", "sample", "--manifest", "target/manifest.json"])
        config = Config(
            project_id="test-project",
            region="us-central1",
            staging_bucket="gs://bucket-name",
            output_dir="runs",
        )

        request = build_review_request(args, config)

        self.assertEqual(
            request,
            ReviewRequest(
                project_path=Path("sample"),
                manifest_path=Path("target/manifest.json"),
                project_id="test-project",
                region="us-central1",
                staging_bucket="gs://bucket-name",
                output_dir=Path("runs"),
            ),
        )


class PrepareLocalRunTests(unittest.TestCase):
    def test_prepare_local_run_creates_zip_and_returns_local_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir)
            project_root = temp_path / "my_project"
            manifest_path = temp_path / "manifest.json"
            output_dir = temp_path / "runs"

            (project_root / "models").mkdir(parents=True)
            (project_root / "models" / "orders.sql").write_text("select 1\n")
            manifest_path.write_text('{"nodes": {}}\n')

            request = ReviewRequest(
                project_path=project_root,
                manifest_path=manifest_path,
                project_id="",
                region="",
                staging_bucket="",
                output_dir=output_dir,
            )

            submission = prepare_local_run(request)

            self.assertTrue(Path(submission.project_uri).exists())
            self.assertTrue(Path(submission.manifest_uri).exists())
            self.assertFalse(submission.project_uri.startswith("gs://"))
            self.assertFalse(submission.manifest_uri.startswith("gs://"))
            self.assertTrue(submission.project_uri.endswith(".zip"))


class RunReviewTests(unittest.TestCase):
    def test_run_review_writes_review_artifacts_for_submission_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_path = Path(tmp_dir)
            project_root = temp_path / "sample"
            manifest_path = temp_path / "target" / "manifest.json"
            output_dir = temp_path / "outputs"
            (project_root / "models").mkdir(parents=True)
            (project_root / "models" / "orders.sql").write_text("select 1\n")
            manifest_path.parent.mkdir(parents=True)
            manifest_path.write_text('{"nodes": {}}\n')

            args = parse_args(
                [
                    "review",
                    "--project",
                    str(project_root),
                    "--manifest",
                    str(manifest_path),
                ]
            )
            config = Config(output_dir=str(output_dir))

            def fake_prepare(_request: ReviewRequest) -> SubmissionArtifacts:
                return SubmissionArtifacts(
                    run_id="run-123",
                    project_uri="project.zip",
                    manifest_uri="manifest.json",
                )

            def fake_review(_submission: SubmissionArtifacts) -> ReviewResult:
                return ReviewResult(
                    run_id="run-123",
                    findings=[],
                    reviewed_files=["models/orders.sql"],
                )

            completed = run_review(args, config, prepare=fake_prepare, review=fake_review)

            self.assertEqual(completed.result.run_id, "run-123")
            self.assertTrue(completed.output_paths.json_path.exists())
            self.assertTrue(completed.output_paths.markdown_path.exists())
