from dbt_vertex_agent.prompt_guidance import SelectedGuidance
from dbt_vertex_agent.service_contract import ReducedReviewContext


def build_review_prompt(
    context: ReducedReviewContext,
    guidance: tuple[SelectedGuidance, ...] = (),
) -> str:
    guidance_block = ""
    if guidance:
        rendered_sections = []
        for item in guidance:
            rendered_sections.append(f"## Guidance: {item.label}\n{item.content.strip()}")
        guidance_block = "\n\n".join(rendered_sections) + "\n\n"

    return (
        "You are reviewing a dbt project submission.\n"
        "Return JSON only.\n"
        "Preserve the provided run_id exactly.\n"
        "Use only file paths from reviewed_files when reporting findings.\n"
        "Do not invent files that are not present in the provided context.\n"
        "If no additional semantic findings are present, return an empty findings list.\n\n"
        f"{guidance_block}"
        f"{context.to_json()}"
    )
