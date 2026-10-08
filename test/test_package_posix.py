"""Native desktop packaging preserves complete runtime/source and exclusively publishes checked output."""

import hashlib
import io
import json
import os
from pathlib import Path
import plistlib
import stat
from types import SimpleNamespace

import pytest

from tools import package_posix as packager


def _source(tmp_path, kind="linux"):
    root = tmp_path / ("FileTree.app" if kind == "macos" else "build/standalone/program.dist")
    root.mkdir(parents=True)
    names = ("FileTree", "libQt6Core.so.6", "libqxcb.so", *packager._CATALOGUES)
    if kind == "macos":
        names = ("Contents/MacOS/FileTree", "Contents/Frameworks/QtCore",
                 "Contents/PlugIns/libqcocoa.dylib", *packager._CATALOGUES)
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"owned compiler fixture")
        if path.name == "FileTree":
            path.chmod(0o755)
    return root


@pytest.mark.parametrize("kind", ["linux", "macos"])
def test_full_runtime_publishes_atomic_proof_without_launching(tmp_path, monkeypatch, kind):
    source = _source(tmp_path, kind)
    before = packager._inventory(source, links=kind == "macos")
    monkeypatch.setattr(packager, "sys", SimpleNamespace(platform="linux" if kind == "linux" else "darwin"))
    monkeypatch.setattr(packager.platform, "machine", lambda: "x86_64")
    def native(root, scratch, version, inventory):
        assert root == source and version == "1.2.3" and inventory == before
        artifact = scratch / "native-artifact"
        artifact.write_bytes(b"checked native artifact")
        return artifact
    monkeypatch.setattr(packager, "_appimage" if kind == "linux" else "_macos", native)
    target = packager.package_posix(kind, source, "1.2.3", tmp_path / "output")
    proof = json.loads((target.parent / "proof.json").read_text(encoding="utf-8"))
    assert proof["source_preserved"] and proof["extraction_verified"]
    assert not proof["app_launched"] and not proof["published"]
    assert proof["sha256"] == hashlib.sha256(target.read_bytes()).hexdigest()
    assert packager._inventory(source, links=kind == "macos") == before


