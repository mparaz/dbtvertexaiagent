---
date: 2026-04-06
topic: debug-mode-and-rule-framework
---

# Debug Mode And Rule Framework

## Problem Frame
The local-orchestrator path now performs real context reduction and can call Gemini directly on Vertex AI, but it is still hard to inspect exactly what was sent to the model for a specific run. At the same time, the deterministic dbt policy layer has a few hard-coded checks but no clear extension point for adding more rules cleanly over time.

The goal of this increment is to make LLM-backed review runs inspectable and teachable, while also giving the deterministic rule layer a minimal structure that future dbt rules can plug into without requiring a redesign.

## Requirements

**Debug Artifacts**
- R1. The system must support a debug mode that persists additional run artifacts for LLM-backed review inspection.
- R2. Debug mode must write the reduced review context and the rendered prompt for a run.
- R3. Debug artifacts must be written into the normal run output directory beside the standard review artifacts.
- R4. Debug mode must be enableable from both the local service environment and from CLI-driven local review runs.
- R5. When debug mode is disabled, the standard run artifact layout and behavior must remain unchanged.

**Deterministic Rule Framework**
- R6. The deterministic dbt review layer must expose a lightweight rule registration point rather than keeping all manifest checks in one hard-coded function.
- R7. This pass must not add new deterministic dbt rules beyond the ones already implemented.
- R8. The codebase must document how future deterministic rules should be added, including where the rule function lives, what input it receives, and what it should return.
- R9. The framework must preserve the current `ReviewResult` and `Finding` contracts so future rules compose into the existing output flow without translation.

## Success Criteria
- A developer can inspect a completed debug-enabled run and see the exact reduced context and prompt that were sent to Gemini.
- A developer can identify one clear place in the code to register a new deterministic dbt rule.
- Existing non-debug runs continue to produce only the normal review artifacts.

## Scope Boundaries
- Do not add full request/response tracing for every internal function.
- Do not implement additional deterministic dbt rules in this pass.
- Do not redesign the `ReviewResult` response schema.
- Do not introduce a plugin or package-discovery system for rules.

## Key Decisions
- Debug mode persists `context.json` and `prompt.txt`, not the raw model response.
  Rationale: These are the highest-value learning artifacts for prompt inspection without expanding scope into full response tracing yet.
- Debug mode is controlled from both the service environment and the CLI path.
  Rationale: The service owns behavior for `curl` and other local clients, while the CLI should also be able to request the same behavior in normal developer workflows.
- Debug artifacts live in the normal run directory.
  Rationale: One run folder should contain the full evidence for that run, not force the user to correlate multiple directories.
- The deterministic rule system should use a lightweight registry.
  Rationale: This creates a stable extension point without overbuilding a plugin architecture.

## Dependencies / Assumptions
- The existing local output flow under `runs/<run_id>/` remains the canonical artifact location.
- The service already has enough information at request time to render the final prompt before the model call.

## Outstanding Questions

### Deferred to Planning
- [Affects R4][Technical] How should CLI-triggered debug mode be expressed in arguments and config so it stays consistent with the existing local-service path?
- [Affects R2][Technical] Should the debug artifacts be written by the local service during request handling, by the CLI after the HTTP response, or by a shared helper used by both?
- [Affects R6][Technical] What is the smallest registry shape that keeps rules easy to test without introducing unnecessary abstraction?

## Next Steps
→ /prompts:ce-plan for structured implementation planning
