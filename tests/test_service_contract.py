import json
import unittest

from dbt_vertex_agent.service_contract import DebugArtifacts, LocalServiceRequest, ReducedReviewContext


class LocalServiceRequestTests(unittest.TestCase):
    def test_to_dict_serializes_request_metadata(self) -> None:
        request = LocalServiceRequest(
            run_id="run-123",
            project_filename="project.zip",
            manifest_filename="manifest.json",
        )

        self.assertEqual(
            request.to_dict(),
            {
                "run_id": "run-123",
                "project_filename": "project.zip",
                "manifest_filename": "manifest.json",
            },
        )


class ReducedReviewContextTests(unittest.TestCase):
    def test_to_json_serializes_review_context(self) -> None:
        context = ReducedReviewContext(
            run_id="run-123",
            reviewed_files=["models/orders.sql"],
            manifest_summary={"target_count": 1},
            source_snippets={"models/orders.sql": "select * from orders"},
        )

        payload = json.loads(context.to_json())

        self.assertEqual(payload["run_id"], "run-123")
        self.assertEqual(payload["reviewed_files"], ["models/orders.sql"])
        self.assertEqual(payload["manifest_summary"], {"target_count": 1})
        self.assertEqual(
            payload["source_snippets"],
            {"models/orders.sql": "select * from orders"},
        )


class DebugArtifactsTests(unittest.TestCase):
    def test_to_dict_serializes_prompt_and_context(self) -> None:
        artifacts = DebugArtifacts(
            context=ReducedReviewContext(
                run_id="run-123",
                reviewed_files=["models/orders.sql"],
                manifest_summary={"target_count": 1},
                source_snippets={"models/orders.sql": "select * from orders"},
            ),
            prompt="Review this dbt model.",
        )

        payload = artifacts.to_dict()

        self.assertEqual(payload["context"]["run_id"], "run-123")
        self.assertEqual(payload["prompt"], "Review this dbt model.")
