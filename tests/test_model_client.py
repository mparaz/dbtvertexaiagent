import json
import unittest

from dbt_vertex_agent.integrations.vertex import (
    build_vertex_model_callback,
    parse_model_response,
)
from dbt_vertex_agent.prompts.builder import build_review_prompt
from dbt_vertex_agent.prompts.guidance import SelectedGuidance
from dbt_vertex_agent.service.contracts import ReducedReviewContext


class ParseModelResponseTests(unittest.TestCase):
    def test_parse_model_response_returns_dict_for_valid_json(self) -> None:
        payload = parse_model_response(
            '{"run_id":"run-123","status":"success","summary":"ok","findings":[],"reviewed_files":[]}'
        )

        self.assertEqual(payload["run_id"], "run-123")

    def test_parse_model_response_rejects_invalid_json(self) -> None:
        with self.assertRaisesRegex(ValueError, "valid JSON"):
            parse_model_response("not-json")


class ReducedReviewContextPromptTests(unittest.TestCase):
    def test_reduced_review_context_json_is_suitable_for_prompting(self) -> None:
        context = ReducedReviewContext(
            run_id="run-123",
            reviewed_files=["models/orders.sql"],
            manifest_summary={"target_count": 1},
            source_snippets={"models/orders.sql": "select * from orders"},
        )

        payload = json.loads(context.to_json())
        self.assertEqual(payload["manifest_summary"]["target_count"], 1)

    def test_build_review_prompt_includes_selected_guidance(self) -> None:
        context = ReducedReviewContext(
            run_id="run-123",
            reviewed_files=["models/staging/stg_orders.sql"],
            manifest_summary={"target_count": 1},
            source_snippets={"models/staging/stg_orders.sql": "select * from orders"},
            selected_guidance=["scoped/staging-guidance.md"],
        )

        prompt = build_review_prompt(
            context,
            guidance=(
                SelectedGuidance(
                    label="scoped/staging-guidance.md",
                    content="Staging guidance goes here.",
                ),
            ),
        )

        self.assertIn("Guidance: scoped/staging-guidance.md", prompt)
        self.assertIn("Staging guidance goes here.", prompt)
        self.assertIn('"selected_guidance": [', prompt)


class BuildVertexModelCallbackTests(unittest.TestCase):
    def test_build_vertex_model_callback_returns_structured_payload(self) -> None:
        captured = {}

        class FakeResponse:
            text = json.dumps(
                {
                    "run_id": "run-123",
                    "status": "warning",
                    "summary": "1 finding detected.",
                    "findings": [
                        {
                            "severity": "warning",
                            "rule": "llm-review",
                            "message": "Example finding.",
                            "file_path": "models/orders.sql",
                        }
                    ],
                    "reviewed_files": ["models/orders.sql"],
                }
            )

        class FakeModels:
            def generate_content(self, *, model, contents, config):
                captured["model"] = model
                captured["contents"] = contents
                captured["config"] = config
                return FakeResponse()

        class FakeClient:
            def __init__(self, **kwargs):
                captured["client_kwargs"] = kwargs
                self.models = FakeModels()

            def close(self) -> None:
                captured["closed"] = True

        class FakeGenaiModule:
            Client = FakeClient

        class FakeTypesModule:
            class HttpOptions:
                def __init__(self, *, api_version):
                    self.api_version = api_version

        context = ReducedReviewContext(
            run_id="run-123",
            reviewed_files=["models/orders.sql"],
            manifest_summary={"target_count": 1},
            source_snippets={"models/orders.sql": "select * from orders"},
        )

        callback = build_vertex_model_callback(
            project_id="test-project",
            region="us-central1",
            model_name="gemini-2.5-flash",
            modules_factory=lambda: (FakeGenaiModule, FakeTypesModule),
        )

        payload = callback(context)

        self.assertEqual(payload["run_id"], "run-123")
        self.assertEqual(captured["client_kwargs"]["project"], "test-project")
        self.assertEqual(captured["client_kwargs"]["location"], "us-central1")
        self.assertTrue(captured["client_kwargs"]["vertexai"])
        self.assertEqual(captured["client_kwargs"]["http_options"].api_version, "v1")
        self.assertEqual(captured["model"], "gemini-2.5-flash")
        self.assertIn("run-123", captured["contents"])
        self.assertEqual(
            captured["config"]["response_mime_type"],
            "application/json",
        )
        self.assertTrue(captured["closed"])
