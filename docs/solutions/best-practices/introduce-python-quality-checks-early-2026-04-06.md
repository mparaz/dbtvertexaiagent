---
title: Introduce Python quality checks at the start of a project, not after the structure settles
date: 2026-04-06
category: best-practices
module: dbt_vertex_agent
problem_type: best_practice
component: tooling
severity: medium
applies_when:
  - Starting a new Python project or package
  - Planning to enforce formatting, linting, and static typing
  - Refactoring package structure after a period of unconstrained implementation
tags: [python, ruff, mypy, tooling, maintainability, development-workflow]
related_components: [documentation, development_workflow]
---

# Introduce Python quality checks at the start of a project, not after the structure settles

## Context
This repo adopted `ruff format`, `ruff check`, and strict `mypy` after the project already had meaningful breadth: compatibility wrappers, local and remote review paths, service code, prompt code, and deployment code.

The tooling still paid off, but adding it later created avoidable rework:

- imports had drifted across the refactor
- line-length cleanup spread through source and tests
- generic `dict` usage had to be tightened after the fact
- integration boundaries that had been "good enough" without typing became noisy under strict `mypy`
- package `__init__.py` exports exposed circular import problems only after the checks were active

None of these were hard problems, but they were cleanup work that could have been prevented.

## Guidance
Introduce the quality bar as soon as the initial package scaffold exists.

For a Python repo like this one, that means doing the following near the start:

1. Add the formatter and linter config to `pyproject.toml`.
2. Add `mypy` with a clear strictness policy for production code.
3. Run the checks before the codebase has enough surface area to accumulate style and typing drift.
4. Keep the checks in the regular development loop instead of treating them as a later hardening phase.

In this repo, the stable combination is:

- `ruff format`
- `ruff check`
- `mypy` in strict mode for `src/`

That combination is strong enough to catch real structural issues without the extra maintenance overhead of a larger linter stack.

## Why This Matters
Early checks change the shape of the code as it is written.

They push the codebase toward:

- cleaner import boundaries
- clearer public contracts
- smaller untyped escape hatches
- fewer ambiguous data structures at runtime boundaries
- less cleanup when refactoring module structure

Adding the checks later still works, but the cost is paid as a backlog of mechanical and typing fixes. That cost grows with the size of the codebase.

## Practical Rule
If you know you want formatting, linting, and static typing, configure them before or during the first real implementation slice.

Do not wait for:

- "after the architecture is clearer"
- "after the first feature lands"
- "after the package structure stabilizes"

That instinct usually creates more rework, not less.

## Related
- [Keep dbt review orchestration local and send only bounded source context to Vertex](/Users/mparaz/projects/gcp/dbtvertexaiagent/docs/solutions/best-practices/local-orchestrator-bounded-vertex-context-2026-04-06.md)
- [Teaching Comments And Thin Agent Boundaries](/Users/mparaz/projects/gcp/dbtvertexaiagent/docs/solutions/best-practices/teaching-comments-and-thin-agent-boundaries-2026-04-05.md)
