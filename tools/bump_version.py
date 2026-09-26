"""Raise FileTree's version in ``pyproject.toml`` and ``je_file_tree/__init__.py`` together.

The release workflow (``.github/workflows/release.yml``) runs it on ``main``; never bump by hand::

    python tools/bump_version.py patch   # 0.1.0 -> 0.1.1 (also: minor -> 0.2.0, major -> 1.0.0)

It prints the new version and fails, changing nothing, when the two files disagree.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARTS = ("major", "minor", "patch")
_FILES = {
    Path("pyproject.toml"): re.compile(r'^(version\s*=\s*")(\d+)\.(\d+)\.(\d+)(")', re.MULTILINE),
    Path("je_file_tree", "__init__.py"): re.compile(r'^(__version__\s*=\s*")(\d+)\.(\d+)\.(\d+)(")', re.MULTILINE),
}


class VersionError(Exception):
    """A version file has no version, or the files disagree."""


def next_version(version: tuple[int, int, int], part: str) -> tuple[int, int, int]:
    """``version`` with ``part`` (``major``, ``minor`` or ``patch``) raised and the parts after it reset."""
    major, minor, patch = version
    if part == "major":
        return major + 1, 0, 0
    if part == "minor":
        return major, minor + 1, 0
    return major, minor, patch + 1


def bump(part: str, root: Path = ROOT) -> str:
    """Raise the version in both files under ``root``; returns the new version as ``x.y.z``."""
    texts = {relative: (root / relative).read_text(encoding="utf-8") for relative in _FILES}
    found = set()
    for relative, pattern in _FILES.items():
        match = pattern.search(texts[relative])
        if match is None:
            raise VersionError(f"no version in {relative}")
        found.add(tuple(int(number) for number in match.group(2, 3, 4)))
    if len(found) != 1:
        raise VersionError(f"the version files disagree: {sorted(found)}")
    new = ".".join(str(number) for number in next_version(found.pop(), part))
    for relative, pattern in _FILES.items():
        text = pattern.sub(lambda match: f"{match.group(1)}{new}{match.group(5)}", texts[relative], count=1)
        (root / relative).write_text(text, encoding="utf-8", newline="\n")
    return new


def main(argv: list[str]) -> int:
    """Parse the part to raise, bump, and print the new version."""
    parser = argparse.ArgumentParser(description="Raise FileTree's version in both version files.")
    parser.add_argument("part", choices=PARTS)
    options = parser.parse_args(argv)
    try:
        new = bump(options.part)
    except VersionError as error:
        parser.exit(1, f"bump_version: {error}\n")
    sys.stdout.write(new + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
