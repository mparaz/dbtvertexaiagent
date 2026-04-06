from collections.abc import Callable
from pathlib import Path

from dbt_vertex_agent.review.contracts import Finding, ReviewResult

ManifestMap = dict[str, object]
ManifestRule = Callable[[ManifestMap], list[Finding]]


def rule_missing_model_description(manifest: ManifestMap) -> list[Finding]:
    findings: list[Finding] = []

    nodes = manifest.get("nodes", {})
    if not isinstance(nodes, dict):
        return findings

    for node in nodes.values():
        if not isinstance(node, dict):
            continue
        if node.get("resource_type") != "model":
            continue

        description = (node.get("description") or "").strip()
        if not description:
            file_path = node.get("original_file_path") or "unknown"
            findings.append(
                Finding(
                    severity="warning",
                    rule="missing-description",
                    message="Model is missing a description in the manifest metadata.",
                    file_path=file_path,
                )
            )

    return findings


def rule_missing_column_description(manifest: ManifestMap) -> list[Finding]:
    findings: list[Finding] = []

    nodes = manifest.get("nodes", {})
    if not isinstance(nodes, dict):
        return findings

    for node in nodes.values():
        if not isinstance(node, dict):
            continue
        if node.get("resource_type") != "model":
            continue

        columns = node.get("columns") or {}
        if not isinstance(columns, dict):
            continue

        for column_name, column in columns.items():
            if not isinstance(column_name, str) or not isinstance(column, dict):
                continue
            column_description = (column.get("description") or "").strip()
            if column_description:
                continue

            file_path = node.get("original_file_path") or "unknown"
            findings.append(
                Finding(
                    severity="warning",
                    rule="missing-column-description",
                    message=(
                        f"Column `{column_name}` is missing a description in the manifest metadata."
                    ),
                    file_path=file_path,
                )
            )

    return findings


# Future manifest-based deterministic checks belong in this registry. Keep each
# rule as a plain function returning `Finding` objects so the behavior stays
# easy to test and reason about.
MANIFEST_RULES: tuple[ManifestRule, ...] = (
    rule_missing_model_description,
    rule_missing_column_description,
)


def collect_manifest_findings(manifest: ManifestMap) -> list[Finding]:
    findings: list[Finding] = []
    for rule in MANIFEST_RULES:
        findings.extend(rule(manifest))
    return findings


def build_review_result(
    run_id: str,
    review_targets: list[Path],
    reviewed_files: list[str],
    manifest: ManifestMap | None = None,
) -> ReviewResult:
    # This function translates raw review evidence into user-facing findings.
    # Keeping it separate from the archive/manifest plumbing makes the code easier
    # to grow into a richer policy engine later.
    findings: list[Finding] = []

    target_names = {target.as_posix() for target in review_targets}
    reviewed_names = set(reviewed_files)

    # An empty target set is not a hard failure, but it is still useful feedback.
    if not review_targets:
        findings.append(
            Finding(
                severity="info",
                rule="no-review-targets",
                message="Manifest did not produce any review targets.",
                file_path="manifest.json",
            )
        )

    # Any target mentioned by the manifest but missing from the uploaded archive
    # becomes a warning because the agent cannot inspect a file that is not there.
    missing_targets = sorted(target_names - reviewed_names)
    for missing_target in missing_targets:
        findings.append(
            Finding(
                severity="warning",
                rule="missing-reviewed-file",
                message=(
                    "Manifest referenced a file that was not found in the uploaded project archive."
                ),
                file_path=missing_target,
            )
        )

    if manifest is not None:
        findings.extend(collect_manifest_findings(manifest))

    # The result status is currently severity-driven:
    # warnings downgrade the overall run to "warning", while informational notes do not.
    status = "success"
    summary = "No findings detected."
    if findings:
        status = (
            "warning" if any(finding.severity == "warning" for finding in findings) else "success"
        )
        summary = f"{len(findings)} finding(s) detected."

    return ReviewResult(
        run_id=run_id,
        status=status,
        summary=summary,
        findings=findings,
        reviewed_files=reviewed_files,
    )
