from dbt_vertex_agent.service.contracts import ReducedReviewContext


def build_reduced_review_context(
    run_id: str,
    reviewed_files: list[str],
    manifest_summary: dict[str, object],
    source_snippets: dict[str, str],
    selected_guidance: list[str] | None = None,
) -> ReducedReviewContext:
    # Keep the model-facing payload compact and explicit.
    return ReducedReviewContext(
        run_id=run_id,
        reviewed_files=reviewed_files,
        manifest_summary=manifest_summary,
        source_snippets=source_snippets,
        selected_guidance=selected_guidance,
    )
