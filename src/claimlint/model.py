from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

CHECKS = {f"DP{i:03}" for i in range(1, 8)}
SEVERITIES = {"note": 0, "warning": 1, "error": 2}


@dataclass(frozen=True)
class Claim:
    file: str
    line: int
    kind: str
    text: str
    language: str = ""
    target: str = ""
    ignored: frozenset[str] = frozenset()
    skip: bool = False


@dataclass(frozen=True)
class Finding:
    check: str
    severity: str
    doc_file: str
    doc_line: int
    message: str
    evidence: dict[str, Any]
    code_ref: str | None = None
    suggestion: str | None = None

    @property
    def id(self) -> str:
        # Line numbers intentionally excluded: adding a paragraph should not reset a baseline.
        identity = [self.check, self.doc_file, self.evidence.get("claim"), self.message]
        digest = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16]
        return f"{self.check}-{digest}"

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, **asdict(self)}


@dataclass
class Coverage:
    checked: int = 0
    skipped: list[dict[str, Any]] = field(default_factory=list)

    def skip(self, reason: str, claim: Claim | None = None) -> None:
        item: dict[str, Any] = {"reason": reason}
        if claim is not None:
            item.update(file=claim.file, line=claim.line, claim=claim.text)
        if item not in self.skipped:
            self.skipped.append(item)


@dataclass
class ScanResult:
    findings: list[Finding]
    coverage: dict[str, Coverage]
    documents: list[str]
    baseline_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "documents": self.documents,
            "findings": [f.to_dict() for f in self.findings],
            "coverage": {key: asdict(value) for key, value in self.coverage.items()},
            "baseline_count": self.baseline_count,
        }
