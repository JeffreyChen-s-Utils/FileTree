"""The compatibility lane keeps pinned dependencies and cannot silently run on modern Qt."""

import re
from pathlib import Path

import pytest
from packaging.requirements import Requirement

from test_workflow_actions import _jobs
from tools.compile_qt68_lock import base_constraints

_ROOT = Path(__file__).resolve().parents[1]


def _pins(name: str) -> dict[str, str]:
    return {package.lower().replace("_", "-"): version
            for package, version in re.findall(r"^([\w.-]+)==([^\s;]+)",
                                               (_ROOT / ".github/requirements" / name).read_text(encoding="utf-8"),
                                               re.MULTILINE)}


def test_compatibility_lock_only_changes_qt_distributions():
    ordinary, compatibility = _pins("test.txt"), _pins("qt68.txt")
    qt = {name for name in compatibility if name.startswith("pyside6") or name == "shiboken6"}
    assert qt == {"pyside6", "pyside6-addons", "pyside6-essentials", "shiboken6"}
    assert {compatibility[name] for name in qt} == {"6.8.3"}
    assert all(ordinary[name] == version for name, version in compatibility.items() if name not in qt)
    assert compatibility["pytest"] == ordinary["pytest"] and compatibility["ruff"] == ordinary["ruff"]
    requirements = (_ROOT / "requirements.txt").read_text(encoding="utf-8")
    requirement = next(Requirement(line) for line in requirements.splitlines()
                       if line.startswith("PySide6"))
    assert requirement.specifier.contains("6.8.3")


def test_base_constraints_keep_markers_and_drop_only_qt():
    source = "\n".join(["# lock", "pyside6==6.12.0 \\", "pyside6-addons==6.12.0 \\",
                        "shiboken6==6.12.0 \\", "pytest==9.1.1 \\",
                        "colorama==0.4.6 ; sys_platform == 'win32' \\", "    --hash=sha256:abcd"])
    assert base_constraints(source) == "pytest==9.1.1\ncolorama==0.4.6 ; sys_platform == 'win32'\n"


@pytest.mark.parametrize("source", ["", "# only comments\n", "pyside6==6.12.0\n"])
def test_missing_base_pins_are_refused(source):
    with pytest.raises(ValueError, match="no non-Qt pins"):
        base_constraints(source)


def test_compatibility_matrix_and_failure_evidence_are_independent():
    job = dict(_jobs(_ROOT / ".github/workflows/test.yml"))["qt68"]
    assert "os: [windows-latest, ubuntu-latest]" in job and "fail-fast: false" in job
    assert 'python-version: "3.13"' in job and "timeout-minutes: 15" in job
    assert "--require-hashes --only-binary :all: -r .github/requirements/qt68.txt" in job
    assert 'record["pyside6"] != "6.8.3"' in job and 'record["qt"] != "6.8.3"' in job
    assert 'record["update_threshold_available"]' in job and "raise SystemExit" in job
    assert job.index("write_text(json.dumps(record") < job.index("raise SystemExit")
    assert "PYTEST_DISABLE_PLUGIN_AUTOLOAD:" in job and "--junitxml=build/qt68-tests.xml" in job
    assert "test/test_grouped_list.py" in job and "test/test_grouped_display_refresh.py" in job
    assert "test/test_measure_grouped_layout.py" in job
    upload = job.split("    - name: Preserve compatibility runtime and test evidence", 1)[1]
    assert "if: always()" in upload and "build/qt68-runtime.json" in upload and "build/qt68-tests.xml" in upload
