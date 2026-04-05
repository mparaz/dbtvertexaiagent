# Local Orchestrator Mode

This mode is for learning the architecture where:

- a local HTTP service performs orchestration
- the CLI uploads artifacts to that service
- only model inference is intended to leave the machine

## 1. Authenticate to Google Cloud

```bash
gcloud init
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

## 2. Set environment variables

```bash
export DBT_VERTEX_PROJECT_ID="your-project-id"
export DBT_VERTEX_REGION="us-central1"
export DBT_VERTEX_STAGING_BUCKET="gs://unused-in-local-http-mode-for-now"
export DBT_VERTEX_OUTPUT_DIR="runs"
export DBT_VERTEX_LOCAL_SERVICE_URL="http://127.0.0.1:8000"
export DBT_VERTEX_MODEL="gemini-2.5-flash"
export DBT_VERTEX_DEBUG="true"
```

`DBT_VERTEX_STAGING_BUCKET` is still required by current config loading even though the local HTTP path does not use GCS uploads.
`DBT_VERTEX_MODEL` is optional. If you omit it, the service falls back to deterministic local review rules only.
`DBT_VERTEX_DEBUG` is optional. If you set it, the local service writes `context.json` and `prompt.txt` beside the normal review artifacts for every run it handles.

## 3. Start the local service

From the repo root:

```bash
PYTHONPATH=src python3 -m dbt_vertex_agent serve --host 127.0.0.1 --port 8000
```

## 4. Check service health

In another terminal:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status": "ok"}
```

## 5. Prepare a sample dbt submission

From a dbt project directory:

```bash
zip -r project.zip models macros seeds snapshots tests dbt_project.yml packages.yml
```

If your project does not have all of those directories, include only the ones that exist.

Your manifest should typically be at:

```bash
target/manifest.json
```

## 6. Test the local service directly with curl

```bash
curl -X POST http://127.0.0.1:8000/review \
  -F "project=@project.zip;type=application/zip" \
  -F "manifest=@target/manifest.json;type=application/json" \
  -F "debug=true"
```

Expected behavior today:

- the service returns JSON
- the response includes `run_id`, `status`, `summary`, `findings`, and `reviewed_files`
- if `DBT_VERTEX_MODEL` is set, the service sends reduced context to Vertex and returns the model-shaped review
- if `DBT_VERTEX_MODEL` is not set, the service falls back to deterministic local review logic
- if debug mode is enabled, the run directory also contains `context.json` and `prompt.txt`

## 7. Run the CLI against the local service

```bash
PYTHONPATH=src python3 -m dbt_vertex_agent review \
  --project /path/to/dbt-project \
  --manifest /path/to/dbt-project/target/manifest.json \
  --local-service-url http://127.0.0.1:8000 \
  --debug
```

Expected behavior today:

- the CLI creates a local zip artifact
- the CLI uses the local-service mode path
- the CLI writes JSON and Markdown outputs under `runs/`
- the CLI posts the zip and manifest to the local service over HTTP
- `--debug` tells the local service to persist `context.json` and `prompt.txt` for that run

## Current status of this mode

What works now:

- service startup
- health endpoint
- direct `curl` review endpoint
- CLI awareness of local-service mode
- full CLI-to-local-service HTTP upload
- local deterministic review response generation
- opt-in direct Vertex model inference for local-service mode
- debug artifact capture for reduced context and rendered prompts

What is still incomplete:

- richer context reduction and dbt review policy
- deployment parity beyond the local-orchestrator path

## 8. End-to-end commands

Start the service with Vertex enabled:

```bash
export DBT_VERTEX_PROJECT_ID="your-project-id"
export DBT_VERTEX_REGION="us-central1"
export DBT_VERTEX_MODEL="gemini-2.5-flash"
export DBT_VERTEX_DEBUG="true"
PYTHONPATH=src python3 -m dbt_vertex_agent serve --host 127.0.0.1 --port 8000
```

In another terminal, run the CLI against it:

```bash
export DBT_VERTEX_PROJECT_ID="your-project-id"
export DBT_VERTEX_REGION="us-central1"
export DBT_VERTEX_STAGING_BUCKET="gs://unused-in-local-http-mode-for-now"
PYTHONPATH=src python3 -m dbt_vertex_agent review \
  --project /path/to/dbt-project \
  --manifest /path/to/dbt-project/target/manifest.json \
  --local-service-url http://127.0.0.1:8000 \
  --debug
```

The CLI prints the Markdown artifact path for the run. The matching JSON artifact is written beside it under `runs/`. When debug mode is enabled, the same run directory also contains `context.json` and `prompt.txt`.

## 9. Adding deterministic rules later

The deterministic manifest checks now run through a small registry in `src/dbt_vertex_agent/review_policy.py`.

To add a new rule later:

1. Add a plain function that accepts `manifest: dict` and returns `list[Finding]`.
2. Keep the rule focused on one concern.
3. Register it in `MANIFEST_RULES`.
4. Add a test proving the rule’s findings and that the existing summary/status behavior remains correct.

Current example shape:

```python
def rule_missing_model_description(manifest: dict) -> list[Finding]:
    findings: list[Finding] = []
    ...
    return findings


MANIFEST_RULES: tuple[ManifestRule, ...] = (
    rule_missing_model_description,
    rule_missing_column_description,
)
```

## 10. Adding prompt guidance later

Prompt-shaping Markdown files now live under `config/prompts/`.

Current structure:

```text
config/prompts/
  global/
    base.md
  scoped/
    staging-guidance.md
  scoped_rules.json
```

How it works:

1. Every run includes the Markdown files in `config/prompts/global/`.
2. The service then checks reviewed file paths against the glob rules in `config/prompts/scoped_rules.json`.
3. Matching scoped Markdown files are added to the rendered prompt.
4. Debug mode makes the final combined prompt visible in `prompt.txt`.

To add new prompt guidance:

1. Add a Markdown file under `config/prompts/global/` if it should always apply.
2. Add a Markdown file under `config/prompts/scoped/` if it should apply only for some reviewed files.
3. Add a `glob` rule in `config/prompts/scoped_rules.json` pointing to that scoped file.
4. Add or update tests proving the expected prompt guidance is selected.

Example scoped rule:

```json
[
  {
    "selector": {
      "kind": "glob",
      "pattern": "models/staging/**"
    },
    "guidance_files": [
      "scoped/staging-guidance.md"
    ]
  }
]
```

Future selector types can be added later, but v1 only supports `glob` against reviewed file paths.
