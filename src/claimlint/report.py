from __future__ import annotations

import json

from .model import SEVERITIES, ScanResult


def fails(result: ScanResult, minimum: str) -> bool:
    return any(SEVERITIES[f.severity] >= SEVERITIES[minimum] for f in result.findings)


def _escape(value: str, property: bool = False) -> str:
    value = value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    return value.replace(":", "%3A").replace(",", "%2C") if property else value


def render(result: ScanResult, format: str = "text", annotation_prefix: str = "") -> str:
    if format == "json":
        return json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n"
    if format == "github":
        severity = {"note": "notice", "warning": "warning", "error": "error"}
        return (
            "\n".join(
                f"::{severity[f.severity]} file={_escape(annotation_prefix + f.doc_file, True)},"
                f"line={f.doc_line},"
                f"title={f.check}::{_escape(f.message)}"
                for f in result.findings
            )
            + "\n"
        )
    lines = [f"claimlint: scanned {len(result.documents)} Markdown document(s)"]
    for f in result.findings:
        lines.append(f"{f.doc_file}:{f.doc_line}: {f.severity} {f.check} {f.message}")
        if f.code_ref:
            lines.append(f"  source: {f.code_ref}")
        lines.append(f"  evidence: {json.dumps(f.evidence, ensure_ascii=False, sort_keys=True)}")
        if f.suggestion:
            lines.append(f"  suggestion: {f.suggestion}")
    lines.append(
        f"{len(result.findings)} finding(s); {result.baseline_count} baseline finding(s) hidden."
    )
    for key, stats in result.coverage.items():
        lines.append(f"{key}: {stats.checked} claim(s) checked, {len(stats.skipped)} skipped")
        for skip in stats.skipped:
            where = f"{skip['file']}:{skip['line']}: " if "file" in skip else ""
            lines.append(f"  skipped: {where}{skip['reason']}")
    return "\n".join(lines) + "\n"
