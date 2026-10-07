"""Capacity details show unknown values and disappear as soon as the tree changes."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from je_file_tree.core.scanner import scan
from je_file_tree.gui import i18n
from je_file_tree.gui.capacity_panel import CapacityPanel
from je_file_tree.gui.results_view import ResultsView
from je_file_tree.gui.scan_worker import analyse


@pytest.mark.parametrize("language", ["en", "zh-TW", "zh-CN"])
def test_capacity_details_display_scope_unknowns_and_retranslate(qapp: QApplication, tmp_path: Path, language) -> None:
    previous = i18n.current_language()
    i18n.set_language(language)
    root = scan(tmp_path).root
    panel = CapacityPanel()
    panel.set_ledger(analyse(scan(tmp_path)).capacity)
    panel.show()
    observed = []

    def inspect():
        dialog = QApplication.activeModalWidget()
        observed.extend(label.text() for label in dialog.findChildren(QLabel))
        dialog.accept()

    try:
        assert i18n.tr("capacity_folder_only") in panel.summary.text()
        QTimer.singleShot(0, inspect)
        QTest.mouseClick(panel.details, Qt.MouseButton.LeftButton)
        assert i18n.tr("capacity_row_unaccounted") in observed
        assert i18n.tr("size_unknown") in observed
        assert i18n.tr("capacity_bin_partial") in observed
        assert panel.ledger.coverage.known_bytes == root.size
    finally:
        panel.close()
        i18n.set_language(previous)


def test_capacity_snapshot_is_invalidated_by_moves_and_branch_rescans(qapp: QApplication, tmp_path: Path) -> None:
    folder = tmp_path / "branch"
    folder.mkdir()
    (folder / "file").write_bytes(b"data")
    view = ResultsView()
    try:
        outcome = analyse(scan(tmp_path))
        view.show_outcome(outcome)
        assert view.capacity.ledger is outcome.capacity
        old = outcome.result.root.children[0]
        view.replace_branch(old, scan(folder))
        assert view.capacity.ledger is None and view.outcome.capacity is None
        view.show_outcome(analyse(scan(tmp_path)))
        file = view.outcome.result.root.children[0].children[0]
        view.forget([file])
        assert view.capacity.ledger is None and view.outcome.capacity is None
        view.begin_scan()
        assert view.capacity.isHidden()
    finally:
        view.cleanup.stop(wait=True)
        view.search.stop(wait=True)
        view.duplicates.stop(wait=True)
        view.changes.stop(wait=True)
        view.wait_for_lists()
        view.close()
