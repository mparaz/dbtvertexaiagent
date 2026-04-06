from dataclasses import asdict, dataclass, field

JsonObject = dict[str, object]


@dataclass(frozen=True)
class Finding:
    # A finding is the smallest review outcome we can report.
    # It is intentionally simple so it can be returned from the local runtime,
    # the remote agent, or future rule engines without translation pain.
    severity: str
    rule: str
    message: str
    file_path: str


@dataclass(frozen=True)
class ReviewResult:
    # This is the top-level contract shared across the whole project.
    run_id: str
    findings: list[Finding]
    status: str = "success"
    summary: str = "No findings detected."
    reviewed_files: list[str] = field(default_factory=list)

    def to_dict(self) -> JsonObject:
        # Dataclasses are convenient in Python; dictionaries are convenient at boundaries.
        return asdict(self)

    @classmethod
    def from_model_payload(cls, payload: JsonObject) -> "ReviewResult":
        required_keys = {"run_id", "status", "summary", "findings", "reviewed_files"}
        missing_keys = sorted(required_keys - payload.keys())
        if missing_keys:
            raise ValueError(f"Model payload missing required keys: {', '.join(missing_keys)}")

        findings_payload = payload["findings"]
        if not isinstance(findings_payload, list):
            raise ValueError("Model payload 'findings' must be a list.")

        findings = [
            Finding(
                severity=item["severity"],
                rule=item["rule"],
                message=item["message"],
                file_path=item["file_path"],
            )
            for item in findings_payload
            if isinstance(item, dict)
        ]

        run_id = payload["run_id"]
        status = payload["status"]
        summary = payload["summary"]
        reviewed_files = payload["reviewed_files"]
        if (
            not isinstance(run_id, str)
            or not isinstance(status, str)
            or not isinstance(summary, str)
            or not isinstance(reviewed_files, list)
        ):
            raise ValueError("Model payload contains invalid field types.")

        return cls(
            run_id=run_id,
            status=status,
            summary=summary,
            findings=findings,
            reviewed_files=[str(item) for item in reviewed_files],
        )
