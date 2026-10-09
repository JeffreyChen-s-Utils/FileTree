"""Prepare reviewable Windows package-store drafts from actual versioned MSI/ZIP hashes; never submit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.build_msi import _version  # noqa: E402
from tools.msi_metadata import read_properties  # noqa: E402
from je_file_tree.core.no_replace import anchored_directory, directory_stamps, rename_no_replace  # noqa: E402

_REPOSITORY = "https://github.com/JeffreyChen-s-Utils/FileTree"
_IDENTIFIER = "JEChen.FileTree"
_SCHEMA = "1.12.0"
_UPGRADE = "1CF91EA0-1ED2-45CB-B2FC-A6F321F67B73"
_GUID = re.compile(r"\{[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}\}")
_DESCRIPTION = "View folder and drive usage as a tree, treemap and largest-file list."
_PACKAGE = "je-file-tree"


def _artifact(path: Path) -> tuple:
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400
            or not info.st_size):
        raise ValueError("Package draft inputs must be nonempty ordinary release files")
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, checksum.hexdigest()


def _zip_payload(path: Path, version: str) -> None:
    prefix = f"FileTree-{version}-windows-standalone"
    names = set()
    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            name, mode = PurePosixPath(entry.filename), stat.S_IFMT(entry.external_attr >> 16)
            if (name.is_absolute() or not name.parts or name.parts[0] != prefix or ".." in name.parts
                    or "\\" in entry.filename or ":" in entry.filename or entry.flag_bits & 1
                    or mode not in (0, stat.S_IFREG, stat.S_IFDIR) or entry.filename.casefold() in names):
                raise ValueError("Standalone ZIP contains unsafe, linked, encrypted or duplicate entries")
            names.add(entry.filename.casefold())
    required = ("FileTree.exe", "Qt6Core.dll", "qwindows.dll", "qtbase_zh_TW.qm", "qtbase_zh_CN.qm",
                "qtbase_ja.qm", "qtbase_ko.qm")
    leaves = [PurePosixPath(name).name for name in names if not name.endswith("/")]
    if (f"{prefix}/FileTree.exe".casefold() not in names
            or any(leaves.count(name.casefold()) != 1 for name in required)):
        raise ValueError("Standalone ZIP lacks a complete unambiguous runtime")


def _product(properties: dict[str, str], version: str) -> str:
    if (properties.get("ProductVersion") != version or properties.get("ProductName") != "FileTree"
            or properties.get("Manufacturer") != "JE-Chen" or properties.get("ALLUSERS") != "1"
            or properties.get("Template") != "x64;1033"
            or _GUID.fullmatch(properties.get("UpgradeCode", "")) is None
            or properties.get("UpgradeCode", "").strip("{}").upper() != _UPGRADE
            or _GUID.fullmatch(properties.get("ProductCode", "")) is None):
        raise ValueError("MSI version/product/platform/scope differs from the release contract")
    return "{" + str(uuid.UUID(properties["ProductCode"])).upper() + "}"


def _winget(version: str, installer: str, checksum: str, product: str) -> dict[str, dict]:
    common = {"PackageIdentifier": _IDENTIFIER, "PackageVersion": version}
    return {
        f"{_IDENTIFIER}.yaml": {**common, "DefaultLocale": "en-US", "ManifestType": "version",
                               "ManifestVersion": _SCHEMA},
        f"{_IDENTIFIER}.installer.yaml": {
            **common, "InstallerType": "wix", "Scope": "machine", "UpgradeBehavior": "install",
            "InstallModes": ["interactive", "silent", "silentWithProgress"],
            "Installers": [{"Architecture": "x64", "InstallerUrl": installer,
                            "InstallerSha256": checksum.upper(), "ProductCode": product}],
            "ManifestType": "installer", "ManifestVersion": _SCHEMA},
        f"{_IDENTIFIER}.locale.en-US.yaml": {
            **common, "PackageLocale": "en-US", "Publisher": "JE-Chen", "PackageName": "FileTree",
            "License": "MIT", "LicenseUrl": f"{_REPOSITORY}/blob/v{version}/LICENSE",
            "ShortDescription": _DESCRIPTION, "PackageUrl": _REPOSITORY,
            "ManifestType": "defaultLocale", "ManifestVersion": _SCHEMA},
    }


def _yaml(manifest: dict) -> str:
    lines = [f"# yaml-language-server: $schema=https://aka.ms/winget-manifest."
             f"{manifest['ManifestType']}.{_SCHEMA}.schema.json"]
    for key, value in manifest.items():
        if key == "Installers":
            lines.append("Installers:")
            for installer in value:
                for index, (field, scalar) in enumerate(installer.items()):
                    prefix = "  - " if index == 0 else "    "
                    lines.append(f"{prefix}{field}: {json.dumps(scalar)}")
        else:
            lines.append(f"{key}: {json.dumps(value)}")
    return "\n".join(lines) + "\n"


def _chocolatey(folder: Path, version: str, installer: str, checksum: str) -> None:
    namespace = "http://schemas.microsoft.com/packaging/2015/06/nuspec.xsd"
    ET.register_namespace("", namespace)
    package = ET.Element(f"{{{namespace}}}package")
    metadata = ET.SubElement(package, f"{{{namespace}}}metadata")
    for name, value in {"id": _PACKAGE, "version": version, "title": "FileTree", "authors": "JE-Chen",
                        "licenseUrl": f"{_REPOSITORY}/blob/v{version}/LICENSE", "projectUrl": _REPOSITORY,
                        "requireLicenseAcceptance": "false", "description": _DESCRIPTION,
                        "tags": "disk usage folder treemap"}.items():
        ET.SubElement(metadata, f"{{{namespace}}}{name}").text = value
    (folder / f"{_PACKAGE}.nuspec").write_bytes(ET.tostring(package, encoding="utf-8", xml_declaration=True))
    tools = folder / "tools"
    tools.mkdir()
    script = ("$ErrorActionPreference = 'Stop'\n$packageArgs = @{\n"
              f"    packageName = '{_PACKAGE}'\n    fileType = 'msi'\n    url64bit = '{installer}'\n"
              f"    checksum64 = '{checksum}'\n    checksumType64 = 'sha256'\n"
              "    silentArgs = '/qn /norestart'\n    validExitCodes = @(0, 3010)\n}\n"
              "Install-ChocolateyPackage @packageArgs\n")
    (tools / "chocolateyinstall.ps1").write_text(script, encoding="utf-8")


def _write_drafts(scratch: Path, version: str, artifacts: tuple, product: str) -> None:
    msi, archive, fingerprints = artifacts
    base = f"{_REPOSITORY}/releases/download/v{version}"
    installer, portable = f"{base}/{msi.name}", f"{base}/{archive.name}"
    winget, scoop, chocolatey = (scratch / name for name in ("winget", "scoop", "chocolatey"))
    for folder in (winget, scoop, chocolatey):
        folder.mkdir()
    for name, manifest in _winget(version, installer, fingerprints[0][-1], product).items():
        (winget / name).write_text(_yaml(manifest), encoding="utf-8")
    manifest = {"version": version, "description": _DESCRIPTION, "homepage": _REPOSITORY, "license": "MIT",
                "architecture": {"64bit": {"url": portable, "hash": fingerprints[1][-1],
                                            "extract_dir": f"FileTree-{version}-windows-standalone"}},
                "shortcuts": [["FileTree.exe", "FileTree"]]}
    (scoop / f"{_PACKAGE}.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _chocolatey(chocolatey, version, installer, fingerprints[0][-1])
    proof = {"version": version, "product_code": product, "upgrade_code": _UPGRADE,
             "msi_sha256": fingerprints[0][-1], "zip_sha256": fingerprints[1][-1], "published": False}
    (scratch / "provenance.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")


def prepare_drafts(source: Path, version: str, output: Path) -> Path:
    """Publish a fresh review folder only after actual artifact hashes/metadata/layout remain unchanged.

    MSI inspection is native read-only Windows database access. No credentials, network requests,
    installation, version changes or store submissions occur. URLs name the matching future release;
    drafts are not installable store listings until those exact release assets are published/reviewed.
    """
    _version(version)
    msi = source / f"FileTree-{version}-windows-x64.msi"
    archive = source / f"FileTree-{version}-windows-standalone.zip"
    before = _artifact(msi), _artifact(archive)
    product = _product(read_properties(msi), version)
    _zip_payload(archive, version)
    output = output.absolute().parent.resolve() / output.name
    if output.exists():
        raise FileExistsError("Package draft output must be a fresh directory")
    with (
        anchored_directory(directory_stamps(str(output.parent))) as descriptor,
        tempfile.TemporaryDirectory(prefix="filetree-package-drafts-", dir=output.parent) as temporary,
    ):
        scratch = Path(temporary)
        if not scratch.resolve().is_relative_to(output.parent):
            raise ValueError("Package draft scratch escaped its output parent")
        _write_drafts(scratch, version, (msi, archive, before), product)
        if (_artifact(msi), _artifact(archive)) != before:
            raise OSError("Release inputs changed while preparing package drafts")
        rename_no_replace(str(scratch), str(output), descriptor, descriptor)
    return output


def main() -> None:
    """Prepare unpublished drafts from local Windows release files without accessing store accounts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, default=Path("package-drafts"))
    args = parser.parse_args()
    try:
        result = prepare_drafts(args.source, args.version, args.output)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        parser.error(str(error))
    sys.stdout.write(str(result) + "\n")


if __name__ == "__main__":
    main()
