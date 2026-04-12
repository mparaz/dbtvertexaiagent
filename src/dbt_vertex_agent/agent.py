import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from dbt_vertex_agent.integrations.storage import download_bytes, download_text
from dbt_vertex_agent.review.manifest import normalize_manifest_path

# File suffixes the LLM is allowed to read. Large binary files (CSV seeds, etc.)
# are excluded because they waste context without helping SQL or YAML review.
_REVIEWABLE_SUFFIXES = {".sql", ".yml", ".yaml", ".md"}
_MAX_FILE_CHARS = 4000

# Global review guidance loaded once at import time. Falls back to an empty
# string if the config file is not present (e.g. during unit tests or when
# the package is installed without the repo config directory).
_GUIDANCE_PATH = Path(__file__).parent.parent.parent / "config" / "prompts" / "global" / "base.md"
_GLOBAL_GUIDANCE = _GUIDANCE_PATH.read_text().strip() if _GUIDANCE_PATH.exists() else ""

_GUIDANCE_BLOCK = f"Review guidance:\n{_GLOBAL_GUIDANCE}\n\n" if _GLOBAL_GUIDANCE else ""

_AGENT_INSTRUCTION = f"""You are a dbt project reviewer.

{_GUIDANCE_BLOCK}Review workflow:
1. Call get_manifest_summary with the provided manifest_uri to understand the project \
file structure.
2. Based on the summary, call read_dbt_file for each SQL model file and its corresponding \
schema YAML that are relevant to the review. Focus on models and schema files; skip \
generated test files.
3. Review the retrieved files for dbt correctness and quality: missing model descriptions, \
missing column descriptions, SQL anti-patterns, incorrect ref/source usage, missing tests.
4. Return a JSON object only with this exact structure:
   {{"run_id": "<run_id from message>", "status": "success" or "warning" or "error", \
"summary": "<one sentence>", "findings": [{{"severity": "error"|"warning"|"info", \
"rule": "<rule name>", "message": "<description>", "file_path": "<path from summary>"}}], \
"reviewed_files": ["<path>", ...]}}
Use only file paths that appeared in the manifest summary.
Preserve the run_id exactly as provided in the message.
If no quality issues are found, return an empty findings list."""


def get_manifest_summary(manifest_uri: str) -> dict[str, object]:
    """Return a structured summary of a dbt manifest for LLM-driven file navigation.

    The summary lists every reviewable file path derived from the manifest along
    with lightweight metadata so the LLM can decide which files are worth reading.
    Raw manifest JSON is never returned — that would overwhelm the context budget.
    """
    if manifest_uri.startswith("gs://"):
        manifest = json.loads(download_text(manifest_uri))
    else:
        manifest = json.loads(Path(manifest_uri).read_text())

    # Walk the manifest entries to build a richer file list than collect_review_targets
    # provides on its own. We include node metadata so the LLM can prioritise files
    # without needing to read every one of them first.
    files: list[dict[str, object]] = []
    seen: set[str] = set()

    for section_name in ("nodes", "sources"):
        section = manifest.get(section_name, {})
        if not isinstance(section, dict):
            continue
        for entry in section.values():
            if not isinstance(entry, dict):
                continue
            for key in ("original_file_path", "patch_path"):
                raw_path = entry.get(key)
                if not isinstance(raw_path, str) or not raw_path:
                    continue

                posix_path = normalize_manifest_path(raw_path).as_posix()
                if posix_path in seen:
                    continue
                seen.add(posix_path)

                config = entry.get("config", {})
                materialized = config.get("materialized", "") if isinstance(config, dict) else ""
                tags = entry.get("tags", [])
                has_description = bool(
                    isinstance(entry.get("description"), str) and entry["description"].strip()
                )

                files.append(
                    {
                        "path": posix_path,
                        "node_type": str(entry.get("resource_type", section_name.rstrip("s"))),
                        "materialized": str(materialized),
                        "tags": tags if isinstance(tags, list) else [],
                        "has_description": has_description,
                    }
                )

    return {
        "total_files": len(files),
        "files": files,
    }


def read_dbt_file(project_uri: str, file_path: str) -> str:
    """Read a single file from a dbt project archive and return its content.

    Only SQL, YAML, and Markdown files are supported. Content is truncated to
    4000 characters to keep model context bounded.
    """
    suffix = Path(file_path).suffix.lower()
    if suffix not in _REVIEWABLE_SUFFIXES:
        return f"File type not supported for review: {file_path}"

    try:
        if project_uri.startswith("gs://"):
            zf = zipfile.ZipFile(BytesIO(download_bytes(project_uri)))
        else:
            zf = zipfile.ZipFile(Path(project_uri))

        with zf:
            try:
                content = zf.read(file_path).decode("utf-8", errors="replace")
            except KeyError:
                return f"File not found in project archive: {file_path}"
    except zipfile.BadZipFile:
        return f"Project archive is not a valid ZIP file: {project_uri}"

    if len(content) > _MAX_FILE_CHARS:
        content = f"{content[:_MAX_FILE_CHARS]}\n-- truncated --"

    return content


def extract_text_from_runner_events(events: list[Any]) -> str:
    """Extract the final text response from a sequence of ADK Runner events.

    Local Runner events are typed Python objects (not dicts), so this function
    accesses .content.parts[].text attributes directly. This is the in-process
    equivalent of extract_final_text in integrations/agent_engine.py.
    """
    for event in reversed(events):
        content = getattr(event, "content", None)
        if content is None:
            continue
        parts = getattr(content, "parts", None)
        if not parts:
            continue
        for part in reversed(parts):
            text = getattr(part, "text", None)
            if text:
                return str(text)

    raise ValueError("No text response found in agent events.")


def get_root_agent() -> Any:
    try:
        from google.adk.agents import Agent
    except ImportError as exc:
        raise RuntimeError("google-adk is required to construct the deployable agent.") from exc

    # The root agent is intentionally thin. The LLM drives the review by calling
    # the navigation tools; deterministic logic lives in the tool implementations.
    return Agent(
        name="dbt_review_agent",
        model=__import__("os").environ.get("DBT_VERTEX_MODEL", "gemini-2.5-flash-lite"),
        description=(
            "Reviews dbt submissions using manifest metadata and uploaded project archives."
        ),
        instruction=_AGENT_INSTRUCTION,
        tools=[get_manifest_summary, read_dbt_file],
    )


try:
    # Import time should not explode on machines that only want to run tests or
    # local code paths. If ADK is missing we keep root_agent as None and let
    # deployment code fail with a clear message later.
    root_agent = get_root_agent()
except RuntimeError:
    root_agent = None
