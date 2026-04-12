import argparse
import json
import sys
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dbt_vertex_agent.agent import extract_text_from_runner_events, get_root_agent
from dbt_vertex_agent.config import Config, load_config
from dbt_vertex_agent.integrations.agent_engine import run_remote_review
from dbt_vertex_agent.integrations.storage import upload_file
from dbt_vertex_agent.models import ReviewRequest, SubmissionArtifacts
from dbt_vertex_agent.output import OutputPaths, write_review_artifacts
from dbt_vertex_agent.packaging import create_project_archive, prepare_submission
from dbt_vertex_agent.review.contracts import ReviewResult


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="dbt-vertex-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    review_parser = subparsers.add_parser("review")
    review_parser.add_argument("--project", type=Path, required=True)
    review_parser.add_argument("--manifest", type=Path, required=True)

    return parser.parse_args(list(argv))


def build_review_request(args: argparse.Namespace, config: Config) -> ReviewRequest:
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
    submission: SubmissionArtifacts
    result: ReviewResult
    output_paths: OutputPaths


def run_local_adk_review(submission: SubmissionArtifacts) -> ReviewResult:
    # Import ADK here so the module can be loaded without google-adk installed.
    try:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("google-adk is required for local review runs.") from exc

    agent = get_root_agent()
    if agent is None:
        raise RuntimeError("Root agent could not be constructed. Install google-adk first.")

    session_service = InMemorySessionService()  # type: ignore[no-untyped-call]
    runner = Runner(
        agent=agent,
        app_name="dbt-review",
        session_service=session_service,
        auto_create_session=True,
    )

    # The message tells the agent the run_id plus the two artifact URIs it needs
    # to call its navigation tools. This mirrors the remote Agent Engine contract.
    message = (
        f"Review this dbt submission and return JSON only. "
        f"run_id={submission.run_id} "
        f"project_uri={submission.project_uri} "
        f"manifest_uri={submission.manifest_uri}"
    )
    events: list[Any] = list(
        runner.run(
            user_id="cli",
            session_id=submission.run_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=message)],
            ),
        )
    )

    payload = json.loads(extract_text_from_runner_events(events))
    if not isinstance(payload, dict):
        raise ValueError("Agent response must be a JSON object.")
    return ReviewResult.from_model_payload(payload)


def prepare_local_run(request: ReviewRequest) -> SubmissionArtifacts:
    # For local runs the project archive stays on disk; no GCS upload is needed.
    # The agent tools read local file paths directly.
    run_id = uuid.uuid4().hex
    archive_path = request.output_dir / f"{request.project_path.name}.zip"
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    create_project_archive(request.project_path, archive_path)
    return SubmissionArtifacts(
        run_id=run_id,
        project_uri=str(archive_path),
        manifest_uri=str(request.manifest_path),
    )


def prepare_remote_run(request: ReviewRequest) -> SubmissionArtifacts:
    # For the Agent Engine path the project and manifest must be in GCS so the
    # deployed agent can access them.
    if not request.staging_bucket:
        raise ValueError(
            "DBT_VERTEX_STAGING_BUCKET is required when using a deployed Agent Engine."
        )
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
) -> Callable[[SubmissionArtifacts], ReviewResult]:
    if config.agent_resource_name:
        resource_name = config.agent_resource_name
        return lambda submission: run_remote_review(resource_name, submission)
    return run_local_adk_review


def run_review(
    args: argparse.Namespace,
    config: Config,
    prepare: Callable[[ReviewRequest], SubmissionArtifacts] | None = None,
    review: Callable[[SubmissionArtifacts], ReviewResult] | None = None,
) -> CompletedReview:
    review = review or build_default_review(config)
    request = build_review_request(args, config)

    if prepare is None:
        prepare = prepare_remote_run if config.agent_resource_name else prepare_local_run

    submission = prepare(request)
    result = review(submission)
    output_paths = write_review_artifacts(result, request.output_dir)
    return CompletedReview(submission=submission, result=result, output_paths=output_paths)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    config = load_config()
    completed = run_review(args, config)
    print(completed.output_paths.markdown_path)
    return 0
