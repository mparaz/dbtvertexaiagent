import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import tempfile
import sys
from typing import Callable, Sequence

from dbt_vertex_agent.agent import review_submission
from dbt_vertex_agent.config import Config, load_config
from dbt_vertex_agent.http_client import post_review_to_local_service
from dbt_vertex_agent.models import ReviewRequest, SubmissionArtifacts
from dbt_vertex_agent.output import OutputPaths, write_review_artifacts
from dbt_vertex_agent.packaging import create_project_archive, prepare_submission
from dbt_vertex_agent.model_client import build_vertex_model_callback
from dbt_vertex_agent.remote import run_remote_review
from dbt_vertex_agent.review_contract import ReviewResult
from dbt_vertex_agent.service import create_app
from dbt_vertex_agent.service_handlers import default_model_callback
from dbt_vertex_agent.storage import upload_file


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    # The CLI starts small on purpose: one subcommand for the end-to-end review flow.
    # This keeps the learning surface compact while the project is still evolving.
    parser = argparse.ArgumentParser(prog="dbt-vertex-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # A "review" run always needs two local inputs:
    # 1. the dbt project root that will be zipped and uploaded
    # 2. the manifest that will act as the structured analysis harness
    review_parser = subparsers.add_parser("review")
    review_parser.add_argument("--project", type=Path, required=True)
    review_parser.add_argument("--manifest", type=Path, required=True)
    review_parser.add_argument("--local-service-url")
    review_parser.add_argument("--debug", action="store_true")

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)

    return parser.parse_args(list(argv))


def build_review_request(args: argparse.Namespace, config: Config) -> ReviewRequest:
    # Convert CLI args + environment config into one immutable object.
    # This gives the rest of the system a stable contract instead of passing
    # around raw argparse namespaces and environment variables.
    return ReviewRequest(
        project_path=args.project,
        manifest_path=args.manifest,
        project_id=config.project_id,
        region=config.region,
        staging_bucket=config.staging_bucket,
        output_dir=Path(config.output_dir),
    )


@dataclass(frozen=True)
class CompletedReview:
    # `submission` tells us what was uploaded and under which run ID.
    # `result` is the structured review returned by the local or remote agent.
    # `output_paths` tells us where the human-readable and machine-readable
    # artifacts were written on disk.
    submission: SubmissionArtifacts
    result: ReviewResult
    output_paths: OutputPaths


def run_review(
    args: argparse.Namespace,
    config: Config,
    prepare: Callable[[ReviewRequest], SubmissionArtifacts] | None = None,
    review: Callable[[SubmissionArtifacts], ReviewResult] | None = None,
) -> CompletedReview:
    # These hooks make the orchestration function easy to test:
    # tests can inject fake upload and review functions instead of depending on
    # real Google Cloud services.
    prepare = prepare or default_prepare
    review = review or build_default_review(config, debug_enabled=args.debug)
    # Step 1: normalize inputs.
    request = build_review_request(args, config)
    # Step 2: package + upload the source artifacts.
    submission = prepare(request)
    # Step 3: run the actual review, either locally or against a deployed agent.
    result = review(submission)
    # Step 4: save artifacts locally so a developer can inspect the run later.
    output_paths = write_review_artifacts(result, request.output_dir)
    return CompletedReview(submission=submission, result=result, output_paths=output_paths)


def default_prepare(request: ReviewRequest) -> SubmissionArtifacts:
    # `prepare_submission` knows how to build the archive layout and object keys.
    # The CLI provides the concrete uploader function that talks to GCS.
    return prepare_submission(
        request,
        uploader=lambda source_path, destination: upload_file(
            request.staging_bucket,
            source_path,
            destination,
        ),
    )


def build_default_review(
    config: Config,
    debug_enabled: bool = False,
) -> Callable[[SubmissionArtifacts], ReviewResult]:
    if config.local_service_url:
        def review_via_local_service(submission: SubmissionArtifacts) -> ReviewResult:
            return post_review_to_local_service(
                config.local_service_url,
                Path(submission.project_uri),
                Path(submission.manifest_uri),
                debug_enabled=debug_enabled,
            )

        return review_via_local_service

    # If the user configured a deployed Agent Engine resource, prefer the remote path.
    # Otherwise we fall back to the local review function, which is useful for tests
    # and for understanding the review flow without deploying first.
    if config.agent_resource_name:
        return lambda submission: run_remote_review(config.agent_resource_name, submission)

    return review_submission


def prepare_local_service_submission(request: ReviewRequest) -> SubmissionArtifacts:
    with tempfile.TemporaryDirectory() as tmp_dir:
        archive_path = Path(tmp_dir) / "project.zip"
        create_project_archive(request.project_path, archive_path)
        persisted_archive_path = request.output_dir / f"{request.project_path.name}.zip"
        persisted_archive_path.parent.mkdir(parents=True, exist_ok=True)
        persisted_archive_path.write_bytes(archive_path.read_bytes())

    return SubmissionArtifacts(
        run_id="local-service-run",
        project_uri=str(persisted_archive_path),
        manifest_uri=str(request.manifest_path),
    )


def build_service_model_callback_from_environment(
    env: dict[str, str] | None = None,
):
    env = env or os.environ
    model_name = env.get("DBT_VERTEX_MODEL")
    if not model_name:
        return default_model_callback

    project_id = env.get("DBT_VERTEX_PROJECT_ID")
    region = env.get("DBT_VERTEX_REGION")
    if not project_id or not region:
        raise ValueError(
            "DBT_VERTEX_PROJECT_ID and DBT_VERTEX_REGION are required when DBT_VERTEX_MODEL is set."
        )

    return build_vertex_model_callback(
        project_id=project_id,
        region=region,
        model_name=model_name,
    )


def run_local_service(args: argparse.Namespace, server_factory=create_app) -> None:
    model_callback = build_service_model_callback_from_environment()
    service_debug_enabled = os.environ.get("DBT_VERTEX_DEBUG", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    output_root = Path(os.environ.get("DBT_VERTEX_OUTPUT_DIR", "runs"))
    server = server_factory(
        args.host,
        args.port,
        model_callback=model_callback,
        debug_enabled=service_debug_enabled,
        output_root=output_root,
    )
    server.serve_forever()


def main(argv: Sequence[str] | None = None) -> int:
    # Entry point used by both `python -m dbt_vertex_agent` and the console script.
    args = parse_args(argv if argv is not None else sys.argv[1:])
    if args.command == "serve":
        run_local_service(args)
        return 0

    config = load_config()
    prepare = default_prepare
    if args.local_service_url or config.local_service_url:
        config = Config(
            project_id=config.project_id,
            region=config.region,
            staging_bucket=config.staging_bucket,
            output_dir=config.output_dir,
            agent_resource_name=config.agent_resource_name,
            local_service_url=args.local_service_url or config.local_service_url,
        )
        prepare = prepare_local_service_submission

    completed = run_review(args, config, prepare=prepare)
    # For now the CLI prints the markdown artifact path. That keeps stdout simple
    # while still giving the developer a concrete file to open next.
    print(completed.output_paths.markdown_path)
    return 0
