"""Store drafts bind real artifact hashes/product identity and refuse partial/changed releases."""

import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from tools import prepare_packages as packager

_PROPERTIES = {"ProductCode": "{00AB0000-1234-5678-9ABC-0123456789AB}",
               "UpgradeCode": "{1CF91EA0-1ED2-45CB-B2FC-A6F321F67B73}", "ProductVersion": "1.2.3",
               "ProductName": "FileTree", "Manufacturer": "JE-Chen", "ALLUSERS": "1", "Template": "x64;1033"}


def _assets(tmp_path, monkeypatch):
    msi = tmp_path / "FileTree-1.2.3-windows-x64.msi"
    msi.write_bytes(b"owned MSI fixture; native database is mocked")
    archive = tmp_path / "FileTree-1.2.3-windows-standalone.zip"
    with zipfile.ZipFile(archive, "w") as payload:
        for name in ("FileTree.exe", "PySide6/Qt6Core.dll", "PySide6/plugins/platforms/qwindows.dll",
                     "PySide6/translations/qtbase_zh_TW.qm", "PySide6/translations/qtbase_zh_CN.qm",
                     "PySide6/translations/qtbase_ja.qm", "PySide6/translations/qtbase_ko.qm"):
            payload.writestr("FileTree-1.2.3-windows-standalone/" + name, b"owned runtime fixture")
    monkeypatch.setattr(packager, "read_properties", lambda _path: dict(_PROPERTIES))
    return msi, archive


def test_drafts_use_complete_zip_real_checksums_and_native_product_without_publishing(tmp_path, monkeypatch):
    msi, archive = _assets(tmp_path, monkeypatch)
    before = msi.read_bytes(), archive.read_bytes()
    output = packager.prepare_drafts(tmp_path, "1.2.3", tmp_path / "drafts")
    proof = json.loads((output / "provenance.json").read_text(encoding="utf-8"))
    assert proof["published"] is False and proof["product_code"] == _PROPERTIES["ProductCode"]
    assert proof["msi_sha256"] == hashlib.sha256(before[0]).hexdigest()
    assert proof["zip_sha256"] == hashlib.sha256(before[1]).hexdigest()
    installer = (output / "winget/JEChen.FileTree.installer.yaml").read_text(encoding="utf-8")
    assert f'InstallerSha256: "{proof["msi_sha256"].upper()}"' in installer
    assert 'Scope: "machine"' in installer and 'InstallerType: "wix"' in installer
    assert f'ProductCode: "{proof["product_code"]}"' in installer
    scoop = json.loads((output / "scoop/je-file-tree.json").read_text(encoding="utf-8"))
    portable = scoop["architecture"]["64bit"]
    assert portable["hash"] == proof["zip_sha256"]
    assert portable["extract_dir"] == "FileTree-1.2.3-windows-standalone"
    assert portable["url"].endswith("/v1.2.3/" + archive.name)
    assert scoop["shortcuts"] == [["FileTree.exe", "FileTree"]]
    install = (output / "chocolatey/tools/chocolateyinstall.ps1").read_text(encoding="utf-8")
    assert f"checksum64 = '{proof['msi_sha256']}'" in install
    assert "checksumType64 = 'sha256'" in install and "Install-ChocolateyPackage @packageArgs" in install
    assert "silentArgs = '/qn /norestart'" in install and "validExitCodes = @(0, 3010)" in install
    assert (msi.read_bytes(), archive.read_bytes()) == before


@pytest.mark.parametrize("key,value", [("ProductVersion", "1.2.4"), ("ProductCode", "fake"),
                                     ("UpgradeCode", "{{1CF91EA0-1ED2-45CB-B2FC-A6F321F67B73}}"),
                                     ("ALLUSERS", ""), ("Template", "Intel;1033"),
                                     ("Manufacturer", "foreign"), ("ProductName", "foreign")])
def test_inconsistent_native_product_refuses_before_output(tmp_path, monkeypatch, key, value):
    _assets(tmp_path, monkeypatch)
    monkeypatch.setattr(packager, "read_properties", lambda _path: {**_PROPERTIES, key: value})
    with pytest.raises(ValueError, match="MSI"):
        packager.prepare_drafts(tmp_path, "1.2.3", tmp_path / "drafts")
    assert not (tmp_path / "drafts").exists()


def test_incomplete_zip_and_existing_output_refuse(tmp_path, monkeypatch):
    _msi, archive = _assets(tmp_path, monkeypatch)
    output = tmp_path / "drafts"
    output.mkdir()
    (output / "keep").write_bytes(b"existing output")
    with pytest.raises(FileExistsError):
        packager.prepare_drafts(tmp_path, "1.2.3", output)
    assert (output / "keep").read_bytes() == b"existing output"
    with zipfile.ZipFile(archive, "w") as payload:
        payload.writestr("FileTree-1.2.3-windows-standalone/FileTree.exe", b"partial")
    with pytest.raises(ValueError, match="runtime"):
        packager.prepare_drafts(tmp_path, "1.2.3", tmp_path / "partial")


@pytest.mark.parametrize("name", ["../arrival", "/absolute", "FileTree-1.2.3-windows-standalone/../bad",
                                  "FileTree-1.2.3-windows-standalone/stream:bad"])
def test_unsafe_archive_names_refuse_without_extracting(tmp_path, monkeypatch, name):
    _msi, archive = _assets(tmp_path, monkeypatch)
    with zipfile.ZipFile(archive, "a") as payload:
        payload.writestr(name, b"untrusted entry")
    with pytest.raises(ValueError, match="unsafe"):
        packager.prepare_drafts(tmp_path, "1.2.3", tmp_path / "drafts")


def test_changed_artifact_refuses_and_removes_only_owned_draft_scratch(tmp_path, monkeypatch):
    msi, _archive = _assets(tmp_path, monkeypatch)
    original = packager._chocolatey
    def changed(*arguments):
        original(*arguments)
        msi.write_bytes(b"changed source")
    monkeypatch.setattr(packager, "_chocolatey", changed)
    with pytest.raises(OSError, match="changed"):
        packager.prepare_drafts(tmp_path, "1.2.3", tmp_path / "drafts")
    assert not (tmp_path / "drafts").exists() and not list(tmp_path.glob("filetree-package-drafts-*"))


def test_output_arrival_is_never_overwritten(tmp_path, monkeypatch):
    _assets(tmp_path, monkeypatch)
    output = tmp_path / "drafts"
    original = packager._chocolatey
    def arrival(*arguments):
        original(*arguments)
        output.mkdir()
        (output / "arrival").write_bytes(b"preserved arrival")
    monkeypatch.setattr(packager, "_chocolatey", arrival)
    with pytest.raises(FileExistsError):
        packager.prepare_drafts(tmp_path, "1.2.3", output)
    assert (output / "arrival").read_bytes() == b"preserved arrival"


def test_linked_release_file_refuses_before_metadata(tmp_path, monkeypatch):
    _assets(tmp_path, monkeypatch)
    real = Path.lstat
    def linked(path):
        info = real(path)
        if path.name.endswith(".msi"):
            values = list(info)
            values[0] = 0o120777
            return type(info)(values)
        return info
    monkeypatch.setattr(Path, "lstat", linked)
    with pytest.raises(ValueError, match="ordinary"):
        packager.prepare_drafts(tmp_path, "1.2.3", tmp_path / "drafts")
