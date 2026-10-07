"""The desktop harness exports a strict native signature and stays isolated/resource-bounded."""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from PySide6.QtCore import QMetaMethod

_ROOT = Path(__file__).parents[1]


def test_stand_in_file_manager_exports_a_string_array_and_string(qapp, tmp_path):
    path = _ROOT / "tools/linux_desktop/manager.py"
    spec = importlib.util.spec_from_file_location("strict_file_manager", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    manager = module.FileManager(tmp_path / "record.json")
    meta = manager.metaObject()
    methods = [meta.method(index) for index in range(meta.methodOffset(), meta.methodCount())]
    exported = next(method for method in methods if bytes(method.name()) == b"ShowItems")
    assert exported.methodType() == QMetaMethod.MethodType.Slot
    assert [bytes(value) for value in exported.parameterTypes()] == [b"QStringList", b"QString"]
    assert meta.classInfo(meta.indexOfClassInfo("D-Bus Interface")).value() == "org.freedesktop.FileManager1"


def test_desktop_job_uses_a_read_only_repository_and_small_container():
    workflow = (_ROOT / ".github/workflows/test.yml").read_text(encoding="utf-8")
    assert '--memory=1g --cpus=2 -v "$PWD:/workspace:ro"' in workflow
    assert '--user "$(id -u):$(id -g)"' in workflow
    assert "linux-desktop-evidence" in workflow and "if: always()" in workflow
    assert "shell: bash" in workflow
    ignore = (_ROOT / "tools/linux_desktop/Dockerfile.dockerignore").read_text(encoding="utf-8")
    assert "**\n!requirements.txt" in ignore


def test_desktop_probe_rejects_a_masked_crash_and_incomplete_evidence(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("desktop_runner", _ROOT / "tools/linux_desktop/run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0))
    with pytest.raises(FileNotFoundError):
        module.run_probe({}, tmp_path)
    proof = {"dbus": {"error": "crashed"}, "trash": True, "fallback": True, "cjk_font": "test"}
    (tmp_path / "proof.json").write_text(json.dumps(proof), encoding="utf-8")
    with pytest.raises(RuntimeError, match="dbus"):
        module.run_probe({}, tmp_path)
    proof["dbus"] = {"signature": ["as", "s"]}
    (tmp_path / "proof.json").write_text(json.dumps(proof), encoding="utf-8")
    with pytest.raises(RuntimeError, match="screenshot"):
        module.run_probe({}, tmp_path)
    (tmp_path / "desktop-zh-TW.png").write_bytes(b"owned screenshot fixture")
    assert module.run_probe({}, tmp_path) == 0
