from dataclasses import dataclass
import json
from fnmatch import fnmatch
from pathlib import Path


@dataclass(frozen=True)
class GlobalGuidanceConfig:
    path: str
    content: str


@dataclass(frozen=True)
class ScopedGuidanceRule:
    selector_kind: str
    selector_value: str
    guidance_paths: tuple[str, ...]


@dataclass(frozen=True)
class PromptGuidanceConfig:
    global_guidance: tuple[GlobalGuidanceConfig, ...]
    scoped_rules: tuple[ScopedGuidanceRule, ...]
    root: Path


@dataclass(frozen=True)
class SelectedGuidance:
    label: str
    content: str


def load_prompt_guidance_config(config_root: Path) -> PromptGuidanceConfig:
    global_dir = config_root / "global"
    global_guidance = tuple(
        GlobalGuidanceConfig(
            path=str(path.relative_to(config_root)),
            content=path.read_text(),
        )
        for path in sorted(global_dir.glob("*.md"))
    )

    rules_path = config_root / "scoped_rules.json"
    rules_payload = json.loads(rules_path.read_text()) if rules_path.exists() else []
    scoped_rules = tuple(
        ScopedGuidanceRule(
            selector_kind=item["selector"]["kind"],
            selector_value=item["selector"]["pattern"],
            guidance_paths=tuple(item["guidance_files"]),
        )
        for item in rules_payload
    )

    return PromptGuidanceConfig(
        global_guidance=global_guidance,
        scoped_rules=scoped_rules,
        root=config_root,
    )


def build_selected_guidance(
    config: PromptGuidanceConfig,
    reviewed_files: list[str],
) -> tuple[SelectedGuidance, ...]:
    selected: list[SelectedGuidance] = [
        SelectedGuidance(label=item.path, content=item.content)
        for item in config.global_guidance
    ]
    selected_labels = {item.label for item in selected}

    for rule in config.scoped_rules:
        if rule.selector_kind != "glob":
            continue
        if not any(fnmatch(path, rule.selector_value) for path in reviewed_files):
            continue

        for guidance_path in rule.guidance_paths:
            if guidance_path in selected_labels:
                continue
            selected.append(
                SelectedGuidance(
                    label=guidance_path,
                    content=(config.root / guidance_path).read_text(),
                )
            )
            selected_labels.add(guidance_path)

    return tuple(selected)
