"""Every GitHub Actions step pins its action to a commit SHA.

A tag such as ``@v4`` can be moved to new code at any time (the 2025
tj-actions/changed-files compromise rewrote tags), so each ``uses:`` names a
full 40-hex commit and carries the release it corresponds to as a comment,
which is what Dependabot reads and updates. Pinning also keeps Node 20 actions
from lingering unnoticed: GitHub removed Node 20 from its runners on 2026-09-23.

The rest of the workflow supply chain is guarded here too: Dependabot's
settings, checkout credentials, job timeouts, and the hash-locked tooling of
the job that holds the PyPI token, the build backend included.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
from packaging.requirements import Requirement  # pytest depends on packaging

_ROOT = next(p for p in Path(__file__).resolve().parents if (p / ".github" / "workflows").is_dir())
_WORKFLOWS = sorted((_ROOT / ".github" / "workflows").glob("*.yml"))
_ACTION_FILES = [*_WORKFLOWS, *sorted((_ROOT / ".github" / "actions").rglob("action.yml"))]
_USES = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)(.*)$")
_PINNED = re.compile(r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
_LOCAL = re.compile(r"^\./")
_VERSION_COMMENT = re.compile(r"^\s+#\s*v\d+(\.\d+)*\s*$")


def _uses(path: Path) -> list[tuple[int, str, str]]:
    """Return ``(line number, action reference, rest of line)`` for each remote ``uses:``."""
    found = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = _USES.match(line)
        if match and not _LOCAL.match(match.group(1)):
            found.append((number, match.group(1), match.group(2)))
    return found


def test_workflows_exist():
    assert _WORKFLOWS


@pytest.mark.parametrize("workflow", _ACTION_FILES, ids=lambda p: p.relative_to(_ROOT).as_posix())
def test_every_action_is_pinned_to_a_commit_with_its_version(workflow):
    bad = [f"{workflow.name}:{number} {ref}{rest}"
           for number, ref, rest in _uses(workflow)
           if not (_PINNED.match(ref) and _VERSION_COMMENT.match(rest))]
    assert bad == []


def test_one_version_per_action():
    # The same action at two different commits means a partial upgrade.
    seen: dict[str, set[str]] = {}
    for workflow in _ACTION_FILES:
        for _number, ref, _rest in _uses(workflow):
            action, _, sha = ref.partition("@")
            seen.setdefault(action, set()).add(sha)
    assert {action: shas for action, shas in seen.items() if len(shas) > 1} == {}


def test_dependabot_keeps_pins_current_on_dev():
    # Pinned SHAs only stay current if something bumps them; every update
    # goes to dev because main is the release branch. Parsed as text: PyYAML
    # is not a test dependency.
    text = (_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    blocks = re.split(r"^\s*-\s*package-ecosystem:", text, flags=re.MULTILINE)[1:]
    ecosystems = {block.split()[0].strip("\"'") for block in blocks}
    assert {"pip", "github-actions"} <= ecosystems
    assert all(re.search(r"^\s*target-branch:\s*\"dev\"", block, re.MULTILINE)
               for block in blocks)


def test_dependabot_waits_a_week_before_proposing_a_release():
    # A compromised release is usually found and yanked within days. Dependabot's
    # own default wait is 3 days, and zizmor's dependabot-cooldown audit asks
    # for 7. The wait never delays security updates.
    text = (_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    blocks = re.split(r"^\s*-\s*package-ecosystem:", text, flags=re.MULTILINE)[1:]
    days = [re.search(r"^\s*default-days:\s*(\d+)", block, re.MULTILINE) for block in blocks]
    assert blocks and all(match and int(match.group(1)) >= 7 for match in days)


def test_dependabot_watches_the_hash_locked_requirements():
    # From "/" Dependabot does not look as deep as .github/requirements/, so the
    # directory has to be named or the lock in it is never updated.
    text = (_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    blocks = re.split(r"^\s*-\s*package-ecosystem:", text, flags=re.MULTILINE)[1:]
    pip = next(block for block in blocks if block.split()[0].strip("\"'") == "pip")
    assert set(re.findall(r"^\s*-\s*\"(/[^\"]*)\"", pip, re.MULTILINE)) == {"/", "/.github/requirements"}


def _checkout_steps(path: Path) -> list[tuple[int, str]]:
    """Return ``(line number, step text)`` for each ``actions/checkout`` step."""
    lines = path.read_text(encoding="utf-8").splitlines()
    steps = []
    for index, line in enumerate(lines):
        if not re.search(r"uses:\s*actions/checkout@", line):
            continue
        column = line.index("uses:")
        body = [line]
        for following in lines[index + 1:]:
            indent = len(following) - len(following.lstrip())
            if following.strip() and (indent < column or following.lstrip().startswith("- ")):
                break
            body.append(following)
        steps.append((index + 1, "\n".join(body)))
    return steps


@pytest.mark.parametrize("workflow", _WORKFLOWS, ids=lambda p: p.name)
def test_every_checkout_decides_on_persisted_credentials(workflow):
    # actions/checkout leaves the job token in .git/config unless told not
    # to, where every later step (and any uploaded workspace) can read it.
    # Only jobs that push keep it, and they say so.
    bad = [f"{workflow.name}:{number}" for number, step in _checkout_steps(workflow)
           if not re.search(r"^\s*persist-credentials:\s*(true|false)\b", step, re.MULTILINE)]
    assert bad == []


_JOB_HEAD = re.compile(r"^  [A-Za-z0-9_-]+:\s*(#.*)?$")


def _jobs(path: Path) -> list[tuple[str, str]]:
    """Return ``(job id, job text)`` for each job under ``jobs:`` in a workflow."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if re.match(r"^jobs:\s*(#.*)?$", line))
    heads = [i for i in range(start + 1, len(lines)) if _JOB_HEAD.match(lines[i])]
    ends = [*heads[1:], len(lines)]
    return [(lines[i].strip().rstrip(":"), "\n".join(lines[i:end])) for i, end in zip(heads, ends, strict=True)]


@pytest.mark.parametrize("workflow", _WORKFLOWS, ids=lambda p: p.name)
def test_every_job_has_a_timeout(workflow):
    # Without timeout-minutes a hung job runs for GitHub's default six hours.
    # Each job sets about three times its slowest recent run, at least 15 minutes.
    bad = [name for name, body in _jobs(workflow)
           if "runs-on:" in body and not re.search(r"^\s*timeout-minutes:", body, re.MULTILINE)]
    assert bad == []


_REQUIREMENTS = _ROOT / ".github" / "requirements"
_LOCKED_INSTALL = "python -m pip install --require-hashes --only-binary :all: -r .github/requirements/publish.txt"
_PIP_INSTALL = re.compile(r"(?:python3? -m )?\bpip3? install\b.*")
_RUN_OR_IMPORT = re.compile(r"python3? -m ([A-Za-z_]\w*)|^\s*import ([A-Za-z_]\w*)", re.MULTILINE)
_BUILD = re.compile(r"(?:\bpython3? -m build\b|\bpyproject-build\b)[^\n#]*")
_PIN = re.compile(r"^([A-Za-z0-9][\w.-]*)==(\S+)", re.MULTILINE)
_BUILD_SYSTEM = re.compile(r"^\[build-system\]\n(.*?)(?=^\[|\Z)", re.MULTILINE | re.DOTALL)
_BUILD_REQUIRES = re.compile(r"^requires\s*=\s*\[([^\]]*)\]", re.MULTILINE)
# The metadata the release job builds from.
_METADATA = ["pyproject.toml"]
# The wheels a lock holds are for one platform; each runner label maps to the one it was resolved for.
_PLATFORM_OF_RUNNER = {"ubuntu-latest": "x86_64-manylinux_2_28"}


def _publish_jobs() -> list[tuple[str, str]]:
    """Return ``(workflow:job, job text without comment lines)`` for each job that reads the PyPI token."""
    found = []
    for workflow in _WORKFLOWS:
        for name, body in _jobs(workflow):
            if "secrets.PYPI_API_TOKEN" in body:
                code = [line for line in body.splitlines() if not line.lstrip().startswith("#")]
                found.append((f"{workflow.name}:{name}", "\n".join(code)))
    return found


_PUBLISH_JOBS = _publish_jobs()
_PUBLISH_IDS = [name for name, _body in _PUBLISH_JOBS]
_PUBLISH_BODIES = [body for _name, body in _PUBLISH_JOBS]


def _distribution(name: str) -> str:
    """Return a module or requirement name the way PyPI spells a distribution."""
    return name.lower().replace("_", "-")


def _tools(body: str) -> set[str]:
    """Return what a job runs with ``python -m`` or imports in an inline script, less pip and the stdlib."""
    named = {module or imported for module, imported in _RUN_OR_IMPORT.findall(body)}
    return {_distribution(name) for name in named - {"pip"} - set(sys.stdlib_module_names)}


def _requirements(name: str) -> set[str]:
    """Return the distributions a file in ``.github/requirements`` names, one at the start of a line."""
    text = (_REQUIREMENTS / name).read_text(encoding="utf-8")
    return {_distribution(found) for found in re.findall(r"^([A-Za-z0-9][\w.-]*)", text, re.MULTILINE)}


def _builds(body: str) -> list[str]:
    """Return each command of a job that builds the distribution, without a trailing comment."""
    return [command.strip() for command in _BUILD.findall(body)]


def _pins() -> dict[str, str]:
    """Return ``{distribution: version}`` for each pin of ``publish.txt``."""
    text = (_REQUIREMENTS / "publish.txt").read_text(encoding="utf-8")
    return {_distribution(name): version for name, version in _PIN.findall(text)}


def _build_requires(metadata: str) -> list[Requirement]:
    """Return ``build-system.requires`` of a metadata file in the repository root.

    Parsed as text: ``tomllib`` is missing on Python 3.10, which CI still tests.
    """
    section = _BUILD_SYSTEM.search((_ROOT / metadata).read_text(encoding="utf-8"))
    assert section is not None, f"{metadata} has no [build-system] table"
    requires = _BUILD_REQUIRES.search(section.group(1))
    assert requires is not None, f"{metadata} has no build-system.requires"
    return [Requirement(item) for item in re.findall(r"[\"']([^\"']+)[\"']", requires.group(1))]


def _unmet(requirements: list[Requirement], pins: dict[str, str]) -> list[str]:
    """Return the requirements ``pins`` does not satisfy; a package it does not pin is unmet."""
    named = [(requirement, _distribution(requirement.name)) for requirement in requirements]
    return [str(requirement) for requirement, name in named
            if name not in pins or not requirement.specifier.contains(pins[name])]


def _lock_option(option: str) -> str:
    """Return the value of an option of the ``uv pip compile`` command recorded in the lock's header."""
    header = (_REQUIREMENTS / "publish.txt").read_text(encoding="utf-8").splitlines()[1]
    match = re.search(rf"{re.escape(option)} (\S+)", header)
    assert match is not None, f"{option} is missing from the lock's header"
    return match.group(1)


def test_only_the_isolated_pypi_upload_job_holds_the_pypi_token():
    # The producer, build-exe and publish-release never see the token; a new job reading it must be
    # held to the rules below.
    assert _PUBLISH_IDS == ["release.yml:publish-pypi"]


@pytest.mark.parametrize("body", _PUBLISH_BODIES, ids=_PUBLISH_IDS)
def test_publish_job_installs_only_the_hash_locked_tooling(body):
    # Whatever this job installs runs next to the PyPI token. An install by
    # version alone trusts the index to serve the same file again, and upgrading
    # pip first takes one more download; the lock allows only wheels whose
    # hashes were recorded.
    assert [command.strip() for command in _PIP_INSTALL.findall(body)] == [_LOCKED_INSTALL]


def test_release_producer_installs_before_it_pushes_anything():
    # A lock that no longer installs must stop the release before the version commit and the tag exist.
    body = dict(_jobs(_ROOT / ".github/workflows/release.yml"))["release"]
    assert [command.strip() for command in _PIP_INSTALL.findall(body)] == [_LOCKED_INSTALL]
    assert body.index(_LOCKED_INSTALL) < body.index("git push")
    assert "secrets.PYPI_API_TOKEN" not in body


def test_release_producer_builds_with_the_locked_backend():
    # An isolated build makes an environment of its own and downloads the newest setuptools of that
    # minute into it, outside publish.txt, in the job that is about to upload with the token.
    # --no-isolation builds with the backend the locked install put in the job.
    body = dict(_jobs(_ROOT / ".github/workflows/release.yml"))["release"]
    builds = _builds(body)
    assert builds
    assert [build for build in builds if "--no-isolation" not in build.split()] == []


def test_the_build_check_sees_an_isolated_build():
    job = "run: python -m build\nrun: python -m build  # --no-isolation\nrun: pyproject-build --sdist\n"
    assert _builds(job) == ["python -m build", "python -m build", "pyproject-build --sdist"]
    assert _builds("run: python -m twine check dist/*\nrun: python tools/build_nuitka.py --onefile\n") == []


def test_publish_in_lists_exactly_the_tools_the_jobs_run_and_the_build_backend():
    # A tool the job starts using has to be locked first, or the release fails at that step. The
    # backend is not run by name: the producer imports it from its own environment (--no-isolation).
    producer = dict(_jobs(_ROOT / ".github/workflows/release.yml"))["release"]
    used = set().union(*(_tools(body) for body in [*_PUBLISH_BODIES, producer]))
    backend = {_distribution(requirement.name)
               for metadata in _METADATA for requirement in _build_requires(metadata)}
    assert backend
    assert used | backend == _requirements("publish.in")


def test_publish_lock_pins_every_tool_of_publish_in():
    # publish.txt is generated; editing publish.in alone changes nothing the job installs.
    assert _requirements("publish.in") <= _requirements("publish.txt")


@pytest.mark.parametrize("metadata", _METADATA)
def test_publish_lock_satisfies_build_system_requires(metadata):
    # --no-isolation checks build-system.requires against what is installed and installs nothing,
    # and the build runs after the version commit and the tag are pushed. A backend that is not
    # locked, or a floor raised without regenerating publish.txt (Dependabot edits pyproject.toml),
    # has to fail here and not in the release job.
    requirements = _build_requires(metadata)
    assert requirements
    assert _unmet(requirements, _pins()) == []


def test_the_requirement_check_sees_a_raised_floor_and_an_unpinned_package():
    pins = {"setuptools": "84.0.0"}
    assert _unmet([Requirement("setuptools>=82.0.1")], pins) == []
    assert _unmet([Requirement("setuptools>=85"), Requirement("wheel")], pins) == ["setuptools>=85", "wheel"]


def test_publish_lock_is_resolved_for_the_python_and_runner_of_the_job():
    # The lock holds the wheels of one Python version on one platform; a job on another may find none that match.
    pythons = {version for body in _PUBLISH_BODIES for version in re.findall(r"python-version:\s*\"([^\"]+)\"", body)}
    runners = {runner for body in _PUBLISH_BODIES for runner in re.findall(r"runs-on:\s*(\S+)", body)}
    assert pythons == {_lock_option("--python-version")}
    assert {_PLATFORM_OF_RUNNER.get(runner) for runner in runners} == {_lock_option("--python-platform")}
