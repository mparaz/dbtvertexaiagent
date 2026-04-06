---
date: 2026-04-06
topic: dbt-review-architecture-notes
---

# dbt Review Architecture Notes

## Context
These notes capture the architectural conclusions from the latest discussion so the next session can resume from the same mental model.

## Key Realizations

- This project should be treated as a **dbt-specific review system**, not as a generic code review tool.
- dbt review is different from normal programming-language review because the important units are:
  - models
  - schema YAML
  - lineage
  - tests
  - tags/materializations
  - semantic consistency between SQL and metadata
- The dbt `manifest.json` should be used as a **local semantic graph**, not dumped raw into the LLM prompt.

## Current State

- The current LLM path is still **single-shot batch review**:
  - one submission
  - one reduced context
  - one prompt
  - one model call
  - one response
- The service does **not** slice the batch internally yet.
- The prompt now includes:
  - reduced context
  - selected source snippets
  - prompt-guidance Markdown from `config/prompts/`

## Important Constraint

- Sending the full manifest to the LLM is likely the wrong move because it will waste prompt budget and reduce signal.
- Naive per-model slicing is also insufficient because the model would lose broader project context.

## Preferred Future Direction

The likely correct architecture is:

1. **Batch submission**
   - Upload the full dbt project and manifest once.
2. **Local semantic analysis**
   - Use the manifest locally to derive model-centered review slices.
3. **Bounded review slices**
   - Each slice should include:
     - one model or small cluster
     - relevant schema YAML
     - immediate lineage neighborhood
     - selected prompt guidance
     - compact global project context
4. **Aggregated batch output**
   - Merge slice findings into one final review result.

This preserves batch review while avoiding:

- one giant prompt for the entire project
- isolated single-model prompts with no surrounding context

## Open Product Direction

- The next major design step is likely **internal slicing for batch review** rather than trying to expand the current single prompt to hold the full semantic value of the manifest.
- If this is pursued later, the design should favor:
  - bounded local context
  - compact shared/global context
  - final aggregation

## Why This Matters

- It clarifies that future work should optimize for **dbt-aware review quality**, not generic code-review abstractions.
- It also suggests that infrastructure can stay reusable, while the actual review intelligence should remain domain-specific to dbt.
