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
    assert '--build-arg DESKTOP_UID="$(id -u)" --build-arg DESKTOP_GID="$(id -g)"' in workflow
    assert "linux-desktop-evidence" in workflow and "if: always()" in workflow
    assert "shell: bash" in workflow
    ignore = (_ROOT / "tools/linux_desktop/Dockerfile.dockerignore").read_text(encoding="utf-8")
    assert "!.github/requirements/runtime.txt" in ignore


def test_desktop_probe_rejects_a_masked_crash_and_incomplete_evidence(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("desktop_runner", _ROOT / "tools/linux_desktop/run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0))
    with pytest.raises(FileNotFoundError):
        module.run_probe({}, tmp_path)
    proof = {"dbus": {"error": "crashed"}, "trash": True, "fallback": True, "drag": True,
             "cjk_font": "test", "background": {"phase": "complete"}}
    (tmp_path / "proof.json").write_text(json.dumps(proof), encoding="utf-8")
    with pytest.raises(RuntimeError, match="dbus"):
        module.run_probe({}, tmp_path)
    proof["dbus"] = {"signature": ["as", "s"]}
    (tmp_path / "proof.json").write_text(json.dumps(proof), encoding="utf-8")
    with pytest.raises(RuntimeError, match="screenshot"):
        module.run_probe({}, tmp_path)
    (tmp_path / "desktop-zh-TW.png").write_bytes(b"owned screenshot fixture")
    assert module.run_probe({}, tmp_path) == 0


@pytest.mark.parametrize("response", [b"12\n", b"", b"0;injected\n", None])
def test_private_display_pipe_requires_readiness_and_always_joins_child(monkeypatch, response):
    spec = importlib.util.spec_from_file_location("desktop_runner", _ROOT / "tools/linux_desktop/run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    closed, lifetime, commands = [], [], []
    server = SimpleNamespace(poll=lambda: None, terminate=lambda: lifetime.append("terminate"),
                             wait=lambda **_kwargs: lifetime.append("joined"))

    def launch(command, **kwargs):
        commands.append(command)
        assert kwargs["pass_fds"] == (41,)
        return server

    monkeypatch.setattr(module, "os", SimpleNamespace(pipe=lambda: (40, 41), close=closed.append,
                                                     read=lambda *_args: response))
    monkeypatch.setattr(module, "select", SimpleNamespace(select=lambda *_args: ([40] if response is not None else [],
                                                                               [], [])))
    monkeypatch.setattr(module.subprocess, "Popen", launch)
    environment = {}
    if response == b"12\n":
        with module.display_server(environment, None):
            assert environment["DISPLAY"] == ":12"
            assert lifetime == []
    else:
        with pytest.raises(RuntimeError, match="Xvfb"), module.display_server(environment, None):
            pytest.fail("invalid/unready display reached the probe")
    assert commands[0][:3] == ["/usr/bin/Xvfb", "-displayfd", "41"]
    assert closed == [41, 40]
    assert lifetime == ["terminate", "joined"]


def test_desktop_container_refuses_an_external_evidence_argument_before_io(monkeypatch):
    spec = importlib.util.spec_from_file_location("desktop_runner", _ROOT / "tools/linux_desktop/run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.sys, "argv", ["run.py", "/outside/evidence"])
    with pytest.raises(ValueError, match="fixed at /evidence"):
        module.main()
