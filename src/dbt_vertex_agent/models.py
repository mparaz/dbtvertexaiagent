from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReviewRequest:
    # This object describes everything needed before a run is submitted.
    project_path: Path
    manifest_path: Path
    project_id: str
    region: str
    staging_bucket: str
    output_dir: Path


@dataclass(frozen=True)
class SubmissionArtifacts:
    # After submission, local paths become storage URIs plus a run identifier.
    # The run ID is the thread that ties uploads, remote review, and local outputs together.
    run_id: str
    project_uri: str
    manifest_uri: str
