"""Standalone release archives retain all runtime files and never publish a partial replacement."""

from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("package_standalone", _ROOT / "tools/package_standalone.py")
assert _spec is not None and _spec.loader is not None
package_standalone = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(package_standalone)


def _build(tmp_path: Path) -> Path:
    folder = tmp_path / "build" / "standalone" / "start_file_tree.dist"
    folder.mkdir(parents=True)
    (folder / "FileTree.exe").write_bytes(b"fixture executable")
    (folder / "Qt6Core.dll").write_bytes(b"fixture library")
    translations = folder / "PySide6" / "translations"
    translations.mkdir(parents=True)
    (translations / "qtbase_zh_TW.qm").write_bytes(b"traditional catalogue")
    (translations / "qtbase_zh_CN.qm").write_bytes(b"simplified catalogue")
    plugins = folder / "PySide6" / "plugins" / "platforms"
    plugins.mkdir(parents=True)
    (plugins / "qwindows.dll").write_bytes(b"platform plugin")
    (folder / "empty").mkdir()
    return folder


def test_versioned_zip_keeps_executable_libraries_plugins_catalogues_and_empty_folders(tmp_path: Path) -> None:
    folder = _build(tmp_path)
    target = package_standalone.package_standalone(folder.parent, "1.2.3", tmp_path)
    assert target.name == "FileTree-1.2.3-windows-standalone.zip"
    prefix = "FileTree-1.2.3-windows-standalone/"
    with zipfile.ZipFile(target) as archive:
        assert archive.testzip() is None
        assert archive.read(prefix + "FileTree.exe") == b"fixture executable"
        assert archive.read(prefix + "Qt6Core.dll") == b"fixture library"
        assert archive.read(prefix + "PySide6/plugins/platforms/qwindows.dll") == b"platform plugin"
        assert archive.read(prefix + "PySide6/translations/qtbase_zh_TW.qm") == b"traditional catalogue"
        assert archive.read(prefix + "PySide6/translations/qtbase_zh_CN.qm") == b"simplified catalogue"
        assert prefix + "empty/" in archive.namelist()


def test_incomplete_ambiguous_or_invalid_builds_fail_without_replacing_the_zip(tmp_path: Path) -> None:
    folder = _build(tmp_path)
    target = tmp_path / "FileTree-1.2.3-windows-standalone.zip"
    target.write_bytes(b"previous archive")
    for version in ("../escape", "1.2", "1.2.3/escape"):
        with pytest.raises(ValueError, match="version"):
            package_standalone.package_standalone(folder.parent, version, tmp_path)
    second = folder.parent / "other.dist"
    second.mkdir()
    (second / "FileTree.exe").write_bytes(b"other executable")
    with pytest.raises(ValueError, match="exactly one"):
        package_standalone.package_standalone(folder.parent, "1.2.3", tmp_path)
    assert target.read_bytes() == b"previous archive"


def test_failed_zip_write_preserves_the_previous_archive_and_removes_the_temporary(tmp_path: Path, monkeypatch) -> None:
    folder = _build(tmp_path)
    target = tmp_path / "FileTree-1.2.3-windows-standalone.zip"
    target.write_bytes(b"previous archive")
    original = zipfile.ZipFile.write

    def failed(self, *args, **kwargs):
        original(self, *args, **kwargs)
        raise OSError("disk full")

    monkeypatch.setattr(zipfile.ZipFile, "write", failed)
    with pytest.raises(OSError, match="disk full"):
        package_standalone.package_standalone(folder.parent, "1.2.3", tmp_path)
    assert target.read_bytes() == b"previous archive"
    assert not list(tmp_path.glob("*.tmp"))


def test_archive_cannot_include_its_own_output(tmp_path: Path) -> None:
    folder = _build(tmp_path)
    with pytest.raises(ValueError, match="outside"):
        package_standalone.package_standalone(folder.parent, "1.2.3", folder)
    assert not list(folder.glob("*.zip")) and not list(folder.glob("*.tmp"))


def test_workflow_builds_uploads_downloads_and_attaches_the_standalone_zip() -> None:
    workflow = (_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "run: python tools/build_nuitka.py\n" in workflow
    assert "run: python tools/package_standalone.py --version" in workflow
    assert workflow.count("name: filetree-standalone") == 2
    assert "path: FileTree-*-windows-standalone.zip\n          if-no-files-found: error" in workflow
    assert "tools/publish_release.py" in workflow
    publisher = (_ROOT / "tools/publish_release.py").read_text(encoding="utf-8")
    assert 'f"FileTree-{version}.exe"' in publisher
    assert 'f"FileTree-{version}-windows-standalone.zip"' in publisher
