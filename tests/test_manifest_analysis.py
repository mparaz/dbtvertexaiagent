import json
import tempfile
import unittest
from pathlib import Path

from dbt_vertex_agent.manifest_analysis import collect_review_targets


class CollectReviewTargetsTests(unittest.TestCase):
    def test_collect_review_targets_returns_model_and_schema_files(self) -> None:
        manifest = {
            "nodes": {
                "model.project.orders": {
                    "resource_type": "model",
                    "original_file_path": "models/orders.sql",
                    "patch_path": "models/schema.yml",
                }
            },
            "sources": {
                "source.project.raw_orders": {
                    "resource_type": "source",
                    "original_file_path": "models/schema.yml",
                }
            },
        }

        targets = collect_review_targets(manifest)

        self.assertEqual(
            targets,
            [
                Path("models/orders.sql"),
                Path("models/schema.yml"),
            ],
        )

    def test_collect_review_targets_handles_missing_optional_sections(self) -> None:
        self.assertEqual(collect_review_targets({"nodes": {}}), [])

    def test_collect_review_targets_normalizes_dbt_patch_paths(self) -> None:
        manifest = {
            "nodes": {
                "model.project.orders": {
                    "resource_type": "model",
                    "patch_path": "jaffle_shop:/models/schema.yml",
                }
            }
        }

        targets = collect_review_targets(manifest)

        self.assertEqual(targets, [Path("models/schema.yml")])
