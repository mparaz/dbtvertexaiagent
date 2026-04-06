import json
from collections.abc import Callable
from typing import Any

from dbt_vertex_agent.prompts.builder import build_review_prompt
from dbt_vertex_agent.service.contracts import ReducedReviewContext

JsonObject = dict[str, object]


def get_google_genai_modules() -> tuple[Any, Any]:
    # The direct local-to-Vertex path uses the newer Gen AI SDK rather than the
    # older Vertex-specific wrapper. Keeping this import lazy means tests and
    # purely local deterministic review can run without Google packages installed.
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("google-genai is required for direct Vertex model calls.") from exc

    return genai, types


def get_vertexai_module() -> Any:
    try:
        import vertexai
    except ImportError as exc:
        raise RuntimeError("vertexai is required for direct remote model calls.") from exc

    return vertexai


def parse_model_response(text: str) -> JsonObject:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("Model response must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Model response must be a JSON object.")
    return payload


def build_review_response_schema() -> JsonObject:
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
    modules_factory: Callable[[], tuple[Any, Any]] = get_google_genai_modules,
) -> Callable[[ReducedReviewContext], JsonObject]:
    # The returned callable matches the service handler's simple callback
    # contract, which keeps the HTTP layer unaware of any SDK details.
    def callback(context: ReducedReviewContext) -> JsonObject:
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
