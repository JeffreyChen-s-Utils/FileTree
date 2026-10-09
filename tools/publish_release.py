"""Publish a tagged GitHub release only after every required compiled asset is uploaded."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


class PublicationError(Exception):
    """The release payload or remote draft is incomplete or unsafe to replace."""


def release_version(value: str) -> str:
    """Turn an untrusted CLI value into a canonical version composed only of bounded integers."""
    match = re.fullmatch(r"([0-9]{1,6})\.([0-9]{1,6})\.([0-9]{1,6})", value)
    if match is None:
        raise PublicationError("Expected a numeric major.minor.patch version")
    major, minor, patch = (int(part) for part in match.groups())
    return f"{major}.{minor}.{patch}"


def release_assets(version: str, root: Path) -> list[Path]:
    """Require the exact version's Python and Windows payloads, including the complete folder ZIP."""
    version = release_version(version)
    windows = root / "release-assets"
    assets = [root / "dist" / f"je_file_tree-{version}-py3-none-any.whl",
              root / "dist" / f"je_file_tree-{version}.tar.gz",
              windows / f"FileTree-{version}-windows-standalone.zip",
              windows / f"FileTree-{version}-windows-x64.msi",
              windows / f"FileTree-{version}-package-drafts.zip"]
    assets.extend(sorted((windows / "linux").glob("*.AppImage")))
    assets.extend(sorted((windows / "macos").glob("*.zip")))
    for asset in assets:
        if asset.is_symlink() or not asset.is_file() or asset.stat().st_size == 0:
            raise PublicationError(f"Missing, empty or linked release asset: {asset.name}")
    if len({asset.name for asset in assets}) != len(assets):
        raise PublicationError("Duplicate release asset names")
    return assets


def _gh(arguments: list[str], *, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess[str]:
    program = shutil.which("gh")
    if program is None:
        raise PublicationError("GitHub CLI is required")
    # Fixed CLI, validated numeric tag and owned artifact paths; never invoke a shell.
    return subprocess.run([program, "release", *arguments], capture_output=capture, text=True,  # noqa: S603
                          check=check, timeout=120)


def publish(version: str, root: Path) -> None:
    """Resume a draft, upload and verify assets, then publish; never replace a public release."""
    version = release_version(version)
    assets = release_assets(version, root)
    tag = f"v{version}"
    existing = _gh(["view", tag, "--json", "isDraft"], capture=True, check=False)
    if existing.returncode == 0:
        if json.loads(existing.stdout).get("isDraft") is not True:
            raise PublicationError(f"Release {tag} is already public; refusing to replace assets")
    else:
        _gh(["create", tag, "--verify-tag", "--draft",
             "--title", f"FileTree {version}", "--generate-notes"])
    _gh(["upload", tag, *(str(asset) for asset in assets), "--clobber"])
    uploaded = _gh(["view", tag, "--json", "assets"], capture=True)
    remote = {asset["name"]: asset for asset in json.loads(uploaded.stdout)["assets"]}
    for asset in assets:
        receipt = remote.get(asset.name, {})
        if receipt.get("state") != "uploaded" or receipt.get("size") != asset.stat().st_size:
            raise PublicationError(f"Release upload verification failed: {asset.name}")
    _gh(["edit", tag, "--draft=false"])


def main(argv: list[str]) -> int:
    """Publish using the runner's GH_TOKEN, without placing credentials in command arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    options = parser.parse_args(argv)
    try:
        publish(options.version, Path.cwd())
    except (PublicationError, subprocess.SubprocessError, OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Release publication failed: {error}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
