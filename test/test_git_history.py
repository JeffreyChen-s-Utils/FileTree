"""Real Git repositories prove all-ref reachability, bounded results and read-only cancellation."""

import hashlib
import stat
import subprocess  # nosec B404 - fixed Git in owned test repositories
import threading

import pytest

from je_file_tree.core import git_history as history


def _git(folder, *arguments, contents=None):
    command = ["git", "-c", "user.name=FileTree test", "-c", "user.email=filetree@example.invalid",
               "-c", "commit.gpgsign=false", "-c", "core.hooksPath=" + str(folder / "absent-hooks"),
               "-c", "gc.auto=0", "-c", "maintenance.auto=false",
               "-C", str(folder), *arguments]
    return subprocess.run(command, input=contents, capture_output=True, check=True,  # noqa: S603 # nosec B603
                          env=history._environment()).stdout.decode("utf-8").strip()


@pytest.fixture
def repository(tmp_path):
    root = tmp_path / "資料 with space"
    root.mkdir()
    _git(root, "init")
    target = root / "資料 1.txt"
    target.write_bytes(b"old large contents" * 15000)
    _git(root, "add", "--", target.name)
    _git(root, "commit", "-m", "large history")
    old_blob = _git(root, "rev-parse", "HEAD:" + target.name)
    _git(root, "tag", "retained-history")
    target.write_bytes(b"now small")
    _git(root, "add", "--", target.name)
    _git(root, "commit", "-m", "small current file")
    unreachable = _git(root, "hash-object", "-w", "--stdin", contents=b"unreachable" * 100000)
    return root, old_blob, unreachable


def _contents(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).digest()
            for path in root.rglob("*") if path.is_file()}


def test_largest_all_ref_objects_are_logical_and_do_not_change_repository(repository):
    root, old_blob, unreachable = repository
    before = _contents(root)
    result = history.git_history(str(root), limit=1)
    assert len(result.rows) == 1 and result.count > 1
    assert result.rows[0].oid == old_blob and result.rows[0].kind == "blob"
    assert result.rows[0].size == len(b"old large contents" * 15000)
    assert result.logical > result.rows[0].size and result.loose > 0
    assert result.rows[0].oid != unreachable
    assert _contents(root) == before
    complete = history.git_history(str(root), limit=100)
    assert result.count == complete.count and result.logical == complete.logical
    assert unreachable not in {row.oid for row in complete.rows}


def test_cancellation_and_deadline_reap_only_the_owned_git_processes(repository, monkeypatch):
    root, _, _ = repository
    original, processes = history.subprocess.Popen, []
    def remember(*args, **kwargs):
        process = original(*args, **kwargs)
        processes.append(process)
        assert args[0][0] == "git" and "--no-lazy-fetch" in args[0]
        assert not kwargs.get("shell", False)
        assert kwargs["env"]["GIT_NO_LAZY_FETCH"] == "1"
        return process
    monkeypatch.setattr(history.subprocess, "Popen", remember)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(history.GitHistoryCancelledError):
        history.git_history(str(root), cancel=cancel)
    assert all(process.poll() is not None for process in processes)
    assert all(process.stdout.closed and process.stderr.closed for process in processes)
    with pytest.raises(OSError, match="timed out"):
        history.git_history(str(root), seconds=.000001)
    assert all(process.poll() is not None for process in processes)


def test_environment_cannot_redirect_the_selected_repository(repository, tmp_path, monkeypatch):
    root, old_blob, _ = repository
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "missing.git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path))
    assert history.git_history(str(root), limit=1).rows[0].oid == old_blob


def test_not_a_repository_and_invalid_limits_are_clear_errors(tmp_path):
    # A scratch folder can be inside the workspace Git repository; stop ancestor discovery here.
    (tmp_path / ".git").write_text(f"gitdir: {(tmp_path / 'missing.git').as_posix()}\n", encoding="utf-8")
    with pytest.raises(OSError, match="not a git repository"):
        history.git_history(str(tmp_path))
    for limits in ({"limit": 0}, {"seconds": 0}):
        with pytest.raises(ValueError, match="positive"):
            history.git_history(str(tmp_path), **limits)


def test_missing_reachable_objects_do_not_become_complete_or_trigger_fetching(repository):
    root, old_blob, _ = repository
    owned_object = root / ".git" / "objects" / old_blob[:2] / old_blob[2:]
    owned_object.chmod(stat.S_IREAD | stat.S_IWRITE)
    owned_object.unlink()
    with pytest.raises(OSError):
        history.git_history(str(root))
