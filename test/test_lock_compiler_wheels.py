"""Compiler wheel locks keep exact versions and reject incomplete/untrusted release metadata."""

import io
import json

import pytest

from tools import lock_compiler_wheels as locker


def _metadata(version="1.2.3", digest="a" * 64):
    return {"info": {"version": version}, "urls": [
        {"packagetype": "sdist", "filename": "package.tar.gz", "digests": {"sha256": "b" * 64}},
        {"packagetype": "bdist_wheel", "filename": "package-win.whl", "digests": {"sha256": digest}},
        {"packagetype": "bdist_wheel", "filename": "package-linux.whl", "digests": {"sha256": "c" * 64}},
        {"packagetype": "bdist_wheel", "filename": "package-yanked.whl", "yanked": True,
         "digests": {"sha256": "d" * 64}}]}


def test_cross_platform_hashes_keep_existing_pins_and_exclude_source_and_yanked_releases(tmp_path, monkeypatch):
    directory = tmp_path / ".github/requirements"
    directory.mkdir(parents=True)
    lock = directory / "archives.txt"
    lock.write_text("package==1.2.3 --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8")
    requests = []
    def request(url, timeout):
        requests.append((url, timeout))
        return io.BytesIO(json.dumps(_metadata()).encode("utf-8"))
    monkeypatch.setattr(locker, "_ROOT", tmp_path)
    monkeypatch.setattr(locker, "urlopen", request)
    locker.regenerate(("archives",))
    contents = lock.read_text(encoding="utf-8")
    assert locker._pins(contents) == [("package", "1.2.3")]
    assert "a" * 64 in contents and "c" * 64 in contents
    assert "b" * 64 not in contents and "d" * 64 not in contents
    assert requests == [("https://pypi.org/pypi/package/1.2.3/json", 30)]
    assert not list(directory.glob("*.txt.*"))


@pytest.mark.parametrize("metadata", [_metadata(version="2.0.0"), _metadata(digest="bad"),
                                     {"info": {"version": "1.2.3"}, "urls": []}])
def test_inconsistent_release_metadata_never_rewrites_the_lock(tmp_path, monkeypatch, metadata):
    directory = tmp_path / ".github/requirements"
    directory.mkdir(parents=True)
    lock = directory / "photos.txt"
    original = "package==1.2.3 --hash=sha256:" + "a" * 64 + "\n"
    lock.write_text(original, encoding="utf-8")
    monkeypatch.setattr(locker, "_ROOT", tmp_path)
    monkeypatch.setattr(locker, "urlopen", lambda *_a, **_kw: io.BytesIO(json.dumps(metadata).encode("utf-8")))
    with pytest.raises(ValueError):
        locker.regenerate(("photos",))
    assert lock.read_text(encoding="utf-8") == original


def test_unknown_lock_or_duplicate_pin_refuses_before_network(monkeypatch):
    monkeypatch.setattr(locker, "urlopen", lambda *_a, **_kw: pytest.fail("Unexpected network request"))
    with pytest.raises(ValueError, match="Unknown"):
        locker.regenerate(("publish",))
    with pytest.raises(ValueError, match="unambiguous"):
        locker._pins("package==1.2.3\npackage==1.2.4\n")
