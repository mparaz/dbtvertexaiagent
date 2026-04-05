import asyncio
import json

from dbt_vertex_agent.models import SubmissionArtifacts
from dbt_vertex_agent.review_contract import Finding, ReviewResult


def get_agent_engines_client():
    try:
        from vertexai import agent_engines
    except ImportError as exc:
        raise RuntimeError(
            "google-cloud-aiplatform with agent engine support is required for remote review."
        ) from exc

    return agent_engines


def extract_final_text(events: list[dict]) -> str:
    # The ADK/Agent Engine event shape can vary a bit between integrations.
    # We normalize that by looking for the most recent text-bearing part.
    for event in reversed(events):
        parts = []
        content = event.get("content")
        if isinstance(content, dict):
            parts.extend(content.get("parts", []))
        parts.extend(event.get("parts", []))

        for part in parts:
            text = part.get("text")
            if text:
                return text

    raise ValueError("No text response found in remote agent events.")


async def _run_remote_review_async(resource_name: str, submission: SubmissionArtifacts, app=None) -> ReviewResult:
    # Tests can pass a fake app directly. Production code resolves the app from
    # the Agent Engine resource name.
    remote_app = app
    if remote_app is None:
        agent_engines = get_agent_engines_client()
        remote_app = agent_engines.get(resource_name)

    # A session is required before the deployed agent can be queried.
    session = await remote_app.async_create_session(user_id="dbt-vertex-agent")
    session_id = session["id"] if isinstance(session, dict) else session.id
    # The remote agent is instructed to return JSON only so we can parse the
    # response directly back into our typed review contract.
    message = (
        "Review this dbt submission and return JSON only. "
        f"project_uri={submission.project_uri} manifest_uri={submission.manifest_uri}"
    )

    events = []
    async for event in remote_app.async_stream_query(
        user_id="dbt-vertex-agent",
        session_id=session_id,
        message=message,
    ):
        events.append(event)

    # Convert the agent's JSON response back into our internal dataclasses.
    payload = json.loads(extract_final_text(events))
    findings = [
        Finding(
            severity=item["severity"],
            rule=item["rule"],
            message=item["message"],
            file_path=item["file_path"],
        )
        for item in payload.get("findings", [])
    ]
    return ReviewResult(
        run_id=payload.get("run_id", submission.run_id),
        status=payload.get("status", "success"),
        summary=payload.get("summary", "No findings detected."),
        findings=findings,
        reviewed_files=payload.get("reviewed_files", []),
    )


def run_remote_review(resource_name: str, submission: SubmissionArtifacts, app=None) -> ReviewResult:
    # Provide a synchronous wrapper because the CLI code is synchronous today.
    return asyncio.run(_run_remote_review_async(resource_name, submission, app=app))
