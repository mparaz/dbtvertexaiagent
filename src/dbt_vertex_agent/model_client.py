import json

from dbt_vertex_agent.prompting import build_review_prompt
from dbt_vertex_agent.service_contract import ReducedReviewContext


def get_google_genai_modules():
    # The direct local-to-Vertex path uses the newer Gen AI SDK rather than the
    # older Vertex-specific wrapper. Keeping this import lazy means tests and
    # purely local deterministic review can run without Google packages installed.
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError(
            "google-genai is required for direct Vertex model calls."
        ) from exc

    return genai, types


def get_vertexai_module():
    try:
        import vertexai
    except ImportError as exc:
        raise RuntimeError(
            "vertexai is required for direct remote model calls."
        ) from exc

    return vertexai


def parse_model_response(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Model response must be valid JSON.") from exc


def build_review_response_schema() -> dict:
    # Structured output keeps the model response inside the same contract used by
    # the deterministic rule engine and the remote Agent Engine path.
    return {
        "type": "OBJECT",
        "properties": {
            "run_id": {"type": "STRING"},
            "status": {"type": "STRING"},
            "summary": {"type": "STRING"},
            "findings": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "severity": {"type": "STRING"},
                        "rule": {"type": "STRING"},
                        "message": {"type": "STRING"},
                        "file_path": {"type": "STRING"},
                    },
                    "required": ["severity", "rule", "message", "file_path"],
                },
            },
            "reviewed_files": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
            },
        },
        "required": ["run_id", "status", "summary", "findings", "reviewed_files"],
    }


def build_vertex_model_callback(
    project_id: str,
    region: str,
    model_name: str,
    modules_factory=get_google_genai_modules,
):
    # The returned callable matches the service handler's simple callback
    # contract, which keeps the HTTP layer unaware of any SDK details.
    def callback(context: ReducedReviewContext) -> dict:
        genai, types = modules_factory()
        client = genai.Client(
            vertexai=True,
            project=project_id,
            location=region,
            http_options=types.HttpOptions(api_version="v1"),
        )
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=build_review_prompt(context),
                config={
                    "response_mime_type": "application/json",
                    "response_schema": build_review_response_schema(),
                },
            )
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()

        return parse_model_response(response.text)

    return callback
