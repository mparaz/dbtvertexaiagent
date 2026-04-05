from dbt_vertex_agent.review_contract import ReviewResult


def render_terminal_summary(result: ReviewResult) -> str:
    # Terminal output is intentionally terse: enough to understand the result
    # without flooding stdout with the full report.
    lines = [
        f"Run: {result.run_id}",
        f"Status: {result.status}",
        result.summary,
    ]

    if result.findings:
        lines.append("Findings:")
        for finding in result.findings:
            lines.append(
                f"- {finding.severity} {finding.rule} {finding.file_path}: {finding.message}"
            )

    if result.reviewed_files:
        lines.append("Reviewed files:")
        for file_path in result.reviewed_files:
            lines.append(f"- {file_path}")

    return "\n".join(lines)


def render_markdown(result: ReviewResult) -> str:
    # Markdown is the richer artifact intended for human review after the run.
    lines = [
        "# dbt Review Report",
        "",
        f"- Run ID: `{result.run_id}`",
        f"- Status: `{result.status}`",
        f"- Summary: {result.summary}",
        "",
        "## Reviewed Files",
    ]

    if result.reviewed_files:
        lines.extend(f"- `{file_path}`" for file_path in result.reviewed_files)
    else:
        lines.append("- None")

    lines.extend(["", "## Findings"])

    if result.findings:
        for finding in result.findings:
            lines.append(
                f"- `{finding.severity}` `{finding.rule}` `{finding.file_path}`: {finding.message}"
            )
    else:
        lines.append("- None")

    return "\n".join(lines)
