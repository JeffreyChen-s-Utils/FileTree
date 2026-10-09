"""Release assets stay private until the exact compiled payloads finish uploading."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
from unittest.mock import Mock

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("publish_release", _ROOT / "tools/publish_release.py")
assert _spec is not None
assert _spec.loader is not None
publisher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(publisher)


@pytest.fixture(autouse=True)
def github_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(publisher.shutil, "which", lambda _name: "/runner/gh")


@pytest.fixture
def payload(tmp_path: Path) -> Path:
    for directory, names in {
        "dist": ["je_file_tree-1.2.3-py3-none-any.whl", "je_file_tree-1.2.3.tar.gz"],
        "release-assets": ["FileTree-1.2.3-windows-standalone.zip",
                           "FileTree-1.2.3-windows-x64.msi", "FileTree-1.2.3-package-drafts.zip"],
    }.items():
        (tmp_path / directory).mkdir()
        for name in names:
            (tmp_path / directory / name).write_bytes(b"compiled-payload")
    return tmp_path


def _receipt(root: Path, **changes: object) -> str:
    assets = [{"name": path.name, "size": path.stat().st_size, "state": "uploaded"}
              for path in publisher.release_assets("1.2.3", root)]
    assets[2].update(changes)
    return json.dumps({"assets": assets})


@pytest.mark.parametrize("invalid", ["--help", "../1.2.3", "v1.2.3", "1.2", "1.2.3; command",
                                    "1.2.3\n", "9999999.2.3", "١.٢.٣"])
def test_invalid_version_never_calls_github(payload: Path, monkeypatch: pytest.MonkeyPatch, invalid: str) -> None:
    run = Mock()
    monkeypatch.setattr(publisher.subprocess, "run", run)
    with pytest.raises(publisher.PublicationError, match="numeric"):
        publisher.publish(invalid, payload)
    run.assert_not_called()


def test_version_is_reconstructed_from_bounded_integers() -> None:
    assert publisher.release_version("001.002.003") == "1.2.3"


@pytest.mark.parametrize("damage", ["missing", "empty", "different-version"])
def test_missing_or_empty_folder_archive_never_creates_release(
    payload: Path, monkeypatch: pytest.MonkeyPatch, damage: str,
) -> None:
    archive = payload / "release-assets/FileTree-1.2.3-windows-standalone.zip"
    if damage == "empty":
        archive.write_bytes(b"")
    elif damage == "different-version":
        archive.rename(archive.with_name("FileTree-1.2.2-windows-standalone.zip"))
    else:
        archive.unlink()
    run = Mock()
    monkeypatch.setattr(publisher.subprocess, "run", run)
    with pytest.raises(publisher.PublicationError, match="FileTree-1.2.3-windows-standalone.zip"):
        publisher.publish("1.2.3", payload)
    run.assert_not_called()


@pytest.mark.parametrize("resume", [False, True])
def test_uploads_to_draft_and_publishes_only_after_verification(
    payload: Path, monkeypatch: pytest.MonkeyPatch, resume: bool,
) -> None:
    commands: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[2] == "view" and command[-1] == "isDraft":
            return subprocess.CompletedProcess(command, 0 if resume else 1, '{"isDraft": true}')
        return subprocess.CompletedProcess(command, 0, _receipt(payload))

    monkeypatch.setattr(publisher.subprocess, "run", run)
    publisher.publish("1.2.3", payload)
    assert [command[2] for command in commands] == (
        ["view", "upload", "view", "edit"] if resume else ["view", "create", "upload", "view", "edit"])
    if not resume:
        assert '--draft' in commands[1]
        assert '--verify-tag' in commands[1]
    assert "--clobber" in next(command for command in commands if command[2] == "upload")
    assert commands[-1] == ["/runner/gh", "release", "edit", "v1.2.3", "--draft=false"]


def test_public_release_is_never_overwritten(payload: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = Mock(return_value=subprocess.CompletedProcess([], 0, '{"isDraft": false}'))
    monkeypatch.setattr(publisher.subprocess, "run", run)
    with pytest.raises(publisher.PublicationError, match="already public"):
        publisher.publish("1.2.3", payload)
    assert run.call_count == 1


@pytest.mark.parametrize("changes", [{"size": 0}, {"state": "new"},
                                     {"name": "FileTree-1.2.2-windows-standalone.zip"}])
def test_incomplete_remote_folder_archive_stays_a_draft(
    payload: Path, monkeypatch: pytest.MonkeyPatch, changes: dict[str, object],
) -> None:
    run = Mock(side_effect=[subprocess.CompletedProcess([], 0, '{"isDraft": true}'),
                            subprocess.CompletedProcess([], 0),
                            subprocess.CompletedProcess([], 0, _receipt(payload, **changes))])
    monkeypatch.setattr(publisher.subprocess, "run", run)
    with pytest.raises(publisher.PublicationError, match="verification failed"):
        publisher.publish("1.2.3", payload)
    assert all(call.args[0][2] != "edit" for call in run.call_args_list)


def test_upload_failure_stays_a_draft(payload: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = Mock(side_effect=[subprocess.CompletedProcess([], 0, '{"isDraft": true}'),
                            subprocess.CalledProcessError(1, ["gh", "release", "upload"])])
    monkeypatch.setattr(publisher.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        publisher.publish("1.2.3", payload)
    assert run.call_count == 2


def test_includes_optional_native_assets(payload: Path) -> None:
    for directory, name in [("linux", "FileTree.AppImage"), ("macos", "FileTree-macos.zip")]:
        parent = payload / "release-assets" / directory
        parent.mkdir()
        (parent / name).write_bytes(b"native")
    assert len(publisher.release_assets("1.2.3", payload)) == 7


def test_folder_release_does_not_require_or_upload_a_single_executable(payload: Path) -> None:
    assets = publisher.release_assets("1.2.3", payload)
    assert len(assets) == 5
    assert not any(asset.suffix == ".exe" for asset in assets)
    (payload / "release-assets/FileTree-1.2.3.exe").write_bytes(b"obsolete one-file artifact")
    assert publisher.release_assets("1.2.3", payload) == assets
