import json
import uuid
import zipfile
from pathlib import Path

from dbt_vertex_agent.context_builder import build_reduced_review_context
from dbt_vertex_agent.manifest_analysis import collect_review_targets
from dbt_vertex_agent.output import write_debug_artifacts
from dbt_vertex_agent.prompt_guidance import (
    build_selected_guidance,
    load_prompt_guidance_config,
)
from dbt_vertex_agent.prompting import build_review_prompt
from dbt_vertex_agent.review_contract import ReviewResult
from dbt_vertex_agent.review_policy import build_review_result
from dbt_vertex_agent.service_contract import DebugArtifacts, ReducedReviewContext
from dbt_vertex_agent.source_reader import (
    extract_source_snippets_from_bytes,
    filter_existing_archive_members_from_bytes,
    list_archive_members_from_bytes,
)


def default_model_callback(_context: ReducedReviewContext) -> dict:
    # Returning an empty payload means "use the deterministic local result".
    return {}


def handle_review_upload(
    project_filename: str,
    project_bytes: bytes,
    manifest_filename: str,
    manifest_bytes: bytes,
    model_callback=default_model_callback,
    debug_enabled: bool = False,
    output_root: Path = Path("runs"),
) -> ReviewResult:
    # Basic filename checks make the service contract easier to understand and debug.
    if not project_filename.endswith(".zip"):
        raise ValueError("Project upload must be a ZIP file.")
    if not manifest_filename.endswith(".json"):
        raise ValueError("Manifest upload must be a JSON file.")

    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Manifest upload must contain valid JSON.") from exc

    try:
        list_archive_members_from_bytes(project_bytes)
    except zipfile.BadZipFile as exc:
        raise ValueError("Project upload must be a valid ZIP file.") from exc

    review_targets = collect_review_targets(manifest)
    reviewed_files = filter_existing_archive_members_from_bytes(project_bytes, review_targets)
    local_result = build_review_result(
        uuid.uuid4().hex,
        review_targets,
        reviewed_files,
        manifest=manifest,
    )

    context = build_reduced_review_context(
        run_id=local_result.run_id,
        reviewed_files=reviewed_files,
        manifest_summary={
            "target_count": len(review_targets),
            "reviewed_file_count": len(reviewed_files),
        },
        source_snippets=extract_source_snippets_from_bytes(project_bytes, review_targets),
        selected_guidance=[],
    )
    prompt_guidance_config = load_prompt_guidance_config(Path("config/prompts"))
    selected_guidance = build_selected_guidance(
        config=prompt_guidance_config,
        reviewed_files=reviewed_files,
    )
    context = build_reduced_review_context(
        run_id=context.run_id,
        reviewed_files=context.reviewed_files,
        manifest_summary=context.manifest_summary,
        source_snippets=context.source_snippets,
        selected_guidance=[item.label for item in selected_guidance],
    )
    prompt = build_review_prompt(context, guidance=selected_guidance)
    if debug_enabled:
        write_debug_artifacts(
            run_id=local_result.run_id,
            debug_artifacts=DebugArtifacts(context=context, prompt=prompt),
            output_root=output_root,
        )
    payload = model_callback(context)
    if payload:
        return ReviewResult.from_model_payload(payload)

    return local_result
