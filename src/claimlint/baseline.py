from __future__ import annotations

import json
from pathlib import Path

from .model import ScanResult


def write_baseline(path: Path, result: ScanResult) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "findings": [
                    {"id": f.id, "check": f.check, "doc_file": f.doc_file, "message": f.message}
                    for f in result.findings
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def apply_baseline(path: Path, result: ScanResult) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(data, dict)
        or data.get("schema_version") != 1
        or not isinstance(data.get("findings"), list)
    ):
        raise ValueError("Unsupported baseline format; regenerate it with claimlint baseline")
    if any(not isinstance(f, dict) or not isinstance(f.get("id"), str) for f in data["findings"]):
        raise ValueError("Baseline findings must contain string IDs")
    ids = {finding["id"] for finding in data["findings"]}
    visible = [f for f in result.findings if f.id not in ids]
    result.baseline_count = len(result.findings) - len(visible)
    result.findings = visible
