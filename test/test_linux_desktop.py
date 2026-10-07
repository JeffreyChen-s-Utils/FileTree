"""The desktop harness exports a strict native signature and stays isolated/resource-bounded."""

import importlib.util
from pathlib import Path

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
    assert "linux-desktop-evidence" in workflow and "if: always()" in workflow
    ignore = (_ROOT / "tools/linux_desktop/Dockerfile.dockerignore").read_text(encoding="utf-8")
    assert "**\n!requirements.txt" in ignore
