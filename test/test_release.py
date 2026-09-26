"""The release: the version bump the workflow runs, and what the workflow must keep doing."""

from __future__ import annotations

import importlib.util
import re
import shutil
from pathlib import Path

import pytest

import je_file_tree

_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW = _ROOT / ".github" / "workflows" / "release.yml"
_spec = importlib.util.spec_from_file_location("bump_version", _ROOT / "tools" / "bump_version.py")
assert _spec is not None
assert _spec.loader is not None
bump_version = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bump_version)


def _copy_version_files(target: Path) -> None:
    (target / "je_file_tree").mkdir()
    shutil.copy(_ROOT / "pyproject.toml", target / "pyproject.toml")
    shutil.copy(_ROOT / "je_file_tree" / "__init__.py", target / "je_file_tree" / "__init__.py")


def _versions(root: Path) -> tuple[str, str]:
    project = re.search(r'^version = "([^"]+)"', (root / "pyproject.toml").read_text(encoding="utf-8"), re.MULTILINE)
    package = re.search(r'__version__ = "([^"]+)"', (root / "je_file_tree" / "__init__.py").read_text(encoding="utf-8"))
    assert project is not None
    assert package is not None
    return project.group(1), package.group(1)


def test_the_two_version_files_agree() -> None:
    project, package = _versions(_ROOT)
    assert project == package == je_file_tree.__version__


@pytest.mark.parametrize(("part", "expected"), [("patch", (1, 2, 4)), ("minor", (1, 3, 0)), ("major", (2, 0, 0))])
def test_next_version(part: str, expected: tuple[int, int, int]) -> None:
    assert bump_version.next_version((1, 2, 3), part) == expected


def test_bump_raises_both_files_together(tmp_path: Path) -> None:
    _copy_version_files(tmp_path)
    before, _ = _versions(tmp_path)
    major, minor, patch = (int(part) for part in before.split("."))
    new = bump_version.bump("patch", tmp_path)
    assert new == f"{major}.{minor}.{patch + 1}"
    assert _versions(tmp_path) == (new, new)


def test_bump_changes_nothing_when_the_files_disagree(tmp_path: Path) -> None:
    _copy_version_files(tmp_path)
    init = tmp_path / "je_file_tree" / "__init__.py"
    init.write_text(re.sub(r'__version__ = "[^"]+"', '__version__ = "9.9.9"', init.read_text(encoding="utf-8")),
                    encoding="utf-8")
    before = _versions(tmp_path)
    with pytest.raises(bump_version.VersionError, match="disagree"):
        bump_version.bump("patch", tmp_path)
    assert _versions(tmp_path) == before


def test_the_workflow_releases_on_merge_and_attaches_the_exe() -> None:
    text = _WORKFLOW.read_text(encoding="utf-8")
    assert "types: [closed]" in text
    assert "github.event.pull_request.merged == true" in text
    assert "python tools/bump_version.py" in text, "the tested script, not an inline copy"
    assert "git add pyproject.toml je_file_tree/__init__.py" in text
    assert text.index("PYPI_API_TOKEN repository secret is not set") < text.index("python tools/bump_version.py"), (
        "a missing token stops the release before anything is pushed")
    assert "python tools/build_nuitka.py --onefile" in text
    assert "FileTree-" in text
    assert ".exe" in text


def test_every_install_in_the_release_takes_wheels_only() -> None:
    # An sdist runs its setup script while installing; in the job that holds the PyPI token that
    # would be code from the index running with the token around. Nuitka is published only as an
    # sdist, so it alone is exempt, by name.
    installs = [line.strip() for line in _WORKFLOW.read_text(encoding="utf-8").splitlines()
                if "pip install" in line and not line.strip().startswith("#")]
    assert installs
    for line in installs:
        assert "--only-binary :all:" in line, line
    exempt = [line for line in installs if "--no-binary" in line]
    assert all("--no-binary nuitka" in line for line in exempt), exempt
