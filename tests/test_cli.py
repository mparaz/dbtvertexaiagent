import os
import unittest
from pathlib import Path
import tempfile

from dbt_vertex_agent.cli import (
    build_review_request,
    build_service_model_callback_from_environment,
    parse_args,
    run_local_service,
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

    def test_parse_args_reads_local_service_base_url(self) -> None:
        args = parse_args(
            [
                "review",
                "--project",
                "sample",
                "--manifest",
                "target/manifest.json",
                "--local-service-url",
                "http://127.0.0.1:8000/",
            ]
        )

        self.assertEqual(args.local_service_url, "http://127.0.0.1:8000/")

    def test_parse_args_supports_debug_flag(self) -> None:
        args = parse_args(
            [
                "review",
                "--project",
                "sample",
                "--manifest",
                "target/manifest.json",
                "--debug",
            ]
        )

        self.assertTrue(args.debug)

    def test_parse_args_supports_serve_command(self) -> None:
        args = parse_args(["serve", "--host", "127.0.0.1", "--port", "9000"])

        self.assertEqual(args.command, "serve")
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 9000)


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
            manifest_path.write_text("{\"nodes\": {}}\n")

            args = parse_args(
                [
                    "review",
                    "--project",
                    str(project_root),
                    "--manifest",
                    str(manifest_path),
                ]
            )
            config = Config(
                project_id="test-project",
                region="us-central1",
                staging_bucket="gs://bucket-name",
                output_dir=str(output_dir),
            )

            def fake_prepare(_request: ReviewRequest) -> SubmissionArtifacts:
                return SubmissionArtifacts(
                    run_id="run-123",
                    project_uri="project.zip",
                    manifest_uri="manifest.json",
                )

            def fake_review(_submission: SubmissionArtifacts) -> ReviewResult:
                return ReviewResult(run_id="run-123", findings=[], reviewed_files=["models/orders.sql"])

            completed = run_review(args, config, prepare=fake_prepare, review=fake_review)

            self.assertEqual(completed.result.run_id, "run-123")
            self.assertTrue(completed.output_paths.json_path.exists())
            self.assertTrue(completed.output_paths.markdown_path.exists())


class RunLocalServiceTests(unittest.TestCase):
    def test_run_local_service_delegates_to_server_factory(self) -> None:
        created = {}

        class FakeServer:
            def serve_forever(self) -> None:
                created["served"] = True

        def fake_factory(host: str, port: int, model_callback, debug_enabled, output_root):
            created["host"] = host
            created["port"] = port
            created["model_callback"] = model_callback
            created["debug_enabled"] = debug_enabled
            created["output_root"] = output_root
            return FakeServer()

        args = parse_args(["serve", "--host", "127.0.0.1", "--port", "9000"])
        run_local_service(args, server_factory=fake_factory)

        self.assertEqual(created["host"], "127.0.0.1")
        self.assertEqual(created["port"], 9000)
        self.assertIsNotNone(created["model_callback"])
        self.assertFalse(created["debug_enabled"])
        self.assertTrue(created["served"])


class BuildServiceModelCallbackFromEnvironmentTests(unittest.TestCase):
    def test_returns_default_callback_when_model_not_configured(self) -> None:
        callback = build_service_model_callback_from_environment(env={})
        self.assertEqual(callback.__name__, "default_model_callback")

    def test_rejects_missing_project_or_region_when_model_is_configured(self) -> None:
        with self.assertRaisesRegex(ValueError, "DBT_VERTEX_PROJECT_ID"):
            build_service_model_callback_from_environment(
                env={"DBT_VERTEX_MODEL": "gemini-2.5-flash"}
            )

    def test_builds_vertex_callback_when_env_is_complete(self) -> None:
        original_builder = build_service_model_callback_from_environment.__globals__["build_vertex_model_callback"]
        created = {}

        def fake_builder(project_id: str, region: str, model_name: str):
            created["project_id"] = project_id
            created["region"] = region
            created["model_name"] = model_name

            def callback(_context):
                return {}

            return callback

        build_service_model_callback_from_environment.__globals__["build_vertex_model_callback"] = fake_builder
        try:
            callback = build_service_model_callback_from_environment(
                env={
                    "DBT_VERTEX_PROJECT_ID": "test-project",
                    "DBT_VERTEX_REGION": "us-central1",
                    "DBT_VERTEX_MODEL": "gemini-2.5-flash",
                }
            )
        finally:
            build_service_model_callback_from_environment.__globals__["build_vertex_model_callback"] = original_builder

        self.assertEqual(created["project_id"], "test-project")
        self.assertEqual(created["region"], "us-central1")
        self.assertEqual(created["model_name"], "gemini-2.5-flash")
        self.assertIsNotNone(callback)
