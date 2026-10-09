"""Installer reports are optional metadata; only exact recorded folders provide measured totals."""

from dataclasses import replace
import json
import os
import threading
from types import SimpleNamespace

import pytest

from je_file_tree.core import programs
from je_file_tree.core.programs import Program, Programs, installed_programs
from je_file_tree.core.scanner import scan
from je_file_tree.core.snapshot import pack_snapshot, unpack_snapshot


def _providers(monkeypatch, rows=()):
    monkeypatch.setattr(programs, "registered_programs", lambda **_kwargs: Programs(list(rows), len(rows), 0))
    monkeypatch.setattr(programs, "_external_epic", lambda _cancel: ([], 0))


def _steam(root, *, folder="中文 Game", name='中文 "Game" {', appid="42"):
    common = root / "steamapps" / "common" / folder
    common.mkdir(parents=True)
    (common / "payload").write_bytes(b"game" * 1024)
    manifest = root / "steamapps" / "appmanifest_42.acf"
    escaped = name.replace('"', '\\"')
    manifest.write_text(f'"AppState" {{ "appid" "{appid}" "name" "{escaped}" '
                        f'"installdir" "{folder}" "buildid" "123" "nested" {{ "key" "value" }} }}\n',
                        encoding="utf-8")
    return common, manifest


def test_registry_reports_match_exact_folders_without_extra_filesystem_reads(tmp_path, monkeypatch):
    matched = tmp_path / "installed"
    matched.mkdir()
    (matched / "data").write_bytes(b"x" * 4096)
    rows = [Program("Known", "1", "Publisher", "registry", str(matched), 999999),
            Program("Missing", "", "", "registry", str(tmp_path / "installed-more"), None)]
    _providers(monkeypatch, rows)
    root = scan(tmp_path).root
    monkeypatch.setattr(programs.os, "scandir", lambda *_args: pytest.fail("Install folders must not be rescanned"))
    result = installed_programs(root)
    known = next(row for row in result.rows if row.name == "Known")
    assert known.node.size == 4096 and known.reported == 999999 and known.complete
    assert next(row for row in result.rows if row.name == "Missing").node is None
    assert not installed_programs(root, partial=True).rows[0].complete


def test_steam_and_epic_names_use_snapshot_guarded_manifests_and_exact_install_locations(tmp_path, monkeypatch):
    _providers(monkeypatch)
    common, _manifest = _steam(tmp_path)
    epic = tmp_path / "EpicGamesLauncher" / "Data" / "Manifests"
    epic.mkdir(parents=True)
    (epic / "owned.item").write_text(json.dumps({"DisplayName": "Epic 中文", "InstallLocation": str(common),
                                               "InstallSize": 8192, "AppVersionString": "v2"}), encoding="utf-8")
    result = installed_programs(scan(tmp_path).root)
    assert result.count == 2 and result.issues == 0
    assert {row.name for row in result.rows} == {'中文 "Game" {', "Epic 中文"}
    assert all(row.node.size == 4096 and row.complete for row in result.rows)
    steam = next(row for row in result.rows if row.source == "steam")
    assert steam.version == "123" and steam.reported is None
    # Selecting steamapps itself must still recognize its directly contained manifests.
    assert installed_programs(scan(tmp_path / "steamapps").root).rows[0].name == steam.name
    assert programs._key_values('"AppState" { "name" "{" "installdir" "}" }')["AppState"]["name"] == "{"


@pytest.mark.parametrize("bad", ["wrong_id", "descendant_escape", "duplicate_key", "truncated", "changed"])
def test_bad_or_changed_game_metadata_never_supplies_a_named_installation(tmp_path, monkeypatch, bad):
    _providers(monkeypatch)
    _common, manifest = _steam(tmp_path)
    if bad == "wrong_id":
        manifest.write_text(manifest.read_text(encoding="utf-8").replace('"42"', '"43"'), encoding="utf-8")
    elif bad == "descendant_escape":
        changed = manifest.read_text(encoding="utf-8").replace('"中文 Game"', '"../escape"')
        manifest.write_text(changed, encoding="utf-8")
    elif bad == "duplicate_key":
        manifest.write_text('"AppState" { "appid" "42" "appid" "42" }', encoding="utf-8")
    elif bad == "truncated":
        manifest.write_text('"AppState" { "appid" "42"', encoding="utf-8")
    root = scan(tmp_path).root
    if bad == "changed":
        manifest.write_text("changed after scan", encoding="utf-8")
    result = installed_programs(root)
    assert result.rows == [] and result.issues == 1


