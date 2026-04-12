import json
from dataclasses import dataclass
from pathlib import Path

from dbt_vertex_agent.rendering import render_markdown
from dbt_vertex_agent.review.contracts import ReviewResult


@dataclass(frozen=True)
class OutputPaths:
    # Returning explicit paths makes the write function easy to test and lets
    # the CLI show users exactly where artifacts landed.
    json_path: Path
    markdown_path: Path


def ensure_run_dir(output_root: Path, run_id: str) -> Path:
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_review_artifacts(result: ReviewResult, output_root: Path) -> OutputPaths:
    # Each run gets its own directory so repeated reviews do not overwrite one another.
    run_dir = ensure_run_dir(output_root, result.run_id)

    json_path = run_dir / "review.json"
    markdown_path = run_dir / "review.md"

    # JSON is the canonical machine-readable artifact.
    json_path.write_text(json.dumps(result.to_dict(), indent=2))
    # Markdown is the human-readable artifact for quick inspection.
    markdown_path.write_text(render_markdown(result))

    return OutputPaths(json_path=json_path, markdown_path=markdown_path)
