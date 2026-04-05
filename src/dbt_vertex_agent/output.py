from dataclasses import dataclass
import json
from pathlib import Path

from dbt_vertex_agent.rendering import render_markdown
from dbt_vertex_agent.review_contract import ReviewResult
from dbt_vertex_agent.service_contract import DebugArtifacts


@dataclass(frozen=True)
class OutputPaths:
    # Returning explicit paths makes the write function easy to test and lets
    # the CLI show users exactly where artifacts landed.
    json_path: Path
    markdown_path: Path


@dataclass(frozen=True)
class DebugOutputPaths:
    # These files capture what the local service actually sent to the model.
    context_path: Path
    prompt_path: Path


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


def write_debug_artifacts(
    run_id: str,
    debug_artifacts: DebugArtifacts,
    output_root: Path,
) -> DebugOutputPaths:
    run_dir = ensure_run_dir(output_root, run_id)

    context_path = run_dir / "context.json"
    prompt_path = run_dir / "prompt.txt"

    context_path.write_text(json.dumps(debug_artifacts.context.to_dict(), indent=2))
    prompt_path.write_text(debug_artifacts.prompt)

    return DebugOutputPaths(context_path=context_path, prompt_path=prompt_path)
