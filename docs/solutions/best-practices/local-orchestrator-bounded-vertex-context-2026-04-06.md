---
title: Keep dbt review orchestration local and send only bounded source context to Vertex
date: 2026-04-06
category: best-practices
module: dbt_vertex_agent
problem_type: best_practice
component: tooling
severity: medium
applies_when:
  - Building a local HTTP orchestrator that should keep compute on the developer machine
  - Reviewing dbt projects with a remote Gemini model on Vertex AI
  - Reducing prompt size while still giving the model enough source context to review SQL and YAML
tags: [dbt, vertex-ai, gemini, local-orchestrator, prompt-context, tooling]
related_components: [documentation, development_workflow]
---

# Keep dbt review orchestration local and send only bounded source context to Vertex

## Context
This project needed a mode where the review service runs locally, the CLI uploads artifacts to a local HTTP endpoint, and only model inference leaves the machine. The initial LLM wiring proved the transport path, but it sent almost no useful context to Gemini: only a run ID, reviewed file names, and a small manifest summary.

That meant the model could return structured JSON, but it could not inspect the contents of dbt models or schema YAML files. The prompt path was technically live but not yet capable of meaningful code review.

## Guidance
Keep the local service responsible for artifact inspection and context reduction, then send a bounded, structured prompt to Vertex.

In this repo, the pattern is:

1. The local HTTP service accepts `project.zip` and `manifest.json`.
2. The service derives review targets from the manifest locally.
3. The service filters those targets against the uploaded archive locally.
4. The service extracts only human-reviewable source text from the archive.
5. The service sends a compact JSON context plus explicit instructions to Gemini.
6. The model returns structured JSON matching the shared review contract.

The important boundary is that Gemini should not receive the whole archive or raw manifest. The local service should decide what is relevant first.

Current implementation highlights:

```python
context = build_reduced_review_context(
    run_id=local_result.run_id,
    reviewed_files=reviewed_files,
    manifest_summary={
        "target_count": len(review_targets),
        "reviewed_file_count": len(reviewed_files),
    },
    source_snippets=extract_source_snippets_from_bytes(project_bytes, review_targets),
)
payload = model_callback(context)
```

The source extraction path is intentionally selective:

```python
REVIEWABLE_SOURCE_SUFFIXES = {".sql", ".yml", ".yaml", ".md"}

def extract_source_snippets_from_bytes(
    project_archive_bytes: bytes,
    targets: list[Path],
    max_chars_per_file: int = 4000,
) -> dict[str, str]:
    target_names = {
        target.as_posix()
        for target in targets
        if target.suffix.lower() in REVIEWABLE_SOURCE_SUFFIXES
    }
```

The direct Vertex callback should remain thin and schema-constrained:

```python
response = client.models.generate_content(
    model=model_name,
    contents=build_review_prompt(context),
    config={
        "response_mime_type": "application/json",
        "response_schema": build_review_response_schema(),
    },
)
```

This keeps the cloud side focused on semantic review, not file discovery or archive parsing.

## Why This Matters
This pattern preserves the architecture the user wanted:

- local compute stays local
- the local service remains the orchestration boundary
- only reduced model context leaves the machine
- the remote model gets enough text to review dbt SQL and YAML meaningfully

Without snippet extraction, the model path is misleading: it appears integrated, but it can only reason over filenames and counts. Without bounded extraction, the opposite failure appears: the service can flood the prompt with unnecessary data, especially from seeds or oversized files.

The bounded-snippet approach avoids both problems:

- enough context for useful semantic findings
- controlled prompt size
- deterministic preprocessing that is easy to test without a live model call

## When to Apply
- When a local service should mirror a future hosted architecture without moving orchestration to the cloud yet
- When uploaded artifacts are larger than what should be passed directly to the model
- When manifest metadata is useful for target selection but insufficient for semantic review on its own
- When you want a stable review contract that works for deterministic rules and LLM-backed review

## Examples
Before:

```python
context = build_reduced_review_context(
    run_id=local_result.run_id,
    reviewed_files=reviewed_files,
    manifest_summary={"target_count": len(review_targets)},
    source_snippets={},
)
```

This lets Gemini see only filenames and counts, not dbt model contents.

After:

```python
context = build_reduced_review_context(
    run_id=local_result.run_id,
    reviewed_files=reviewed_files,
    manifest_summary={
        "target_count": len(review_targets),
        "reviewed_file_count": len(reviewed_files),
    },
    source_snippets=extract_source_snippets_from_bytes(project_bytes, review_targets),
)
```

This gives Gemini the actual SQL and YAML text for the selected review targets while still excluding irrelevant or bulky archive members such as CSV seeds.

## Related
- [Teaching Comments And Thin Agent Boundaries](/Users/mparaz/projects/gcp/dbtvertexaiagent/docs/solutions/best-practices/teaching-comments-and-thin-agent-boundaries-2026-04-05.md)
- [Local Orchestrator Mode](/Users/mparaz/projects/gcp/dbtvertexaiagent/docs/local-orchestrator-mode.md)
