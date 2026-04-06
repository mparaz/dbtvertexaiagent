---
date: 2026-04-06
topic: structure-and-python-tooling
---

# Structure And Python Tooling

## Problem Frame
The package has grown from a simple flat scaffold into a repo with distinct responsibilities: CLI orchestration, local service handling, prompt construction, review policy, storage, and remote model integration. The current flat module layout is still workable, but it is starting to increase cognitive load. At the same time, the project does not yet have a modern Python formatting, linting, and typing setup that matches the desired code quality bar.

The goal is to make the codebase easier to understand and extend by applying a shallow, responsibility-based subpackage structure and by adopting a strong but not overcomplicated Python quality toolchain.

## Requirements

**Structure**
- R1. Split the internals into a minimal set of shallow subpackages organized by responsibility.
- R2. The split must improve clarity without introducing a deep or speculative hierarchy.
- R3. Public entrypoints and package behavior must remain stable for the current CLI and runtime use cases.
- R4. The restructuring should make it easier to understand the code through the lenses of Ousterhout’s module/interface thinking and Hermans’ cognitive-load/readability concerns.

**Tooling**
- R5. Add `ruff format` as the code formatter.
- R6. Add `ruff check` as the primary linting/checking layer.
- R7. Add `mypy` with strict settings.
- R8. Do not add `pylint`.
- R9. Tooling configuration should be consolidated in standard project config where practical.

**Contributor Workflow**
- R10. The repo must document the intended package structure and how to think about module boundaries.
- R11. The repo must document how to run formatting, linting, and strict type checking locally.
- R12. The quality setup should be strong, but maintainable enough for a small project without excessive tool overlap.

## Success Criteria
- A new contributor can look at the package tree and understand the main responsibilities without reading every file.
- Formatting, linting, and strict typing can be run with a small, clear command set.
- The structure feels simpler to navigate after the refactor, not just more formally organized.

## Scope Boundaries
- Do not perform a large architectural rewrite just to satisfy package naming preferences.
- Do not introduce deep nested package trees.
- Do not add multiple overlapping Python linting tools.
- Do not treat strict typing as a reason to add unnecessary abstraction.

## Key Decisions
- Use Ousterhout and Hermans as design guidance, not rigid enforcement frameworks.
  Rationale: They are useful lenses for module depth, readability, and cognitive load, but they should not force ceremony.
- Split the package minimally by responsibility.
  Rationale: The codebase is large enough to justify structure, but not large enough to need an elaborate hierarchy.
- Use `ruff format`, `ruff check`, and strict `mypy`.
  Rationale: This gives strong quality signals with less overlap and maintenance cost than adding `pylint`.
- Exclude `pylint`.
  Rationale: The user wants strong checks, but not the extra strictness and config overhead that `pylint` would add here.

## Dependencies / Assumptions
- The current `src/` layout remains the packaging strategy.
- Existing tests should continue to serve as the main regression net during the refactor.

## Outstanding Questions

### Deferred to Planning
- [Affects R1][Technical] What exact shallow subpackages best match the current responsibility boundaries?
- [Affects R7][Technical] Which strict `mypy` rules should be adopted immediately versus phased in through targeted ignores or gradual cleanup?
- [Affects R10][Technical] Where should the package-structure guidance live so contributors can find it easily?

## Next Steps
→ /prompts:ce-plan for structured implementation planning
