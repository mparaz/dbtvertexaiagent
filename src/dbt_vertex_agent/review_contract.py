from dataclasses import asdict, dataclass, field


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

    def to_dict(self) -> dict:
        # Dataclasses are convenient in Python; dictionaries are convenient at boundaries.
        return asdict(self)

    @classmethod
    def from_model_payload(cls, payload: dict) -> "ReviewResult":
        required_keys = {"run_id", "status", "summary", "findings", "reviewed_files"}
        missing_keys = sorted(required_keys - payload.keys())
        if missing_keys:
            raise ValueError(f"Model payload missing required keys: {', '.join(missing_keys)}")

        findings = [
            Finding(
                severity=item["severity"],
                rule=item["rule"],
                message=item["message"],
                file_path=item["file_path"],
            )
            for item in payload["findings"]
        ]

        return cls(
            run_id=payload["run_id"],
            status=payload["status"],
            summary=payload["summary"],
            findings=findings,
            reviewed_files=payload["reviewed_files"],
        )
