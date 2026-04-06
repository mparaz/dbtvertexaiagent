from pathlib import Path

ManifestMap = dict[str, object]


def normalize_manifest_path(raw_path: str) -> Path:
    # dbt sometimes stores patch paths in the form `package:/path/to/file.yml`.
    # Uploaded project archives use plain relative paths, so we strip the package
    # prefix and leading slash before matching against zip members.
    if ":/" in raw_path:
        _, _, remainder = raw_path.partition(":")
        raw_path = remainder.lstrip("/")

    return Path(raw_path)


def collect_review_targets(manifest: ManifestMap) -> list[Path]:
    # We keep insertion order so downstream reporting is predictable for humans,
    # but we also deduplicate because multiple manifest entries can point at
    # the same YAML file.
    targets: list[Path] = []
    seen: set[Path] = set()

    # `nodes` contains models/tests/etc and `sources` contains declared sources.
    # This is intentionally broad for now so the manifest acts as a simple harness.
    for section_name in ("nodes", "sources"):
        section = manifest.get(section_name, {})
        if not isinstance(section, dict):
            continue
        for entry in section.values():
            if not isinstance(entry, dict):
                continue
            # `original_file_path` usually points at the SQL or YAML source file.
            # `patch_path` often points at the schema YAML patch file.
            for key in ("original_file_path", "patch_path"):
                raw_path = entry.get(key)
                if not isinstance(raw_path, str) or not raw_path:
                    continue

                target = normalize_manifest_path(raw_path)
                if target not in seen:
                    targets.append(target)
                    seen.add(target)

    return targets
