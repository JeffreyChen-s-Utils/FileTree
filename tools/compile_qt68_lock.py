"""Resolve the Qt 6.8 compatibility lock without upgrading other locked test dependencies."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PIN = re.compile(r"^([A-Za-z0-9][\w.-]*)==")


def base_constraints(text: str) -> str:
    """Keep regular test version pins and markers, excluding only the Qt distributions."""
    lines = []
    for line in text.splitlines():
        if match := _PIN.match(line):
            name = match.group(1).lower().replace("_", "-")
            if not name.startswith("pyside6") and name != "shiboken6":
                lines.append(line.removesuffix("\\").rstrip())
    if not lines:
        raise ValueError("The regular test lock contains no non-Qt pins")
    return "\n".join(lines) + "\n"


def main() -> None:
    """Create deterministic base constraints and run the fixed wheel-only compatibility resolver."""
    build = _ROOT / "build"
    build.mkdir(exist_ok=True)
    constraints = build / "qt68-base-constraints.txt"
    constraints.write_text(base_constraints((_ROOT / ".github/requirements/test.txt").read_text(encoding="utf-8")),
                           encoding="utf-8", newline="\n")
    uv = shutil.which("uv")
    if uv is None:
        raise FileNotFoundError("Install uv before regenerating the Qt 6.8 compatibility lock")
    subprocess.run([  # noqa: S603 - resolved uv executable and fixed repository arguments
        uv, "pip", "compile", "dev_requirements.txt", "--constraint", "build/qt68-base-constraints.txt",
        "--override", ".github/requirements/qt68.in", "--universal", "--python-version", "3.13",
        "--generate-hashes", "--only-binary", ":all:", "--default-index", "https://pypi.org/simple",
        "--output-file", ".github/requirements/qt68.txt",
    ], cwd=_ROOT, check=True)


if __name__ == "__main__":
    main()
