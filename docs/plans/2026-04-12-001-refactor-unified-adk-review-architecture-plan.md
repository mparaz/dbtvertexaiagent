---
title: "refactor: unify review paths under ADK Runner with multi-tool navigation"
type: refactor
status: active
date: 2026-04-12
origin: docs/brainstorms/2026-04-12-unified-adk-review-architecture-requirements.md
---

# refactor: unify review paths under ADK Runner with multi-tool navigation

## Overview

Replace the local HTTP service path and the inverted-orchestration pattern with a unified
ADK `Runner` in-process execution path. Both local and deployed runs will use the same
`root_agent` definition. The agent will expose two navigation tools so the LLM drives
genuine file inspection rather than reformatting deterministic output.

Key decisions carried forward from origin document:
- **ADK Runner in-process** replaces the HTTP service (same code path for local and Agent Engine)
- **Fix the architectural inversion** — LLM drives tool calls, not the other way around
- **Multi-tool navigation** — `get_manifest_summary` + `read_dbt_file` replace the monolithic tool
- **Skip GCS for local runs** — tools read local file paths directly

## Problem Statement

Two execution paths exist and have diverged architecturally
(see origin: `docs/brainstorms/2026-04-12-unified-adk-review-architecture-requirements.md`):

1. **Agent Engine path** (`agent.py`): ADK `Agent` with `review_dbt_submission` as a tool.
   The LLM calls the tool, but the tool does all the work and returns a finished `ReviewResult`.
   The LLM only reformats it. Architecturally correct in shape but inverted in intent.

2. **Local service path** (`service/`, `integrations/vertex.py`): HTTP server runs a
   deterministic pipeline then calls Vertex as a plain function — the LLM is a callable,
   not a driver. This path was solving a problem ADK already solves natively.

The result is two systems that share types but not logic, where neither path genuinely
lets the LLM reason over dbt project files.

## Proposed Solution

### New tool design (`agent.py`)

Replace `review_dbt_submission` with two tools:

**`get_manifest_summary(manifest_uri: str) -> dict`**
- Reads the manifest (local path or `gs://`)
- Calls `collect_review_targets(manifest)` to derive model/source file list
- Returns a structured summary: list of file paths with their node type (model/source/test),
  tags, materialisation, and test coverage from the manifest
- Does NOT return raw manifest JSON — that would blow the context budget
  (see origin and `docs/solutions/best-practices/local-orchestrator-bounded-vertex-context-2026-04-06.md`)

**`read_dbt_file(project_uri: str, file_path: str) -> str`**
- Reads one file by name from the project archive (local zip or `gs://` zip)
- Accepts `.sql`, `.yml`, `.yaml`, `.md` only (same filter as existing `source_reader.py`)
- Truncates at 4000 chars with a `-- truncated --` marker (preserves existing behaviour)
- Returns the file content as a string

Both tools accept plain `str` inputs (not dataclasses), matching the existing documented
pattern for ADK tool signatures
(see `docs/solutions/best-practices/teaching-comments-and-thin-agent-boundaries-2026-04-05.md`).

### Updated agent instruction

The `root_agent` instruction changes from "call `review_dbt_submission` and return JSON only"
to a workflow instruction:

```
You are reviewing a dbt project submission.
1. Call get_manifest_summary with the manifest_uri to understand the project structure.
2. Based on the summary, call read_dbt_file for each file that is relevant to your review.
   Prioritise model SQL files and their corresponding schema YAML files.
3. Review the files for dbt correctness and quality:
   missing descriptions, missing column definitions, anti-patterns, ref/source usage.
4. Return JSON only, matching the ReviewResult schema.
   Use only file paths from the manifest summary when reporting findings.
   Preserve the provided run_id exactly.
```

Prompt guidance rules from `config/prompts/` (currently `global/base.md` and
`scoped/staging-guidance.md`) should be migrated into the instruction string or loaded
at agent construction time and appended to the instruction.

### New local CLI execution path (`cli.py`)

Replace the three-way branch in `build_default_review` with two paths:

1. **Remote Agent Engine** (unchanged): when `DBT_VERTEX_AGENT_RESOURCE_NAME` is set,
   use `run_remote_review` from `integrations/agent_engine.py`.

2. **Local ADK Runner** (new default): construct a `Runner` with `InMemorySessionService`
   and call `runner.run(...)` in-process. Extract the final text event and parse as JSON
   into a `ReviewResult`.

