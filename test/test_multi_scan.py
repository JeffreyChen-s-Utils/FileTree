"""Multiple roots retain physical source paths, partial coverage and no synthetic filesystem authority."""

import csv
import json
import os
import threading

import pytest

from je_file_tree.core import capacity, export
from je_file_tree.core.analysis import summarise
from je_file_tree.core.cleanup import empty_folders, find_cleanup
from je_file_tree.core.compare import SavedScanError, compare, load_saved
from je_file_tree.core.coverage import coverage_of
from je_file_tree.core.history import ScanHistory
from je_file_tree.core.multi_scan import scan_roots
from je_file_tree.core.operations import revalidate
from je_file_tree.core.scanner import NOT_SCANNED, ScanCancelledError, ScanOptions


@pytest.fixture
def sources(tmp_path):
    roots = [tmp_path / "b", tmp_path / "a-longer-name"]
    for number, root in enumerate(roots, 1):
        root.mkdir()
        (root / "資料.txt").write_bytes(b"x" * number)
        (root / "empty").mkdir()
    return roots


def test_virtual_root_retains_all_source_paths_and_sorted_totals(sources):
    received = []
    result = scan_roots(sources, on_root=received.append)
    root = result.root
    assert received == [root] and root.path is None and root.snapshot is None
    assert root.size == 3 and root.file_count == 2 and root.dir_count == 4
    assert [child.path for child in root.children] == [str(sources[1]), str(sources[0])]
    assert {node.path for node in root.iter_files()} == {str(path / "資料.txt") for path in sources}
    assert all(node.is_in(root) for node in root.iter_nodes())
    assert summarise(root).largest[0].size == 2 and coverage_of(root).complete


def test_duplicate_and_ordinary_nested_roots_do_not_count_data_twice(sources):
    root = sources[0]
    result = scan_roots([root / "empty", root, root])
    assert len(result.root.children) == 1 and result.root.size == 1
    assert result.root.children[0].path == str(root)


@pytest.mark.parametrize("value", [[], "folder", ["folder"] * 257])
def test_invalid_root_inventory_refuses_before_scan(value):
    with pytest.raises(ValueError, match="explicit roots"):
        scan_roots(value)


def test_failed_root_retains_incomplete_coverage_and_never_becomes_empty_cleanup(sources, tmp_path):
    missing = tmp_path / "missing"
    result = scan_roots([sources[0], missing])
    coverage = coverage_of(result.root)
    failure = next(child for child in result.root.children if child.path == str(missing))
    assert result.errors and failure.error and not coverage.complete
    assert not coverage.can_clean(failure) and failure not in empty_folders(result.root)
    assert all(failure not in group.nodes for group in find_cleanup(result.root))


def test_cancel_preserves_completed_data_and_pending_roots(sources):
    cancel = threading.Event()
    def progress(value):
        if value.files:
            cancel.set()
    with pytest.raises(ScanCancelledError) as caught:
        scan_roots(sources, cancel=cancel, progress=progress)
    partial = caught.value.partial
    assert partial.root.size > 0 and len(partial.root.children) == 2
    assert any(child.error == NOT_SCANNED for child in partial.root.children)
    assert not coverage_of(partial.root).complete


def test_hard_link_accounting_is_applied_across_all_roots(sources):
    for root in sources:
        (root / "資料.txt").unlink()
    original, alias = sources[0] / "original", sources[1] / "alias"
    original.write_bytes(b"same payload")
    os.link(original, alias)
    result = scan_roots(sources, options=ScanOptions(count_hard_links=True))
    assert result.hard_links.aliases == 1
    assert result.root.size == 2 * original.stat().st_size
    assert result.root.accounted_size == original.stat().st_size
    assert result.root.children[0].parent is result.root


def test_virtual_capacity_has_no_os_totals_and_mutation_has_no_authority(sources, monkeypatch, tmp_path):
    root = scan_roots(sources).root
    monkeypatch.setattr(capacity.shutil, "disk_usage", lambda _path: pytest.fail("Virtual capacity queried OS"))
    ledger = capacity.capacity_ledger(root)
    assert ledger.status == "multiple_roots" and ledger.total is ledger.used is ledger.free is None
    assert ledger.unique_allocated == ledger.named_allocated and ledger.unaccounted is None
    assert revalidate(next(root.iter_files()), root) == "outside"
    store = ScanHistory(tmp_path / "never-created")
    with pytest.raises(ValueError, match="individual source roots"):
        store.save(root)
    assert not store.directory.exists()


def test_exports_and_saved_comparison_preserve_pathless_root_and_absolute_sources(sources, tmp_path):
    root = scan_roots(sources).root
    target, table = tmp_path / "multiple.json", tmp_path / "multiple.csv"
    export.export_json(root, target)
    export.export_folders_csv(root, table)
    document = json.loads(target.read_text(encoding="utf-8"))
    assert document["root"]["name"] == "" and document["root"]["virtual"] is True
    saved = load_saved(target)
    assert saved.root is None and saved.size == 3 and compare(root, saved) == []
    with table.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert rows[0]["path"] == "" and {row["path"] for row in rows[1:]} >= {str(path) for path in sources}
    (sources[0] / "資料.txt").write_bytes(b"growth")
    assert compare(scan_roots(sources).root, saved)[0].path == ""


@pytest.mark.parametrize("name,marker", [("", False), ("physical", True), ("", "true")])
def test_saved_virtual_marker_cannot_claim_a_physical_root(tmp_path, name, marker):
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps({"format": export.JSON_FORMAT, "root": {"name": name, "virtual": marker,
                                                                         "size": 0}}), encoding="utf-8")
    with pytest.raises(SavedScanError, match="virtual root"):
        load_saved(path)
