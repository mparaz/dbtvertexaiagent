---
date: 2026-04-06
topic: prompt-guidance-config
---

# Prompt Guidance Config

## Problem Frame
The current Gemini prompt is built from a fixed instruction block plus reduced dbt context. That works, but it leaves no clean place for project-specific review guidance such as style rules, domain policies, or folder-specific dbt conventions. We need a way to shape the LLM prompt from repo-owned Markdown files without hard-coding every guidance rule into Python.

## Requirements

**Guidance Sources**
- R1. Add a prompt-guidance configuration area under `config/prompts/`.
- R2. The system must always include a small fixed set of global Markdown guidance files in the LLM prompt.
- R3. The system must optionally include additional Markdown guidance files based on glob matching against reviewed dbt file paths.

**Selection Behavior**
- R4. The initial selector must be file-path glob matching only.
- R5. The selection design must be extensible for future manifest-based criteria, but those selectors must not be implemented in this pass.
- R6. Guidance selection must be deterministic and inspectable so a developer can understand why a guidance file was included.

**Prompt Integration**
- R7. Selected guidance content must be incorporated into the rendered LLM prompt alongside the reduced dbt review context.
- R8. Debug mode must make the included guidance visible through the existing prompt inspection path.
- R9. The absence of any optional guidance matches must still produce a valid prompt using only the global guidance set.

**Contributor Experience**
- R10. The repo must document how to add new global guidance files and new glob-scoped guidance files.
- R11. The repo must document where future non-glob selectors would fit, without implementing them now.

## Success Criteria
- A contributor can add a Markdown guidance file under `config/prompts/` and have it affect prompt construction without editing core prompt text.
- A run involving reviewed files under a matching path includes the expected scoped guidance in the final prompt.
- Debug artifacts make it obvious which guidance text was included for a run.

## Scope Boundaries
- Do not implement manifest-based selector logic yet.
- Do not add a user-facing per-run file chooser for guidance files.
- Do not move deterministic Python review rules into Markdown configuration.
- Do not create a general-purpose prompt templating system.

## Key Decisions
- Store prompt-shaping files under `config/prompts/`.
  Rationale: This keeps runtime prompt guidance separate from docs and separate from deterministic review logic.
- Always include a small fixed global set.
  Rationale: Core review behavior should not depend on path matching.
- Add optional scoped guidance via file-path globs against reviewed files.
  Rationale: Folder-based dbt conventions are common and this keeps v1 selection easy to reason about.
- Keep the config structure extensible for future selector types.
  Rationale: The repo should be able to add manifest-based targeting later without reorganizing the prompt guidance folder.

## Dependencies / Assumptions
- The local service already knows the reviewed file paths before rendering the prompt.
- The existing debug mode continues to write `prompt.txt`, which can expose the selected guidance content.

## Outstanding Questions

### Deferred to Planning
- [Affects R2][Technical] What exact global guidance files should be created by default in the initial scaffold?
- [Affects R3][Technical] What metadata format should describe glob-scoped guidance selection without overbuilding the config surface?
- [Affects R8][Technical] Should debug mode expose guidance provenance only through `prompt.txt`, or also through a separate structured artifact?

## Next Steps
→ /prompts:ce-plan for structured implementation planning
