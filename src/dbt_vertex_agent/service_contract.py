from dataclasses import asdict, dataclass
import json


@dataclass(frozen=True)
class LocalServiceRequest:
    # Metadata describing one multipart request received by the local orchestrator.
    run_id: str
    project_filename: str
    manifest_filename: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ReducedReviewContext:
    # Compact local context that will be sent to the remote model instead of
    # forwarding the raw manifest or full project bundle.
    run_id: str
    reviewed_files: list[str]
    manifest_summary: dict
    source_snippets: dict[str, str]
    selected_guidance: list[str] | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class DebugArtifacts:
    # Debug mode keeps the model-facing evidence in a compact, serializable
    # object so it can be written beside the normal review artifacts.
    context: ReducedReviewContext
    prompt: str

    def to_dict(self) -> dict:
        return {
            "context": self.context.to_dict(),
            "prompt": self.prompt,
        }
