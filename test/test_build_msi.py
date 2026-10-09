"""MSI publication preserves complete runtime inventories and refuses partial/changed builds."""

from pathlib import Path
import subprocess
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest

from tools import build_msi as builder
from test_package_standalone import _build


def _compiler(monkeypatch, hook=None, version="6.0.2+fixture"):
    calls = []
    monkeypatch.setattr(builder.shutil, "which", lambda _name: "wix.exe")

    def run(command, **_kwargs):
        calls.append(command)
        if command[-1] == "--version":
            return SimpleNamespace(stdout=version)
        Path(command[command.index("-out") + 1]).write_bytes(b"compiled fixture MSI")
        if hook is not None:
            hook()
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(builder.subprocess, "run", run)
    return calls


def test_compile_preserves_all_payload_and_publishes_versioned_msi(tmp_path, monkeypatch):
    folder = _build(tmp_path)
    before = builder._inventory(folder)
    calls = _compiler(monkeypatch)
    result = builder.build_msi(folder.parent, "1.2.3", tmp_path)
    assert result.name == "FileTree-1.2.3-windows-x64.msi"
    assert result.read_bytes() == b"compiled fixture MSI"
    assert builder._inventory(folder) == before
    assert "Payload=" + str(folder) in calls[-1]
    assert calls[-1][calls[-1].index("-arch") + 1] == "x64"
    assert not any(value.startswith("-sice") or value == "-sval" for value in calls[-1])
    assert not list(tmp_path.glob("filetree-msi-*"))


@pytest.mark.parametrize("version", ["../bad", "1.2", "01.2.3", "256.0.0", "0.256.0", "0.0.65536",
                                     "1.2.3\n", "1.2.3 -d Other=evil", "1.2.3;evil"])
def test_invalid_msi_version_refuses_before_compiler(tmp_path, monkeypatch, version):
    _compiler(monkeypatch, lambda: pytest.fail("compiler must not run"))
    with pytest.raises(ValueError, match="version"):
        builder.build_msi(tmp_path, version, tmp_path)


def test_changed_payload_never_replaces_previous_artifact(tmp_path, monkeypatch):
    folder = _build(tmp_path)
    target = tmp_path / "FileTree-1.2.3-windows-x64.msi"
    target.write_bytes(b"previous")
    _compiler(monkeypatch, lambda: (folder / "Qt6Core.dll").write_bytes(b"changed"))
    with pytest.raises(OSError, match="changed"):
        builder.build_msi(folder.parent, "1.2.3", tmp_path)
    assert target.read_bytes() == b"previous" and not list(tmp_path.glob("filetree-msi-*"))


def test_failed_compiler_never_replaces_previous_artifact(tmp_path, monkeypatch):
    folder = _build(tmp_path)
    target = tmp_path / "FileTree-1.2.3-windows-x64.msi"
    target.write_bytes(b"previous")

    def fail():
        raise subprocess.CalledProcessError(1, "wix")

    _compiler(monkeypatch, fail)
    with pytest.raises(subprocess.CalledProcessError):
        builder.build_msi(folder.parent, "1.2.3", tmp_path)
    assert target.read_bytes() == b"previous" and not list(tmp_path.glob("filetree-msi-*"))


def test_wrong_compiler_version_refuses_before_build(tmp_path, monkeypatch):
    folder = _build(tmp_path)
    calls = _compiler(monkeypatch, version="7.0.0")
    with pytest.raises(ValueError, match="required"):
        builder.build_msi(folder.parent, "1.2.3", tmp_path)
    assert len(calls) == 1


def test_source_selection_and_output_scope_refuse(tmp_path, monkeypatch):
    folder = _build(tmp_path)
    _compiler(monkeypatch)
    with pytest.raises(ValueError, match="outside"):
        builder.build_msi(folder.parent, "1.2.3", folder)
    second = folder.parent / "other.dist"
    second.mkdir()
    (second / "FileTree.exe").write_bytes(b"other")
    with pytest.raises(ValueError, match="exactly one"):
        builder.build_msi(folder.parent, "1.2.3", tmp_path)


def test_payload_link_refuses_without_reading_target(tmp_path, monkeypatch):
    folder = _build(tmp_path)
    monkeypatch.setattr(builder, "_linked", lambda path: path.name == "Qt6Core.dll")
    with pytest.raises(ValueError, match="links"):
        builder._inventory(folder)


def test_package_has_stable_upgrade_identity_complete_runtime_and_no_custom_actions():
    root = ET.parse(builder._ROOT / "tools/installer/FileTree.wxs").getroot()  # noqa: S314 - checked-in fixed template
    namespace = {"w": "http://wixtoolset.org/schemas/v4/wxs"}
    package = root.find("w:Package", namespace)
    assert package.attrib["Scope"] == "perMachine"
    assert package.attrib["UpgradeCode"] == "1CF91EA0-1ED2-45CB-B2FC-A6F321F67B73"
    assert root.find(".//w:MajorUpgrade", namespace) is not None
    assert root.find(".//w:Files", namespace).attrib["Include"] == "$(Payload)\\**"
    assert root.find(".//w:File", namespace).attrib["Source"] == "$(Payload)\\FileTree.exe"
    assert root.find(".//w:Shortcut", namespace).attrib["Directory"] == "ProgramMenuFolder"
    assert root.find(".//w:CustomAction", namespace) is None


def test_release_and_native_fixture_validation_keep_msi_artifacts():
    workflow = (builder._ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "dotnet tool install wix --version 6.0.2" in workflow
    assert "python tools/build_msi.py --version" in workflow
    assert "name: filetree-msi" in workflow and "release-assets/*.msi" in workflow
    native = (builder._ROOT / "tools/validate_msi.ps1").read_text(encoding="utf-8")
    assert "$env:GITHUB_ACTIONS -ne 'true'" in native
    assert "Existing FileTree installation/shortcut/product found" in native
    assert "RelatedProducts($upgradeCode)" in native
    assert "Invoke-OwnedInstaller '/x'" in native and "-WindowStyle Hidden" in native
    assert "--version 1.2.4" in native and "Invoke-OwnedInstaller '/i' 'upgrade.log'" in native
    assert "$installer.ProductInfo($products[0], 'VersionString')" in native
