# Local Development

## Intended GCP setup

The local development flow assumes:

- a Google Cloud project is available
- a supported Vertex AI Agent Engine region is chosen
- a GCS bucket exists for submission artifacts
- Application Default Credentials are configured locally

## Suggested environment variables

Set these before running the CLI:

```bash
export DBT_VERTEX_PROJECT_ID="your-gcp-project"
export DBT_VERTEX_REGION="us-central1"
export DBT_VERTEX_STAGING_BUCKET="gs://your-staging-bucket"
export DBT_VERTEX_OUTPUT_DIR="runs"
```

## Authentication

For local development, use Application Default Credentials:

```bash
gcloud auth application-default login
```

## Expected review flow

1. Point the CLI at a dbt project root and a `manifest.json` path.
2. Package the project into `project.zip`.
3. Upload `project.zip` and `manifest.json` to:
   - `submissions/<run-id>/project.zip`
   - `submissions/<run-id>/manifest.json`
4. Invoke the Vertex AI review agent with those artifact URIs.
5. Save local review outputs under `runs/<run-id>/`.

## Current limitation

The repository now includes real GCS upload helpers, a deployable ADK root agent, and a remote Agent Engine client path. The main remaining limitation is review depth: the deployed agent currently returns a structured manifest-first review result, but the actual dbt quality policy is still minimal and should be expanded before production use.

For the service-oriented local mode, use `docs/local-orchestrator-mode.md`.
