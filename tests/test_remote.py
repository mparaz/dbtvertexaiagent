import unittest

from dbt_vertex_agent.models import SubmissionArtifacts
from dbt_vertex_agent.remote import extract_final_text, run_remote_review


class ExtractFinalTextTests(unittest.TestCase):
    def test_extract_final_text_returns_first_non_tool_text_part(self) -> None:
        events = [
            {
                "content": {
                    "parts": [
                        {
                            "function_call": {
                                "name": "review_dbt_submission",
                                "args": {"project_uri": "gs://bucket/project.zip"},
                            }
                        }
                    ]
                }
            },
            {
                "content": {
                    "parts": [
                        {
                            "text": "{\"run_id\": \"run-123\", \"status\": \"success\"}"
                        }
                    ]
                }
            },
        ]

        self.assertEqual(
            extract_final_text(events),
            "{\"run_id\": \"run-123\", \"status\": \"success\"}",
        )


class RunRemoteReviewTests(unittest.TestCase):
    def test_run_remote_review_queries_remote_app_with_submission_uris(self) -> None:
        class FakeRemoteApp:
            async def async_create_session(self, user_id: str) -> dict:
                return {"id": "session-123", "user_id": user_id}

            async def async_stream_query(self, user_id: str, session_id: str, message: str):
                yield {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    "{\"run_id\": \"run-123\", "
                                    "\"status\": \"success\", "
                                    "\"summary\": \"No findings detected.\", "
                                    "\"findings\": [], "
                                    "\"reviewed_files\": [\"models/orders.sql\"]}"
                                )
                            }
                        ]
                    }
                }

        submission = SubmissionArtifacts(
            run_id="run-123",
            project_uri="gs://bucket/submissions/run-123/project.zip",
            manifest_uri="gs://bucket/submissions/run-123/manifest.json",
        )

        result = run_remote_review("projects/123/locations/us-central1/reasoningEngines/456", submission, app=FakeRemoteApp())

        self.assertEqual(result.run_id, "run-123")
        self.assertEqual(result.reviewed_files, ["models/orders.sql"])