For local runs, skip GCS upload entirely. `prepare_local_run` (new function replacing
`default_prepare` for the local path) will:
- Call `create_project_archive(request.project_path, output_dir / "project.zip")`
- Return `SubmissionArtifacts` with local file paths (not `gs://` URIs)

The `review` subcommand's `--local-service-url` flag is removed.

### ADK Runner usage pattern

```python
# Resolved from ADK source: google.adk.runners.Runner (runners.py:113)
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

session_service = InMemorySessionService()
runner = Runner(
    agent=root_agent,
    app_name="dbt-review",
    session_service=session_service,
    auto_create_session=True,
)
# runner.run() is synchronous, suitable for CLI use (runners.py:438)
# Note: docstring calls it "local testing and convenience" — acceptable for CLI
events = list(runner.run(
    user_id="cli",
    session_id=run_id,
    new_message=types.Content(
        role="user",
        parts=[types.Part(text=f"Review this dbt submission. run_id={run_id} "
                               f"project_uri={submission.project_uri} "
                               f"manifest_uri={submission.manifest_uri}")]
    ),
))
```

Event parsing reuses the same pattern as `extract_final_text` in `integrations/agent_engine.py`.

## Implementation Phases

### Phase 1: New tools in `agent.py`

**Goal:** Replace `review_dbt_submission` with `get_manifest_summary` + `read_dbt_file`.
Both tools work for local paths and `gs://` URIs.

Tasks:
- [ ] Add `get_manifest_summary(manifest_uri: str) -> dict` to `agent.py`
  - Read manifest via `download_text` (GCS) or `Path.read_text` (local)
  - Call `collect_review_targets(manifest)` from `review/manifest.py`
  - Return structured dict: `{run_id, files: [{path, node_type, tags, materialization, has_tests}]}`
- [ ] Add `read_dbt_file(project_uri: str, file_path: str) -> str` to `agent.py`
  - For local zip: open with `zipfile.ZipFile`, read named member
  - For `gs://`: `download_bytes` then open with `zipfile.ZipFile(BytesIO(...))`
  - Filter to reviewable suffixes (`.sql`, `.yml`, `.yaml`, `.md`)
  - Truncate at 4000 chars
- [ ] Remove `review_dbt_submission` and `review_submission`
- [ ] Update `get_root_agent()` to use `tools=[get_manifest_summary, read_dbt_file]`
- [ ] Update agent `instruction` to the multi-step workflow (see above)
- [ ] Load and embed prompt guidance from `config/prompts/global/base.md` into instruction

**Files changed:** `src/dbt_vertex_agent/agent.py`

**Files unchanged:** `review/manifest.py`, `review/source_reader.py`, `integrations/storage.py`

### Phase 2: Local ADK Runner in `cli.py`

**Goal:** Replace the local service path in the CLI with an in-process `Runner` call.

Tasks:
- [ ] Add `run_local_adk_review(submission: SubmissionArtifacts) -> ReviewResult` to `cli.py`
  - Construct `Runner(agent=root_agent, app_name="dbt-review", session_service=InMemorySessionService(), auto_create_session=True)`
  - Call `runner.run(user_id="cli", session_id=submission.run_id, new_message=...)`
  - Call `extract_final_text(events)` (move or copy from `integrations/agent_engine.py`)
  - Parse JSON into `ReviewResult.from_model_payload(payload)`
- [ ] Add `prepare_local_run(request: ReviewRequest) -> SubmissionArtifacts` to `cli.py`
  - Call `create_project_archive(request.project_path, request.output_dir / "project.zip")`
  - Return `SubmissionArtifacts(run_id=uuid4().hex, project_uri=str(archive_path), manifest_uri=str(request.manifest_path))`
- [ ] Simplify `build_default_review`: remote Agent Engine branch unchanged; default branch returns `run_local_adk_review`
- [ ] Simplify `main`: remove `serve` dispatch and `local_service_url` config mutation
- [ ] Simplify `parse_args`: remove `serve` subparser and `--local-service-url` from `review`
- [ ] Remove functions: `run_local_service`, `build_service_model_callback_from_environment`, `prepare_local_service_submission`, `default_prepare`
- [ ] Remove imports: `service.app`, `service.client`, `service.contracts`, `service.handlers`, `integrations.vertex`

**Files changed:** `src/dbt_vertex_agent/cli.py`

### Phase 3: Delete service path code

**Goal:** Remove all service path modules, shims, and tests.

