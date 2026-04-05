# dbt Vertex Agent

Local CLI and Vertex AI agent runtime for reviewing dbt projects.

## Current state

This repository now contains:

- a Python package scaffold under `src/dbt_vertex_agent/`
- config loading for local development
- dbt project packaging and real GCS upload helpers
- a manifest-first review runtime that can work from local files or `gs://...` artifacts
- an ADK root agent exposed through `agent.py`
- a `deploy.py` script for Vertex AI Agent Engine deployment
- a remote Agent Engine query client for deployed-agent review runs
- a local HTTP orchestrator mode for service-oriented local development
- a direct Vertex model client for local-orchestrator mode
- debug artifacts for inspecting reduced model context and prompts
- prompt guidance configuration under `config/prompts/`
- JSON and Markdown review artifact rendering

## Install

For local scaffolding and tests:

```bash
pip install -e .
```

For Google Cloud deployment and runtime support:

```bash
pip install -e '.[gcp]'
```

Python `3.11` to `3.13` is the intended range for deployment.

## Test

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Deploy to Vertex AI Agent Engine

```bash
export DBT_VERTEX_PROJECT_ID="your-gcp-project"
export DBT_VERTEX_REGION="us-central1"
export DBT_VERTEX_STAGING_BUCKET="gs://your-staging-bucket"
python deploy.py
```

The script prints the deployed agent resource name. Set it locally before using the CLI against the deployed agent:

```bash
export DBT_VERTEX_AGENT_RESOURCE_NAME="projects/.../locations/.../reasoningEngines/..."
```

## Remaining gap

The review logic is still intentionally narrow: it derives review targets from manifest metadata and matching files in the uploaded archive, but it does not yet implement richer dbt rule evaluation. See `docs/local-development.md` for the local flow and deployment assumptions.

## Local HTTP Orchestrator Mode

This repo now also supports a local-service architecture where:

- the service runs on your machine
- the CLI acts as a local HTTP client
- orchestration stays local
- only the eventual model call is intended to go to Vertex

See `docs/local-orchestrator-mode.md` for exact startup and test commands.
