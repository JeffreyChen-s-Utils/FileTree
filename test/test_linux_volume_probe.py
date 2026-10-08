"""The privileged volume probe refuses host/foreign state before any mount or removal."""

import json
import os

import pytest

from tools import validate_linux_volume as volume


@pytest.mark.parametrize("case", ["host_namespace", "wrong_token", "existing_contents"])
def test_probe_refuses_unowned_or_host_state_before_commands(tmp_path, monkeypatch, case):
    scratch = tmp_path / "filetree-volume-owned-test"
    scratch.mkdir()
    owner = {"token": "owned", "uid": scratch.stat().st_uid, "namespace": "mnt:[host]"}
    (scratch / "owner.json").write_text(json.dumps(owner), encoding="utf-8")
    monkeypatch.setattr(volume.sys, "platform", "linux")
    monkeypatch.setattr(volume.os, "geteuid", lambda: 0, raising=False)
    namespace = "mnt:[host]" if case == "host_namespace" else "mnt:[private]"
    monkeypatch.setattr(volume.os, "readlink", lambda _path: namespace)
    calls = []
    monkeypatch.setattr(volume, "command", calls.append)
    if case == "existing_contents":
        (scratch / "foreign").write_text("preserve", encoding="utf-8")
    with pytest.raises(RuntimeError):
        volume.probe(scratch, "wrong" if case == "wrong_token" else "owned")
    assert calls == []
    assert {path.name for path in scratch.iterdir()} == (
        {"owner.json", "foreign"} if case == "existing_contents" else {"owner.json"})


@pytest.mark.skipif(os.name != "posix", reason="POSIX symlink fixture")
def test_probe_refuses_an_alias_to_an_existing_directory(tmp_path, monkeypatch):
    target = tmp_path / "foreign"
    target.mkdir()
    alias = tmp_path / "filetree-volume-alias"
    alias.symlink_to(target, target_is_directory=True)
    monkeypatch.setattr(volume.sys, "platform", "linux")
    monkeypatch.setattr(volume.os, "geteuid", lambda: 0)
    monkeypatch.setattr(volume, "command", lambda _arguments: pytest.fail("foreign alias reached a command"))
    with pytest.raises(RuntimeError, match="owned scratch"):
        volume.probe(alias, "owned")
    assert alias.is_symlink() and target.is_dir() and not list(target.iterdir())
