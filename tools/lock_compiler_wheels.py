"""Regenerate compiler runtime wheel hashes for every native platform without changing pinned versions."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.request import urlopen

_ROOT = Path(__file__).resolve().parents[1]
_LOCKS = ("reports", "archives", "photos")
_PIN = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_.-]*)==([0-9]+(?:\.[0-9]+)*(?:[a-z]+[0-9]+)?)(?=\s|$)")
_HASH = re.compile(r"[a-f0-9]{64}")
_MAX_METADATA = 8 * 1024 * 1024


def _pins(contents: str) -> list[tuple[str, str]]:
    if any(line.strip() and not line.lstrip().startswith(("#", "--hash=sha256:")) and not _PIN.match(line)
           for line in contents.splitlines()):
        raise ValueError("Compiler lock contains an unsupported non-pin line")
    pins = [_PIN.match(line).groups() for line in contents.splitlines() if _PIN.match(line)]
    if not pins or len({name.lower().replace("_", "-") for name, _version in pins}) != len(pins):
        raise ValueError("Compiler lock must contain unambiguous existing exact version pins")
    return pins


def _wheel_hashes(pin: tuple[str, str]) -> tuple[str, str, tuple[str, ...]]:
    name, version = pin
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    with urlopen(url, timeout=30) as response:  # noqa: S310 - fixed HTTPS host and validated exact pins
        payload = response.read(_MAX_METADATA + 1)
    if len(payload) > _MAX_METADATA:
        raise ValueError("PyPI release metadata exceeds the compiler lock bound")
    metadata = json.loads(payload)
    if metadata["info"]["version"] != version:
        raise ValueError("PyPI release version differs from the existing compiler pin")
    hashes = {item["digests"]["sha256"] for item in metadata["urls"]
              if item["packagetype"] == "bdist_wheel" and item["filename"].endswith(".whl")
              and not item.get("yanked", False)}
    if not hashes or any(_HASH.fullmatch(value) is None for value in hashes):
        raise ValueError("PyPI release contains no verified non-yanked wheel hashes")
    return name, version, tuple(sorted(hashes))


def regenerate(names: tuple[str, ...] = _LOCKS) -> None:
    """Atomically rewrite selected compiler locks with published wheel hashes, retaining every exact pin.

    Only fixed repository lock files and validated PyPI release metadata are accessed. Packages and
    source distributions are never downloaded/executed or installed. Native pip still selects only
    compatible wheels under --require-hashes --only-binary :all:; publication credentials are absent.
    """
    if not names or any(name not in _LOCKS for name in names):
        raise ValueError("Unknown compiler runtime lock")
    paths = tuple(_ROOT / ".github/requirements" / f"{name}.txt" for name in names)
    original = {path: path.read_text(encoding="utf-8") for path in paths}
    pins = sorted(set(pin for contents in original.values() for pin in _pins(contents)))
    with ThreadPoolExecutor(max_workers=4) as executor:
        releases = {(name, version): hashes for name, version, hashes in executor.map(_wheel_hashes, pins)}
    prepared = {}
    for path, contents in original.items():
        lines = ["# Published PyPI wheel hashes for Windows/Linux/macOS native compiler runtimes.",
                 "# Regenerate without version changes: py -3 tools/lock_compiler_wheels.py"]
        for name, version in _pins(contents):
            lines.append(f"{name}=={version} \\")
            hashes = releases[name, version]
            lines.extend(f"    --hash=sha256:{checksum}" + (" \\" if index < len(hashes) - 1 else "")
                         for index, checksum in enumerate(hashes))
        prepared[path] = "\n".join(lines) + "\n"
    if any(path.read_text(encoding="utf-8") != contents for path, contents in original.items()):
        raise OSError("Compiler lock changed during metadata verification")
    for path, contents in prepared.items():
        descriptor, filename = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(contents)
            os.replace(filename, path)
        finally:
            Path(filename).unlink(missing_ok=True)


def main() -> None:
    """Refresh only compiler wheel hashes; never bump dependency versions."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("locks", nargs="*", choices=_LOCKS)
    options = parser.parse_args()
    try:
        regenerate(tuple(options.locks) or _LOCKS)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    sys.stdout.write("Compiler wheel hashes verified; exact versions retained.\n")


if __name__ == "__main__":
    main()
