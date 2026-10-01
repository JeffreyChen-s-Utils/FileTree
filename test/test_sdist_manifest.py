"""The source distribution carries no tests.

setuptools adds ``test*/test*.py`` to an sdist by default, so the ``je_file_tree`` 0.1.1 sdist shipped
18 files of this suite although the wheel installs only the package
(``[tool.setuptools.packages.find]`` in ``pyproject.toml``). ``MANIFEST.in`` prunes the directory.
Nothing is built here: the template is read and its commands are checked in the order setuptools
applies them.
"""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_TEST_DIRECTORY = Path(__file__).resolve().parent.name
_PRUNE = ["prune", _TEST_DIRECTORY]
# The template commands that add files; one of them after the prune could bring tests back.
_ADDING = {"include", "recursive-include", "global-include", "graft"}


def _commands() -> list[list[str]]:
    """Return the commands of ``MANIFEST.in`` in order, each split into words."""
    lines = (_ROOT / "MANIFEST.in").read_text(encoding="utf-8").splitlines()
    return [line.split() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def test_manifest_prunes_the_test_directory() -> None:
    assert _PRUNE in _commands()


def test_nothing_after_the_prune_adds_files_back() -> None:
    commands = _commands()
    following = commands[commands.index(_PRUNE) + 1:]
    assert [command for command in following if command[0] in _ADDING] == []