Delete these files entirely:
- [ ] `src/dbt_vertex_agent/service/` (all 6 files: `app.py`, `client.py`, `contracts.py`, `handlers.py`, `settings.py`, `__init__.py`)
- [ ] `src/dbt_vertex_agent/integrations/vertex.py`
- [ ] `src/dbt_vertex_agent/prompts/builder.py`
- [ ] `src/dbt_vertex_agent/prompts/context.py`
- [ ] `src/dbt_vertex_agent/prompts/guidance.py`
- [ ] `src/dbt_vertex_agent/prompts/__init__.py` (if empty after above)
- [ ] Root shims: `service.py`, `service_handlers.py`, `service_settings.py`, `http_client.py`, `service_contract.py`, `prompting.py`, `context_builder.py`, `prompt_guidance.py`, `model_client.py`
- [ ] Tests: `tests/test_service.py`, `tests/test_http_client.py`, `tests/test_service_contract.py`, `tests/test_model_client.py`

Fix surviving files that import deleted modules:
- [ ] `src/dbt_vertex_agent/output.py:7` — remove `from dbt_vertex_agent.service.contracts import DebugArtifacts` and any `write_debug_artifacts` that depends on it (debug artifact writing can be removed or simplified to write the raw prompt string)
- [ ] `src/dbt_vertex_agent/config.py` — remove `local_service_url` field from `Config`
- [ ] Root shims to keep but update imports: `review_contract.py`, `source_reader.py`, `manifest_analysis.py`, `storage.py`, `remote.py`, `review_policy.py` — verify no deleted modules are referenced

**Files changed:** `output.py`, `config.py`, affected shims

### Phase 4: Update tests

**Goal:** Replace service-path tests with ADK Runner path tests.

- [ ] Add `tests/test_local_runner.py` — test `run_local_adk_review` with a fake `root_agent` whose tools return controlled outputs; verify `ReviewResult` is parsed correctly
- [ ] Add tool unit tests to `tests/test_agent.py`:
  - `get_manifest_summary` with local manifest path
  - `get_manifest_summary` with a valid manifest that has no reviewable paths (empty result)
  - `read_dbt_file` with a local zip — happy path
  - `read_dbt_file` with a non-reviewable extension — returns error/empty string
  - `read_dbt_file` with a file that exceeds 4000 chars — returns truncated content
- [ ] Update `tests/test_cli.py` — remove `serve` subcommand tests, `RunLocalServiceTests`, `BuildServiceModelCallbackTests`; add `PrepareLocalRunTests`
- [ ] Update `tests/test_rendering.py:68` — remove `DebugArtifacts` construction if that type is deleted
- [ ] Run `PYTHONPATH=src python3 -m unittest discover -s tests -v` to confirm green

### Phase 5: Quality and cleanup

- [ ] Run `ruff format .` and `ruff check .`
- [ ] Run `mypy` (strict mode targets `src/`)
- [ ] Delete `config/prompts/` directory if all content has been migrated to the agent instruction
- [ ] Update `README.md` to remove the "Local HTTP Orchestrator Mode" section and reference to `docs/local-orchestrator-mode.md`
- [ ] Consider whether `docs/local-orchestrator-mode.md` and `docs/brainstorms/2026-04-05-local-orchestrator-remote-model-requirements.md` should be archived or deleted

## Technical Considerations

### Async/sync boundary
`Runner.run()` is documented as synchronous and "for local testing and convenience"
(`runners.py:438`). The CLI is synchronous. This is acceptable — the same pattern already
exists in `integrations/agent_engine.py` where `asyncio.run()` wraps the async Agent Engine
path. Use `runner.run()` directly; do not wrap in `asyncio.run()`.

### Event extraction
`extract_final_text(events)` in `integrations/agent_engine.py` already handles the ADK event
shape. For the local Runner path, the same logic applies — iterate events in reverse looking
for the last `text` part. This function can be moved to `agent.py` or kept in
`integrations/agent_engine.py` and imported from there.

### Prompt guidance migration
`config/prompts/global/base.md` contains the base review instruction. Load it at agent
construction time (`get_root_agent()`) and append to the `instruction` string. The scoped
rules (`scoped_rules.json`, `scoped/staging-guidance.md`) were selected per-run based on
file names; in the multi-tool design the LLM decides what to look at, so these can be
simplified to static instruction content or dropped initially.

### GCS upload for Agent Engine path
`prepare_submission` with GCS upload is still needed when `DBT_VERTEX_AGENT_RESOURCE_NAME`
is set (the deployed agent reads from GCS). The `default_prepare` function stays in `cli.py`
but is only called for the remote Agent Engine branch.