def test_known_cloud_metadata_is_refused_before_opening(tmp_path, monkeypatch):
    _providers(monkeypatch)
    _common, manifest = _steam(tmp_path)
    root = scan(tmp_path).root
    node = next(node for node in root.iter_files() if node.name == manifest.name)
    info = unpack_snapshot(node.snapshot)
    stat_info = SimpleNamespace(st_dev=info.device, st_ino=info.inode, st_size=info.size,
                                st_mode=info.mode, st_mtime_ns=info.modified_ns, st_ctime_ns=info.changed_ns,
                                st_nlink=info.links, st_file_attributes=0x40000)
    node.snapshot = pack_snapshot(stat_info)
    monkeypatch.setattr(programs, "stat_snapshot", lambda _path: node.snapshot)
    monkeypatch.setattr(programs, "open", lambda *_args: pytest.fail("Cannot hydrate known cloud metadata"),
                        raising=False)
    result = installed_programs(root)
    assert result.rows == [] and result.issues == 1


def test_registry_optional_fields_size_units_and_no_uninstall_command_queries(monkeypatch):
    fields = {"DisplayName": "Native sample", "EstimatedSize": 42, "InstallLocation": os.path.abspath("owned")}
    queried = []

    def query(_key, name):
        queried.append(name)
        assert "UninstallString" not in name
        if name not in fields:
            raise FileNotFoundError(name)
        return fields[name], 1

    fake = SimpleNamespace(QueryValueEx=query)
    monkeypatch.setattr(programs, "winreg", fake, raising=False)
    row = programs._registration(object())
    assert row.reported == 42 * 1024 and row.version == "" and row.publisher == ""
    fields["EstimatedSize"] = True
    assert programs._registration(object()).reported is None
    fields["SystemComponent"] = 1
    assert programs._registration(object()) is None
    assert queried


def test_registration_views_deduplicate_without_writes_and_preserve_unavailable_counts(monkeypatch):
    row = Program("Sample", "v1", "Publisher", "registry", os.path.abspath("owned"), 4096)
    calls = []
    fake = SimpleNamespace(HKEY_LOCAL_MACHINE=1, HKEY_CURRENT_USER=2, KEY_WOW64_64KEY=64, KEY_WOW64_32KEY=32)
    monkeypatch.setattr(programs, "winreg", fake, raising=False)
    monkeypatch.setattr(programs, "sys", SimpleNamespace(platform="win32"))

    def view(hive, flags, _cancel):
        calls.append((hive, flags))
        return [row], int(hive == 2)

    monkeypatch.setattr(programs, "_registry_view", view)
    result = programs.registered_programs()
    assert result.rows == [row] and result.count == 1 and result.issues == 2
    assert calls == [(1, 64), (1, 32), (2, 64), (2, 32)]
    cancel = threading.Event()
    cancel.set()
    assert programs.registered_programs(cancel=cancel) is None


def test_external_epic_metadata_is_read_for_other_drive_scan_and_deduplicates_scanned_manifest(tmp_path, monkeypatch):
    data = tmp_path / "ProgramData"
    directory = data / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    directory.mkdir(parents=True)
    installed = tmp_path / "Game"
    installed.mkdir()
    (installed / "data").write_bytes(b"x" * 4096)
    (directory / "owned.item").write_text(json.dumps({"DisplayName": "Epic game", "InstallLocation": str(installed),
                                                     "InstallSize": True}), encoding="utf-8")
    monkeypatch.setenv("PROGRAMDATA", str(data))
    monkeypatch.setattr(programs, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(programs, "registered_programs", lambda **_kwargs: Programs([], 0, 0))
    result = installed_programs(scan(installed).root)
    assert result.count == 1 and result.rows[0].node.size == 4096 and result.rows[0].reported is None
    result = installed_programs(scan(tmp_path).root)
    assert result.count == 1 and result.issues == 0


def test_bounded_rows_complete_count_and_cancel(tmp_path, monkeypatch):
    row = Program("Sample", "", "", "registry", "", 1)
    _providers(monkeypatch, [replace(row, name=f"App {number}", reported=number) for number in range(1002)])
    result = installed_programs(scan(tmp_path).root)
    assert len(result.rows) == 1000 and result.count == 1002 and result.rows[0].reported == 1001
    cancel = threading.Event()
    root = scan(tmp_path).root
    monkeypatch.setattr(programs, "give_way", cancel.set)
    assert installed_programs(root, cancel=cancel) is None
