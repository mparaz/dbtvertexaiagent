---
date: 2026-04-12
topic: unified-adk-review-architecture
---

# Unified ADK Review Architecture

## Problem Frame

The project currently has two separate review paths — an Agent Engine path (ADK `Agent` with a tool,
deployed to Vertex) and a local service path (HTTP server that calls Vertex directly as an
orchestrated function call). These paths have diverged architecturally: the local service path
inverts the intended agent pattern by driving the LLM from Python orchestration code rather than
letting the LLM drive tool calls. The local service path also reimplements capabilities that ADK
already provides natively (local execution, session management). The goal of this work is to unify
both paths around ADK, remove the local service path, and fix the architectural inversion so the
LLM genuinely reasons over dbt project files rather than just reformatting deterministic output.

## Requirements

**Execution path**
- R1. The CLI `review` command must execute the agent via an ADK `Runner` in-process, using the
  same `root_agent` definition used for Agent Engine deployment.
- R2. The `serve` subcommand and the entire `service/` package must be removed.
- R3. For local review runs, the packaged project archive and manifest must be accessible to the
  agent tools via local file paths — no GCS upload should be required when running locally.
- R4. For Agent Engine deployment runs, the existing GCS upload and remote tool read behavior
  must continue to work unchanged.

**Tool design**
- R5. The agent must expose at least two tools for navigating the dbt project:
  one that returns a structured manifest summary (model list, lineage, tags, test coverage),
  and one that reads the content of a specific file from the project archive.
- R6. Tools must accept both local file paths and `gs://` URIs so the same tool code runs in
  local and deployed execution without branching.
- R7. The LLM must decide which files to inspect based on the manifest summary it receives —
  the agent must not receive a pre-built context bundle containing all file snippets.

**Review quality**
- R8. The LLM must produce review findings by reasoning over the file contents it retrieves,
  not by reformatting output from the deterministic rule engine.
- R9. Prompt guidance from `config/prompts/` must remain available to the agent to inform
  dbt-specific review behavior.

## Success Criteria

- A developer can run `dbt-vertex-agent review --project ... --manifest ...` locally and receive
  LLM-generated findings without starting a separate service process or uploading to GCS.
- The same `root_agent` definition runs identically in local (`Runner`) and deployed
  (Agent Engine) modes.
- The LLM selectively reads dbt files based on manifest data rather than receiving all content
  in one pre-built prompt.
- The `service/` package and `serve` command are gone with no replacement.

## Scope Boundaries

- No change to the Agent Engine deployment flow (`deploy.py`).
- No requirement to implement the "bounded review slices" architecture described in
  `docs/brainstorms/2026-04-06-dbt-review-architecture-notes.md` — that is a follow-on improvement.
- No requirement to preserve or migrate existing local service tests beyond converting them
  to cover the new in-process path.
- No change to the `packaging.py` zip format or GCS upload contract for the Agent Engine path.

## Key Decisions

- **ADK Runner in-process over HTTP service**: ADK already supports local execution natively.
  The HTTP service was solving a problem ADK solves better, and should be removed.
- **Fix the architectural inversion**: The LLM should drive tool calls, not be called as a
  function by Python orchestration. This is the correct agent pattern and matches Agent Engine behavior.
- **Multi-tool navigation over single context bundle**: Giving the LLM separate manifest and
  file-read tools lets it navigate the project selectively, which is more faithful to the intended
  dbt-aware review design and avoids pre-loading content the LLM may not need.
- **Skip GCS for local runs**: With in-process execution, tools can read local paths directly.
  Removing the mandatory upload simplifies local development significantly.

## Dependencies / Assumptions

- `google-adk` provides a `Runner` class (or equivalent) that can execute an ADK `Agent`
  in-process with a session, without requiring Agent Engine deployment.
- The ADK session contract (`InMemorySessionService` or equivalent) is available for local runs.
- The prompt guidance in `config/prompts/` can be embedded in the agent instruction or passed
  through a tool without requiring the existing `prompts/builder.py` pipeline.

## Outstanding Questions

### Deferred to Planning

- [Affects R1][Needs research] What is the exact ADK `Runner` API for in-process execution
  (class name, session service, `run()` vs `stream()` call shape)?
- [Affects R5][Technical] Should the manifest summary tool parse the zip to extract manifest
  bytes, or should manifest and project archive be passed as separate inputs?
- [Affects R7][Technical] How should the file-read tool handle truncation for large SQL files
  (currently capped at 4000 chars in the service path)?
- [Affects R9][Technical] What is the best way to surface prompt guidance to the agent —
  embedded in the `Agent` instruction string, returned by a dedicated tool, or injected into
  the session context?
- [Affects R2][Technical] Which additional modules beyond `service/` can be removed
  (`integrations/vertex.py`, `prompts/builder.py`, `prompts/context.py`, shim modules at
  package root) once the service path is gone?

## Next Steps
→ /ce:plan for structured implementation planning
