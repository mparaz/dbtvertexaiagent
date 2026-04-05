---
title: Teaching comments work best when they explain the system shape, not just individual lines
date: 2026-04-05
category: best-practices
module: dbt_vertex_agent
problem_type: best_practice
component: documentation
severity: medium
applies_when:
  - onboarding yourself to a new greenfield codebase
  - building an agent system with both deterministic code and an LLM-facing layer
  - trying to make infrastructure code learnable for future readers
tags: [comments, documentation, vertex-ai, agents, dbt, python]
---

# Teaching comments work best when they explain the system shape, not just individual lines

## Context
This project started as a greenfield Vertex AI dbt review agent with almost no explanatory comments. That made it harder to learn from because the code mixes several layers:

- local CLI orchestration
- artifact packaging and GCS boundaries
- local review logic
- Agent Engine deployment and remote query integration

In a repo like this, a reader is not only trying to learn what one function does. They are also trying to learn why the project is split into these modules and where the deterministic Python logic ends and the LLM-facing agent layer begins.

## Guidance
Comment aggressively in early-stage educational codebases, but comment with purpose.

The most useful pattern in this repo is:

1. Keep the deterministic work in normal Python modules.
2. Keep the agent-facing layer thin.
3. Use comments to explain the data flow between those layers.

That means comments should explain:

- what contract each dataclass or function represents
- where local paths turn into GCS URIs
- where synchronous CLI code hands off to async remote agent code
- where manifest-derived evidence turns into policy findings
- why some imports are lazy
- why top-level deployment files exist in addition to the package code

This is stronger than only adding comments like "create parser" or "return config", because the real learning value is in understanding the system boundaries.

Examples from this repo:

- `src/dbt_vertex_agent/cli.py` explains the four-step run flow: normalize inputs, submit artifacts, run review, save outputs.
- `src/dbt_vertex_agent/agent.py` explains the split between deterministic Python review logic and the thin ADK agent wrapper.
- `src/dbt_vertex_agent/remote.py` explains why a synchronous CLI still wraps an async Agent Engine query path.
- `src/dbt_vertex_agent/storage.py` explains why Google Cloud imports are lazy and how `gs://` URIs are decomposed for the SDK.
- `agent.py` and `deploy.py` explain why repo-root files exist even though the main package lives under `src/`.

## Why This Matters
Without these comments, a learner can still read the code, but they have to reverse-engineer the architecture from imports and call sites. That slows down understanding and makes future edits riskier.

In an agent project, this matters even more because there are usually two different execution models present at once:

- normal deterministic application code
- LLM/agent orchestration code with external runtime requirements

If those boundaries are not explained, readers tend to over-attribute behavior to the LLM layer and miss the fact that much of the important logic should stay in ordinary testable Python.

## When to Apply
- When the repo is new and local conventions have not yet become obvious.
- When the code is intended to teach as well as execute.
- When the system crosses storage, packaging, deployment, and agent-runtime boundaries.
- When a project uses thin orchestration over deterministic code and you want future contributors to preserve that shape.

## Examples
Before:

```python
def build_default_review(config: Config) -> Callable[[SubmissionArtifacts], ReviewResult]:
    if config.agent_resource_name:
        return lambda submission: run_remote_review(config.agent_resource_name, submission)

    return review_submission
```

After:

```python
def build_default_review(config: Config) -> Callable[[SubmissionArtifacts], ReviewResult]:
    # If the user configured a deployed Agent Engine resource, prefer the remote path.
    # Otherwise we fall back to the local review function, which is useful for tests
    # and for understanding the review flow without deploying first.
    if config.agent_resource_name:
        return lambda submission: run_remote_review(config.agent_resource_name, submission)

    return review_submission
```

Before:

```python
def review_dbt_submission(project_uri: str, manifest_uri: str) -> dict:
    result = review_submission(
        SubmissionArtifacts(
            run_id="remote-run",
            project_uri=project_uri,
            manifest_uri=manifest_uri,
        )
    )
    return result.to_dict()
```

After:

```python
def review_dbt_submission(project_uri: str, manifest_uri: str) -> dict:
    # This function is the tool exposed to the ADK agent. The tool layer uses
    # plain strings because LLM tool calls are much simpler when their inputs are
    # basic JSON types.
    result = review_submission(
        SubmissionArtifacts(
            run_id="remote-run",
            project_uri=project_uri,
            manifest_uri=manifest_uri,
        )
    )
    return result.to_dict()
```

## Related
- `docs/plans/2026-04-05-001-feat-vertex-dbt-review-agent-plan.md`
- `docs/brainstorms/2026-04-05-vertex-ai-dbt-review-agent-requirements.md`
