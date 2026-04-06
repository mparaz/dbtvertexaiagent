import unittest

from dbt_vertex_agent.review.policy import (
    MANIFEST_RULES,
    collect_manifest_findings,
    rule_missing_column_description,
    rule_missing_model_description,
)


class ManifestRuleRegistryTests(unittest.TestCase):
    def test_registry_contains_current_manifest_rules(self) -> None:
        self.assertEqual(
            MANIFEST_RULES,
            (
                rule_missing_model_description,
                rule_missing_column_description,
            ),
        )

    def test_collect_manifest_findings_runs_registered_rules(self) -> None:
        manifest = {
            "nodes": {
                "model.project.orders": {
                    "resource_type": "model",
                    "original_file_path": "models/orders.sql",
                    "description": "",
                    "columns": {
                        "order_id": {
                            "name": "order_id",
                            "description": "",
                        }
                    },
                }
            }
        }

        findings = collect_manifest_findings(manifest)

        self.assertEqual(
            [finding.rule for finding in findings],
            ["missing-description", "missing-column-description"],
        )