@pytest.mark.parametrize("arrival", [False, True])
def test_source_changes_and_output_arrivals_never_publish_over_existing_entries(tmp_path, monkeypatch, arrival):
    source, output = _source(tmp_path), tmp_path / "output"
    monkeypatch.setattr(packager, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(packager.platform, "machine", lambda: "x86_64")
    def changed(_source, scratch, _version, _inventory):
        artifact = scratch / "artifact"
        artifact.write_bytes(b"native fixture")
        if arrival:
            output.mkdir()
            (output / "arrival").write_bytes(b"keep")
        else:
            (source / "FileTree").write_bytes(b"changed")
        return artifact
    monkeypatch.setattr(packager, "_appimage", changed)
    with pytest.raises(OSError):
        packager.package_posix("linux", source, "1.2.3", output)
    if arrival:
        assert (output / "arrival").read_bytes() == b"keep"
    else:
        assert not output.exists()
    assert not list(tmp_path.glob("filetree-posix-package-*"))


def test_incomplete_and_special_payloads_refuse_before_tools(tmp_path):
    source = _source(tmp_path)
    (source / "libqxcb.so").unlink()
    with pytest.raises(ValueError, match="lacks"):
        packager._complete(source, "linux")


def test_internal_framework_links_preserved_and_external_links_refused(tmp_path):
    source = _source(tmp_path, "macos")
    link = source / "Framework"
    try:
        link.symlink_to(Path("Contents") / "Frameworks", target_is_directory=True)
    except OSError as error:
        pytest.skip(f"Native symlink fixture unavailable: {error}")
    assert packager._inventory(source, links=True)["Framework"][0] == "link"
    with pytest.raises(ValueError, match="link"):
        packager._inventory(source, links=False)
    link.unlink()
    link.symlink_to("..", target_is_directory=True)
    with pytest.raises(ValueError, match="link"):
        packager._inventory(source, links=True)


@pytest.mark.parametrize("correct", [True, False])
def test_download_hash_is_verified_before_the_tool_can_run(tmp_path, monkeypatch, correct):
    contents = b"owned pinned tool fixture"
    checksum = hashlib.sha256(contents).hexdigest() if correct else "0" * 64
    monkeypatch.setattr(packager, "_ASSETS", {"tool": ("AppImage/appimagetool/1.9.1/tool", checksum)})
    requests = []
    def download(url, timeout):
        requests.append((url, timeout))
        return io.BytesIO(contents)
    monkeypatch.setattr(packager, "urlopen", download)
    if correct:
        assert packager._download("tool", tmp_path).read_bytes() == contents
    else:
        with pytest.raises(ValueError, match="checksum"):
            packager._download("tool", tmp_path)
    assert requests == [("https://github.com/AppImage/appimagetool/releases/download/1.9.1/tool", 30)]


def test_macos_metadata_and_native_extraction_preserve_the_full_bundle(tmp_path, monkeypatch):
    source, scratch = _source(tmp_path, "macos"), tmp_path / "scratch"
    scratch.mkdir()
    metadata = {"CFBundleIdentifier": "io.github.jechen.FileTree", "CFBundleShortVersionString": "1.2.3",
                "CFBundleExecutable": "FileTree"}
    (source / "Contents/Info.plist").write_bytes(plistlib.dumps(metadata))
    before, calls = packager._complete(source, "macos"), []
    def run(arguments, directory, environment=None):
        import shutil  # noqa: PLC0415 - fixture copying only
        calls.append(arguments)
        if "-c" in arguments:
            Path(arguments[-1]).write_bytes(b"native zip fixture")
        else:
            shutil.copytree(source, Path(arguments[-1]) / source.name)
    monkeypatch.setattr(packager, "_run", run)
    assert packager._macos(source, scratch, "1.2.3", before).is_file()
    assert all(arguments[0] == "/usr/bin/ditto" for arguments in calls)
    assert "--sequesterRsrc" in calls[0] and "--keepParent" in calls[0]
    metadata["CFBundleIdentifier"] = "foreign"
    (source / "Contents/Info.plist").write_bytes(plistlib.dumps(metadata))
    with pytest.raises(ValueError, match="metadata"):
        packager._macos(source, scratch, "1.2.3", before)


def test_linux_packaging_uses_pinned_runtime_and_preserves_all_extracted_dependencies(tmp_path, monkeypatch):
    import shutil  # noqa: PLC0415 - fixture copying only
    source = _source(tmp_path)
    (source.parent.parent / "FileTree.png").write_bytes(b"owned icon fixture")
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    calls = []
    def download(name, folder):
        path = folder / name
        path.write_bytes(b"owned fixture")
        return path
    def run(arguments, directory, environment=None):
        calls.append((arguments, environment))
        if "--runtime-file" in arguments:
            Path(arguments[-1]).write_bytes(b"owned image fixture")
        else:
            shutil.copytree(scratch / "FileTree.AppDir", directory / "squashfs-root")
    monkeypatch.setattr(packager, "_download", download)
    monkeypatch.setattr(packager, "_run", run)
    packager._appimage(source, scratch, "1.2.3", packager._complete(source, "linux"))
    assert calls[0][0][1:4] == ["--no-appstream", "--runtime-file", str(scratch / "runtime")]
    assert calls[0][1]["APPIMAGE_EXTRACT_AND_RUN"] == "1"
    assert calls[1][0][-1] == "--appimage-extract"
    appdir = scratch / "FileTree.AppDir"
    if os.name != "nt":
        assert (appdir / "AppRun").stat().st_mode & stat.S_IEXEC
    assert '"$APPDIR/usr/bin/filetree/FileTree" "$@"' in (appdir / "AppRun").read_text(encoding="utf-8")
