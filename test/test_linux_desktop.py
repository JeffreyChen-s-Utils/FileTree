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


def test_fallback_refuses_an_external_target_before_native_dispatch(monkeypatch):
    spec = importlib.util.spec_from_file_location("desktop_fallback", _ROOT / "tools/linux_desktop/fallback.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "sys", SimpleNamespace(platform="linux", argv=["fallback.py", "/foreign/target"]))
    monkeypatch.setattr(module, "QApplication", lambda *_args: pytest.fail("foreign target reached Qt"))
    monkeypatch.setattr(module, "reveal_in_file_manager", lambda *_args: pytest.fail("foreign target dispatched"))
    with pytest.raises(ValueError, match="private Linux container fixture"):
        module.main()


def _trash_probe(monkeypatch):
    monkeypatch.syspath_prepend(str(_ROOT / "tools/linux_desktop"))
    spec = importlib.util.spec_from_file_location("desktop_trash_probe", _ROOT / "tools/linux_desktop/probe.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("kind", ["ordinary", "protected", "foreign", "extra"])
def test_private_trash_probe_binds_only_its_presenter_and_restores_on_failure(qapp, tmp_path, monkeypatch, kind):
    module = _trash_probe(monkeypatch)
    results = SimpleNamespace()
    results.show_outcome = lambda outcome: setattr(results, "outcome", outcome)
    window = SimpleNamespace(results=results, _trash_worker=None)
    before = (module.main_window.confirm_entry_move, module.main_window.CleanupReview.exec, module.QMessageBox.question)

    def move(nodes):
        assert len(nodes) == 1 and nodes[0].path == str(tmp_path / "trash-source" / "垃圾桶 測試.txt")
        assert module.main_window.confirm_entry_move is not before[0], "old question hook missed the presenter"
        assert module.QMessageBox.question is before[2], "private approval changed unrelated static questions"
        parent = object() if kind == "foreign" else window
        reply = module.main_window.confirm_entry_move(parent, "Owned fixture", nodes[0].name,
                                                      protected=kind == "protected")
        assert reply == module.QMessageBox.StandardButton.Yes
        if kind == "extra":
            module.main_window.confirm_entry_move(window, "Unexpected second approval", nodes[0].name)
        raise RuntimeError("controlled stop after explicit fixture approval")

    window.move_to_trash = move
    expected = "controlled stop" if kind == "ordinary" else "Unexpected"
    with pytest.raises(RuntimeError, match=expected):
        module.check_trash(qapp, window, tmp_path)
    assert (module.main_window.confirm_entry_move, module.main_window.CleanupReview.exec,
            module.QMessageBox.question) == before
    assert (tmp_path / "trash-source" / "垃圾桶 測試.txt").read_text(encoding="utf-8") == "owned trash contents"


def test_private_trash_probe_declines_unhandled_modal_without_touching_fixture(qapp, tmp_path, monkeypatch):
    module = _trash_probe(monkeypatch)
    results = SimpleNamespace()
    results.show_outcome = lambda outcome: setattr(results, "outcome", outcome)
    before = module.main_window.confirm_entry_move
    window = SimpleNamespace(results=results, _trash_worker=None)
    window.move_to_trash = lambda nodes: module.QMessageBox.question(None, "Unhandled approval", nodes[0].name)
    with pytest.raises(RuntimeError, match="Unhandled entry-move confirmation"):
        module.check_trash(qapp, window, tmp_path)
    assert module.main_window.confirm_entry_move is before
    assert (tmp_path / "trash-source" / "垃圾桶 測試.txt").read_text(encoding="utf-8") == "owned trash contents"
