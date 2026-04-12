# CLAUDE.md

## Project overview

**dbt Vertex Agent** — a Python CLI and Vertex AI Agent Engine runtime for reviewing dbt projects.
The agent ingests a dbt project directory and its `manifest.json`, packages and optionally uploads
them to GCS, then produces a structured review using a Vertex AI model or a locally-running
service that calls Vertex.

## Architecture

### Execution modes

There are three distinct runtime paths selected by environment config / CLI flags:

| Mode | How it works |
|---|---|
| **Local direct** | CLI → `review_submission()` in-process, no GCP required |
| **Local service** | CLI → HTTP to `dbt-vertex-agent serve` → Vertex model call |
| **Remote Agent Engine** | CLI → Vertex AI Agent Engine (deployed via `deploy.py`) |

### Package layout (`src/dbt_vertex_agent/`)

| Module / package | Role |
|---|---|
| `cli.py` | Entry point, subcommands: `review` and `serve` |
| `config.py` | Reads environment variables into a `Config` dataclass |
| `packaging.py` | Zips the dbt project; builds `SubmissionArtifacts` |
| `manifest_analysis.py` | Parses `manifest.json` to identify review targets |
| `review/` | `contracts.py` (types), `policy.py`, `manifest.py`, `source_reader.py` |
| `prompts/` | `builder.py` assembles prompts; `guidance.py` loads config rules |
| `service/` | `app.py` (HTTP server), `client.py`, `contracts.py`, `handlers.py`, `settings.py` |
| `integrations/` | `storage.py` (GCS), `vertex.py` (model callback), `agent_engine.py` (remote run) |
| `agent.py` | ADK root agent exposed for Vertex AI Agent Engine deployment |
| `rendering.py` | JSON + Markdown output formatting |
| `output.py` | Writes review artifacts to `runs/<run-id>/` |
| `models.py` | Shared dataclasses (`ReviewRequest`, `SubmissionArtifacts`, etc.) |

Top-level `deploy.py` deploys the agent to Vertex AI Agent Engine.

### Config — environment variables

| Variable | Purpose |
|---|---|
| `DBT_VERTEX_PROJECT_ID` | GCP project |
| `DBT_VERTEX_REGION` | Vertex region (e.g. `us-central1`) |
| `DBT_VERTEX_STAGING_BUCKET` | `gs://...` bucket for submission artifacts |
| `DBT_VERTEX_OUTPUT_DIR` | Local output root (default `runs`) |
| `DBT_VERTEX_AGENT_RESOURCE_NAME` | Deployed Agent Engine resource name |
| `DBT_VERTEX_MODEL` | Vertex model name (used in local-service mode) |
| `DBT_VERTEX_DEBUG` | Set `1`/`true` to emit debug artifacts |

### Prompt guidance

Rules are configured in `config/prompts/scoped_rules.json` and loaded by
`prompts/guidance.py`. These control what the review focuses on per dbt node type.

## Development

```bash
# Install (base — no GCP SDK)
pip install -e .

# Install (with GCP runtime)
pip install -e '.[gcp]'

# Install dev tools
pip install -e '.[dev]'
```

## Testing

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Tests are in `tests/` and use injected callbacks to avoid real GCP calls.

## Quality checks

```bash
ruff format .
ruff check .
mypy
```

- Line length: 100
- mypy: strict mode, targets `src/`
- ruff lint rules: B, E, F, I, N, UP

## Known limitations / in-progress

- Review depth is intentionally minimal — rule evaluation in `review/policy.py` should be
  expanded before production use.
- The `src/dbt_vertex_agent/` root still contains some legacy shim modules
  (`review_contract.py`, `service_contract.py`, `source_reader.py`, etc.) that proxy to
  the sub-packages introduced in the last refactor. These may be cleaned up over time.