### `run_id` in tool responses
`get_manifest_summary` should accept and echo back a `run_id` so the LLM can include it in
the final JSON response, matching the `ReviewResult` contract's `run_id` field. Alternatively,
pass `run_id` in the initial message and instruct the agent to preserve it (current approach
in `agent_engine.py:64`).

## Acceptance Criteria

- [ ] `dbt-vertex-agent review --project ... --manifest ...` runs without a `serve` process
      and without uploading to GCS when `DBT_VERTEX_AGENT_RESOURCE_NAME` is not set
- [ ] The same `root_agent` runs via `Runner` locally and via Agent Engine when deployed
- [ ] The LLM calls `get_manifest_summary` first, then selectively calls `read_dbt_file`
      for relevant files — verified by test with a fake agent whose tool calls are recorded
- [ ] `dbt-vertex-agent serve` no longer exists as a subcommand
- [ ] `service/` package is gone; `mypy` and `ruff` pass clean
- [ ] All surviving tests pass: `PYTHONPATH=src python3 -m unittest discover -s tests -v`

## Dependencies & Risks

**ADK `Runner.run()` sync note:** Marked "for local testing and convenience" in the docstring.
If this becomes a production concern, wrapping with `asyncio.run(runner.run_async(...))` is a
drop-in replacement — the public API is identical.

**`extract_final_text` portability:** Currently in `integrations/agent_engine.py`. Moving or
duplicating it risks divergence if the ADK event shape changes. Prefer moving it to `agent.py`
as a module-level helper used by both paths.

**Prompt guidance loss:** The scoped guidance rules (per-file-type review focus) were a
meaningful feature of the service path. Migrating them to a static instruction string may
reduce review quality for projects with staging models. Consider a follow-on task to encode
them as part of the `get_manifest_summary` response (e.g., returning a `guidance` field per
node type) rather than pre-filtering on the orchestrator side.

**Test coverage gap:** The service path had 9 test cases in `test_service.py` covering
guidance selection, debug artifacts, CSV seed exclusion, and error handling. New tests in
Phase 4 must cover equivalent scenarios for the tool functions.

## System-Wide Impact

### Interaction graph
`cli.py:main` → `run_review` → `run_local_adk_review` → `Runner.run()` → `root_agent` →
LLM → `get_manifest_summary` (tool call) → returns manifest summary → LLM →
`read_dbt_file` (tool call, N times) → returns file content → LLM → final JSON response →
`ReviewResult.from_model_payload` → `write_review_artifacts`.

### State lifecycle
`InMemorySessionService` creates a session per review run. Sessions are not persisted.
No orphan risk — the session lives only for the duration of the `runner.run()` call.

### API surface parity
`deploy.py` uses `root_agent` via `AdkApp`. After Phase 1, `root_agent` exposes the new
multi-tool interface. `deploy.py` requires no changes — it wraps whatever `root_agent`
exposes. The deployed Agent Engine and local Runner will be identical.

## Sources & References

### Origin
- **Origin document:** [docs/brainstorms/2026-04-12-unified-adk-review-architecture-requirements.md](../brainstorms/2026-04-12-unified-adk-review-architecture-requirements.md)
  Key decisions carried forward: ADK Runner in-process, fix architectural inversion, multi-tool navigation, skip GCS for local runs, remove `service/` entirely.

### Internal References
- Current agent definition: `src/dbt_vertex_agent/agent.py:69-100`
- Manifest target collection: `src/dbt_vertex_agent/review/manifest.py:17`
- File extraction (zip): `src/dbt_vertex_agent/review/source_reader.py:34`
- GCS helpers: `src/dbt_vertex_agent/integrations/storage.py`
- Event extraction (reuse): `src/dbt_vertex_agent/integrations/agent_engine.py:20-41`
- ADK Runner class: `.venv/lib/python3.12/site-packages/google/adk/runners.py:113`
- ADK Runner.run() (sync): `.venv/lib/python3.12/site-packages/google/adk/runners.py:438`

### Institutional Learnings
- Keep manifest parsing and snippet extraction before LLM — do not pass raw manifests:
  `docs/solutions/best-practices/local-orchestrator-bounded-vertex-context-2026-04-06.md`
- Use plain string tool signatures; deterministic logic stays in Python modules:
  `docs/solutions/best-practices/teaching-comments-and-thin-agent-boundaries-2026-04-05.md`
- Run `ruff` + `mypy` before and after structural changes:
  `docs/solutions/best-practices/introduce-python-quality-checks-early-2026-04-06.md`
