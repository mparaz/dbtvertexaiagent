import tempfile
import unittest
from pathlib import Path

from dbt_vertex_agent.prompts.guidance import (
    GlobalGuidanceConfig,
    ScopedGuidanceRule,
    build_selected_guidance,
    load_prompt_guidance_config,
)


class LoadPromptGuidanceConfigTests(unittest.TestCase):
    def test_loads_global_and_scoped_guidance_from_config_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_root = Path(tmp_dir) / "config" / "prompts"
            global_dir = config_root / "global"
            scoped_dir = config_root / "scoped"
            global_dir.mkdir(parents=True)
            scoped_dir.mkdir(parents=True)

            (global_dir / "base.md").write_text("Base guidance\n")
            (scoped_dir / "staging.md").write_text("Staging guidance\n")
            (config_root / "scoped_rules.json").write_text(
                """
[
  {
    "selector": {"kind": "glob", "pattern": "models/staging/**"},
    "guidance_files": ["scoped/staging.md"]
  }
]
""".strip()
            )

            config = load_prompt_guidance_config(config_root)

            self.assertEqual(
                config.global_guidance,
                (GlobalGuidanceConfig(path="global/base.md", content="Base guidance\n"),),
            )
            self.assertEqual(
                config.scoped_rules,
                (
                    ScopedGuidanceRule(
                        selector_kind="glob",
                        selector_value="models/staging/**",
                        guidance_paths=("scoped/staging.md",),
                    ),
                ),
            )


class BuildSelectedGuidanceTests(unittest.TestCase):
    def test_includes_global_guidance_and_matching_scoped_guidance(self) -> None:
        config = load_prompt_guidance_config(Path("config/prompts"))

        selected = build_selected_guidance(
            config=config,
            reviewed_files=["models/staging/stg_orders.sql"],
        )

        labels = [item.label for item in selected]
        self.assertIn("global/base.md", labels)
        self.assertIn("scoped/staging-guidance.md", labels)

    def test_deduplicates_scoped_guidance_when_multiple_files_match_same_rule(self) -> None:
        config = load_prompt_guidance_config(Path("config/prompts"))

        selected = build_selected_guidance(
            config=config,
            reviewed_files=[
                "models/staging/stg_orders.sql",
                "models/staging/stg_customers.sql",
            ],
        )

        labels = [item.label for item in selected]
        self.assertEqual(labels.count("scoped/staging-guidance.md"), 1)

    def test_returns_only_global_guidance_when_no_scoped_rules_match(self) -> None:
        config = load_prompt_guidance_config(Path("config/prompts"))

        selected = build_selected_guidance(
            config=config,
            reviewed_files=["models/orders.sql"],
        )

        labels = [item.label for item in selected]
        self.assertIn("global/base.md", labels)
        self.assertNotIn("scoped/staging-guidance.md", labels)
