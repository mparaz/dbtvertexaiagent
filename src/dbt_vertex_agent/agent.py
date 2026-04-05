import json
import os
from pathlib import Path

from dbt_vertex_agent.manifest_analysis import collect_review_targets
from dbt_vertex_agent.models import SubmissionArtifacts
from dbt_vertex_agent.review_contract import ReviewResult
from dbt_vertex_agent.review_policy import build_review_result
from dbt_vertex_agent.source_reader import (
    filter_existing_archive_members,
    filter_existing_archive_members_from_bytes,
)
from dbt_vertex_agent.storage import download_bytes, download_text


def review_submission(submission: SubmissionArtifacts) -> ReviewResult:
    # The local review runtime supports two storage modes:
    # - local files, which are convenient for tests and local experiments
    # - gs:// URIs, which are what a deployed agent will typically receive
    try:
        if submission.manifest_uri.startswith("gs://"):
            manifest = json.loads(download_text(submission.manifest_uri))
        else:
            manifest = json.loads(Path(submission.manifest_uri).read_text())
    except json.JSONDecodeError:
        return ReviewResult(
            run_id=submission.run_id,
            status="error",
            summary="Manifest could not be parsed.",
            findings=[],
            reviewed_files=[],
        )

    # `collect_review_targets` turns the manifest into the smaller set of file paths
    # we want to inspect or validate against the uploaded archive.
    review_targets = collect_review_targets(manifest)
    # The project bundle can also be local or remote. We only check which of the
    # manifest-derived target files are present in the uploaded archive here.
    if submission.project_uri.startswith("gs://"):
        reviewed_files = filter_existing_archive_members_from_bytes(
            download_bytes(submission.project_uri), review_targets
        )
    else:
        reviewed_files = filter_existing_archive_members(Path(submission.project_uri), review_targets)

    # The policy layer decides how to turn "targets vs files found" into findings
    # and a summary. Keeping that logic outside this function makes the review flow
    # easier to extend later.
    return build_review_result(submission.run_id, review_targets, reviewed_files, manifest=manifest)


def review_dbt_submission(project_uri: str, manifest_uri: str) -> dict:
    # This function is the tool exposed to the ADK agent. The tool layer uses
    # plain strings because LLM tool calls are much simpler when their inputs are
    # basic JSON types.
    result = review_submission(
        SubmissionArtifacts(
            run_id="remote-run",
            project_uri=project_uri,
            manifest_uri=manifest_uri,
        )
    )
    return result.to_dict()


def get_root_agent():
    try:
        from google.adk.agents import Agent
    except ImportError as exc:
        raise RuntimeError("google-adk is required to construct the deployable agent.") from exc

    # The root agent is intentionally thin. Most of the deterministic work lives
    # in regular Python functions; the LLM layer mainly decides when to call the tool
    # and how to return the structured result.
    return Agent(
        name="dbt_review_agent",
        model=os.environ.get("DBT_VERTEX_MODEL", "gemini-2.5-flash-lite"),
        description="Reviews dbt submissions using manifest metadata and uploaded project archives.",
        instruction=(
            "You are a dbt project review agent. "
            "When the user provides project_uri and manifest_uri, call the review_dbt_submission tool. "
            "Return JSON only, matching the tool output."
        ),
        tools=[review_dbt_submission],
    )


try:
    # Import time should not explode on machines that only want to run tests or
    # local code paths. If ADK is missing, we keep `root_agent` as `None` and let
    # deployment code fail with a clear message later.
    root_agent = get_root_agent()
except RuntimeError:
    root_agent = None
