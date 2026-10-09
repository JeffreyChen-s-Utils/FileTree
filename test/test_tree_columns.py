"""Persistent column choices and volume shares do not disturb live node indexes."""

from dataclasses import replace

import pytest
from PySide6.QtCore import QPersistentModelIndex, QSettings, Qt

from je_file_tree.core.capacity import capacity_ledger
from je_file_tree.core.scanner import scan
from je_file_tree.core.snapshot import unpack_snapshot
from je_file_tree.gui.i18n import tr
from je_file_tree.gui.results_view import ResultsView
from je_file_tree.gui.scan_worker import analyse
from je_file_tree.gui.tree_model import DRIVE_SHARE, NAME, SHARE_ROLE, SIZE, FolderTreeModel


def test_optional_columns_remember_choices_but_name_stays_visible(qapp, tmp_path) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    first = ResultsView(settings=settings)
    assert first.tree.columnWidth(NAME) >= 200 and first.tree.isColumnHidden(DRIVE_SHARE)
    menu = first.tree_columns.menu()
    assert not menu.actions()[NAME].isEnabled()
    menu.actions()[DRIVE_SHARE].trigger()
    menu.actions()[SIZE].trigger()
    second = ResultsView(settings=settings)
    assert not second.tree.isColumnHidden(DRIVE_SHARE) and second.tree.isColumnHidden(SIZE)
    second.tree_columns.set_visible(NAME, False)
    assert not second.tree.isColumnHidden(NAME)
    second.tree_columns.reset()
    assert second.tree.isColumnHidden(DRIVE_SHARE) and not second.tree.isColumnHidden(SIZE)
    first.deleteLater()
    second.deleteLater()
    menu.deleteLater()


def test_invalid_column_settings_use_the_readable_default(qapp, tmp_path) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    for value in ('["column_removed"]', '{"unexpected":1}', '[', '[1]'):
        settings.setValue("tree_visible_columns", value)
        view = ResultsView(settings=settings)
        assert not view.tree.isColumnHidden(SIZE) and view.tree.isColumnHidden(DRIVE_SHARE)
        view.deleteLater()


def test_volume_share_uses_logical_bytes_and_preserves_persistent_indexes(qapp, tmp_path) -> None:
    (tmp_path / "file").write_bytes(b"bytes")
    root = scan(tmp_path).root
    model = FolderTreeModel()
    model.set_root(root)
    node = root.children[0]
    index = model.index_for(node).siblingAtColumn(DRIVE_SHARE)
    persistent = QPersistentModelIndex(index)
    assert index.data() == tr("size_unknown")
    model.set_drive_total(100)
    assert index.data(SHARE_ROLE) == pytest.approx(.05)
    assert "5" in index.data() and persistent.data() == index.data()
    info = unpack_snapshot(node.snapshot)
    node.snapshot = (info.device + 1).to_bytes(8, "little") + node.snapshot[8:]
    assert index.data(SHARE_ROLE) is None and index.data() == tr("size_unknown")
    model.set_drive_total(None)
    assert persistent.isValid() and persistent.data() == tr("size_unknown")


def test_branch_changes_invalidate_drive_share_until_new_capacity(qapp, tmp_path) -> None:
    folder = tmp_path / "branch"
    folder.mkdir()
    (folder / "file").write_bytes(b"bytes")
    outcome = analyse(scan(tmp_path))
    ledger = replace(capacity_ledger(outcome.result.root), total=100)
    view = ResultsView()
    view.show_outcome(replace(outcome, capacity=ledger))
    assert view.tree_model.index(0, DRIVE_SHARE).data(SHARE_ROLE) == pytest.approx(.05)
    branch = outcome.result.root.children[0]
    view.replace_branch(branch, scan(folder))
    assert view.tree_model.index(0, DRIVE_SHARE).data(SHARE_ROLE) is None
    view.set_capacity(ledger)
    assert view.tree_model.index(0, DRIVE_SHARE).data(SHARE_ROLE) == pytest.approx(.05)
    view.tree_model.sort(DRIVE_SHARE, Qt.SortOrder.AscendingOrder)
    view.cleanup.stop(wait=True)
    view.duplicates.stop(wait=True)
    view.search.stop(wait=True)
    view.changes.stop(wait=True)
    view.deleteLater()
