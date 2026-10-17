"""Independent owned APFS observations retain every failure instead of accepting a healthy retry."""

import os
from pathlib import Path
import shutil
import subprocess
import textwrap

import pytest

from test_workflow_actions import _jobs

_ROOT = Path(__file__).resolve().parents[1]


def _bash():
    if os.name != "nt":
        return "/bin/bash"
    git = shutil.which("git")
    if git:
        candidate = Path(git).resolve().parent.parent / "bin/bash.exe"
        if candidate.is_file():
            return str(candidate)
    pytest.skip("Git Bash unavailable for the isolated workflow-shell test")


def _script():
    job = dict(_jobs(_ROOT / ".github/workflows/test.yml"))["macos"]
    step = job.split("    - name: Validate fresh owned APFS capacity, recovery and cross-volume metadata\n", 1)[1]
    step = step.split("\n    - ", 1)[0]
    assert "shell: bash" in step
    return textwrap.dedent(step.split("      run: |\n", 1)[1])


@pytest.mark.parametrize("statuses", [(0, 0, 0), (7, 0, 0), (0, 7, 0), (0, 0, 7), (7, 7, 7)])
def test_native_samples_keep_independent_paths_and_any_failure(tmp_path, statuses):
    script = _script()
    prelude = r"""
PATH=/usr/bin:/bin:$PATH
apfs_test_calls=0
python() {
    [ "$#" = 3 ] && [ "$1" = tools/validate_macos_volume.py ] && [ "$2" = --evidence ] || return 97
    apfs_test_calls=$((apfs_test_calls + 1))
    printf '%s\n' "$3" >> calls.txt
    case "$apfs_test_calls" in
        1) return "$FILETREE_APFS_STATUS_1" ;;
        2) return "$FILETREE_APFS_STATUS_2" ;;
        3) return "$FILETREE_APFS_STATUS_3" ;;
        *) return 98 ;;
    esac
}
"""
    environment = dict(os.environ, **{f"FILETREE_APFS_STATUS_{index}": str(value)
                                      for index, value in enumerate(statuses, 1)})
    result = subprocess.run([_bash(), "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", prelude + script],
                            cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=10, check=False)
    assert result.returncode == int(any(statuses)), result.stderr
    expected = ["macos-evidence/apfs", "macos-evidence/apfs/sample-2", "macos-evidence/apfs/sample-3"]
    assert (tmp_path / "calls.txt").read_text(encoding="utf-8").splitlines() == expected
    summary = (tmp_path / "macos-evidence/apfs/samples.tsv").read_text(encoding="utf-8").splitlines()
    assert summary == [f"{index}\t{status}\t{path}"
                       for index, (status, path) in enumerate(zip(statuses, expected, strict=True), 1)]
    assert all(f"exit={status}" in result.stdout for status in statuses)
