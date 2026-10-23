from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from ..model import Claim, Coverage, Finding


def check(claims: list[Claim], root: Path, coverage: Coverage, timeout: float) -> list[Finding]:
    findings = []
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(root / "src"), str(root), env.get("PYTHONPATH", "")])
    for claim in claims:
        if claim.kind != "code" or claim.language not in {"python", "py", "python3"}:
            continue
        coverage.checked += 1
        # A temporary cwd prevents relative writes to the repo. It is NOT a sandbox.
        with tempfile.TemporaryDirectory(prefix="claimlint-example-") as directory:
            script = Path(directory) / "example.py"
            script.write_text(claim.text, encoding="utf-8")
            try:
                proc = subprocess.run(
                    [sys.executable, str(script)],
                    cwd=directory,
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                findings.append(
                    Finding(
                        "DP004",
                        "error",
                        claim.file,
                        claim.line,
                        f"Example timed out after {timeout:g}s",
                        {"claim": claim.text, "category": "Timeout", "timeout": timeout},
                    )
                )
                continue
            if proc.returncode:
                error = proc.stderr[-4000:].replace(str(script), f"{claim.file}:example")
                match = re.search(r"^(\w*(?:Error|Exception)):", error, re.M)
                category = match[1] if match else "Other"
                if category == "ModuleNotFoundError":
                    category = "ImportError"
                findings.append(
                    Finding(
                        "DP004",
                        "error",
                        claim.file,
                        claim.line,
                        f"Example failed ({category}), exit {proc.returncode}",
                        {"claim": claim.text, "category": category, "stderr": error},
                    )
                )
    return findings
