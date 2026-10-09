"""Counted chart/export totals stay separate from file lengths and mutations rebuild full scopes."""

import csv
import json
import os

from PySide6.QtCore import Qt

from test_gui import _wait
from test_gui import window as window  # noqa: PLC0414
from je_file_tree import cli
from je_file_tree.core import export, sunburst, treemap
from je_file_tree.core.analysis import summarise
from je_file_tree.core.compare import compare, load_saved
from je_file_tree.core.report import prepare_report
from je_file_tree.core.scanner import ScanOptions, scan
from je_file_tree.core.operations import MoveResult
from je_file_tree.gui.report_dialog import _labels
from je_file_tree.gui.scan_worker import ScanWorker, analyse
from je_file_tree.gui.tree_model import ACCOUNTED_ALLOCATED, ACCOUNTED_SIZE, SIZE


def _root(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a").mkdir()
    (source / "z").mkdir()
    first = source / "a" / "kept.txt"
    second = source / "z" / "alias.txt"
    first.write_bytes(b"owned" * 1024)
    os.link(first, second)
    return scan(source, options=ScanOptions(count_hard_links=True)).root


def test_columns_summary_charts_and_named_largest_sizes(window, tmp_path):
    root = _root(tmp_path)
    outcome = analyse(scan(root.path, options=ScanOptions(count_hard_links=True)))
    window.results.show_outcome(outcome)
    root = outcome.result.root
    alias = next(node for node in root.iter_files() if node.accounted_size == 0)
    model = window.results.tree_model
    index = model.index_for(alias)
    assert index.siblingAtColumn(SIZE).data() != index.siblingAtColumn(ACCOUNTED_SIZE).data()
    assert index.siblingAtColumn(ACCOUNTED_SIZE).data() == "0 B"
    assert index.siblingAtColumn(ACCOUNTED_ALLOCATED).data() == "0 B"
    assert window.results.tree.isColumnHidden(ACCOUNTED_SIZE)
    window.results.tree_columns.set_visible(ACCOUNTED_SIZE, True)
    assert not window.results.tree.isColumnHidden(ACCOUNTED_SIZE)
    assert "Counted:" in window.results.summary.text() and "1 observed aliases" in window.results.summary.text()
    assert len(outcome.largest) == 2 and all(node.size == 5120 for node in outcome.largest)
    assert sum(item.size for item in outcome.categories) == 10240
    assert sum(item.size for item in outcome.chart_categories) == 5120
    legend = window.results._legend.text().replace("\u2060", "").replace("\xa0", " ")
    assert "5.0 KB" in legend and "10.0 KB" not in legend
    tiles = treemap.layout(root, treemap.Rect(0, 0, 500, 500), max_depth=4)
    assert all(tile.node is not alias for tile in tiles)
    assert all(segment.node is not alias for segment in sunburst.layout(root))
    assert index.siblingAtColumn(ACCOUNTED_SIZE).data(Qt.ItemDataRole.ToolTipRole)


def test_persisted_scan_option_is_captured_and_branch_rescan_uses_whole_root(window, tmp_path, monkeypatch):
    root = _root(tmp_path)
    window._actions["count_hard_links"].setChecked(True)
    assert window.settings.value("count_hard_links", type=bool)
    old_worker = ScanWorker(root.path, window._scan_options(), window)
    window._actions["count_hard_links"].setChecked(False)
    assert old_worker._options.count_hard_links and not window._scan_options().count_hard_links
    window.results.show_outcome(analyse(scan(root.path, options=ScanOptions(count_hard_links=True))))
    root = window.results.outcome.result.root
    calls = []
    monkeypatch.setattr(window, "start_scan", lambda path, **kwargs: calls.append((path, kwargs)))
    window.rescan_folder(root.children[0], exact_allocation=True)
    assert calls == [(root.path, {"exact_allocation": True})]
    assert not window._trash_rescans
    old_worker.deleteLater()


def test_counted_exports_preserve_named_saved_comparison_and_report_rows(tmp_path):
    root = _root(tmp_path)
    target, folders, files = tmp_path / "tree.json", tmp_path / "folders.csv", tmp_path / "files.csv"
    export.export_json(root, target)
    export.export_folders_csv(root, folders)
    export.export_files_csv(root.iter_files(), files)
    data = json.loads(target.read_text(encoding="utf-8"))["root"]
    assert data["size"] == 10240 and data["accounted_size"] == 5120
    assert not any(change.change for change in compare(root, load_saved(target)))
    with files.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert [int(row["size_bytes"]) for row in rows] == [5120, 5120]
    assert sum(int(row["accounted_size_bytes"]) for row in rows) == 5120
    assert all(row["hard_link_accounting"] == "1" for row in rows)
    with folders.open(encoding="utf-8-sig", newline="") as stream:
        assert next(csv.DictReader(stream))["accounted_size_bytes"] == "5120"
    report = prepare_report(root, summarise(root), _labels())
    assert dict(report.tables[0].rows)["Counted size"] == 5120
    assert all(row[1] == 5120 for row in report.tables[2].rows)
    assert sum(row[-2] for row in report.tables[2].rows) == 5120
    old_labels = _labels()
    del old_labels["accounted_bytes"], old_labels["accounted_allocated"]
    old_report = prepare_report(root, summarise(root), old_labels)
    assert len(old_report.tables[2].header) == 7
    assert all(len(row) == 7 for row in old_report.tables[2].rows)


def test_cli_flag_reports_named_and_counted_totals(tmp_path, capsys):
    root = _root(tmp_path)
    assert cli.main(["scan", root.path, "--count-hard-links"]) == cli.OK
    data = json.loads(capsys.readouterr().out)
    assert data["logical_bytes"] == 10240 and data["accounted_logical_bytes"] == 5120
    assert data["hard_link_accounting"]["aliases"] == 1


def test_move_completion_rebuilds_root_and_transfers_counted_name(window, qapp, tmp_path):
    root = _root(tmp_path)
    window._actions["count_hard_links"].setChecked(True)
    window.results.show_outcome(analyse(scan(root.path, options=ScanOptions(count_hard_links=True))))
    root = window.results.outcome.result.root
    counted = next(node for node in root.iter_files() if node.accounted_size > 0)
    parent = counted.parent
    os.unlink(counted.path)  # Only this newly created disposable pytest fixture; no user entry/bin.
    window._trash_finished(MoveResult(moved=[counted], parents=[parent]))
    _wait(qapp, lambda: window._worker is None and window.results.outcome is not None
          and window.results.outcome.result.root is not root)
    result = window.results.outcome.result
    assert result.root.file_count == 1 and result.root.accounted_size == result.root.size == 5120
    remaining = next(result.root.iter_files())
    assert remaining.name == "alias.txt" and remaining.accounted_size == 5120
    assert result.hard_links.aliases == 0
