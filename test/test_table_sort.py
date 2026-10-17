"""Captured result sorting retains Qt order, filters and persistent row identity."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QItemSelectionModel, QPersistentModelIndex, QSortFilterProxyModel, Qt
from PySide6.QtWidgets import QApplication, QTableView
from PySide6.QtTest import QAbstractItemModelTester

from je_file_tree.core.node import Node
from je_file_tree.gui.tables import Column, LargestFilesModel, ProblemsModel, SORT_ROLE, TableProxy
from je_file_tree.gui.tree_model import NODE_ROLE


@pytest.fixture(scope="module")
def app():
    """Keep the application alive while Qt owns the models."""
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("descending", [False, True])
@pytest.mark.parametrize("column", [0, 1])
def test_problem_sort_matches_native_qt(app, descending, column):
    """Include codepoints whose Python and UTF-16 string orders differ."""
    rows = [(path, reason) for path, reason in zip(
        ["z", "A", "a", "\ue000", "\U0001f600", "a\u0301", "\u00e1", "a", ""],
        ["z", "a", "b", "a", "b", "c", "a", "a", "z"],
        strict=True,
    )]
    order = Qt.SortOrder.DescendingOrder if descending else Qt.SortOrder.AscendingOrder
    native_source, source = ProblemsModel(), ProblemsModel()
    native, proxy = QSortFilterProxyModel(), TableProxy()
    native.setSourceModel(native_source)
    native.setSortRole(SORT_ROLE)
    proxy.setSourceModel(source)
    native_source.set_rows(rows)
    source.set_rows(rows)
    assert native.rowCount() == len(rows)
    native.sort(column, order)
    proxy.sort(column, order)
    assert source.rows() == [native_source.row_at(native.mapToSource(native.index(row, 0)).row())
                             for row in range(native.rowCount())]
    assert proxy.rowCount() == len(rows)


def test_reset_reapplies_sort_and_filter(app):
    source, proxy = ProblemsModel(), TableProxy()
    proxy.setSourceModel(source)
    proxy.setFilterKeyColumn(0)
    proxy.setFilterFixedString("keep")
    proxy.sort(0, Qt.SortOrder.DescendingOrder)
    for rows in [[("keep-a", "x"), ("omit", "x"), ("keep-z", "x")],
                 [("keep-b", "x"), ("keep-y", "x"), ("omit", "x")]]:
        source.set_rows(rows)
        assert [proxy.index(row, 0).data() for row in range(proxy.rowCount())] == sorted(
            [path for path, _ in rows if "keep" in path], reverse=True)
    proxy.sort(-1)
    assert source.rows() == rows


def test_selection_and_duplicate_occurrences_survive_layout(app):
    source, proxy = ProblemsModel(), TableProxy()
    proxy.setSourceModel(source)
    shared = ("same", "reason")
    source.set_rows([("z", "x"), shared, ("a", "x"), shared])
    first = QPersistentModelIndex(source.index(1, 1))
    second = QPersistentModelIndex(source.index(3, 1))
    table = QTableView()
    table.setModel(proxy)
    selection = table.selectionModel()
    selection.select(proxy.index(3, 0), QItemSelectionModel.SelectionFlag.Select)
    proxy.sort(0)
    assert (first.row(), second.row()) == (1, 2)
    assert selection.selectedIndexes()[0].row() == 2
    proxy.sort(0, Qt.SortOrder.DescendingOrder)
    assert (first.row(), second.row()) == (1, 2)
    proxy.sort(-1)
    assert (first.row(), second.row()) == (1, 3)
    assert selection.selectedIndexes()[0].row() == 3
    table.setModel(None)


def test_sort_reads_each_key_once_and_refresh_preserves_node(app):
    source, proxy = LargestFilesModel(), TableProxy()
    proxy.setSourceModel(source)
    calls = []
    source._columns = (Column("column_size", lambda node: str(node.size),
                              lambda node: calls.append(node) or node.size),)
    nodes = [Node(str(i), False, size=i) for i in range(2000)]
    source.set_rows(nodes)
    proxy.sort(0, Qt.SortOrder.DescendingOrder)
    assert len(calls) == len(nodes)
    selected = QPersistentModelIndex(proxy.index(1999, 0))
    nodes[0].size = 5000
    calls.clear()
    source.refresh()
    assert len(calls) == len(nodes)
    assert selected.row() == 0
    assert selected.data(NODE_ROLE) is nodes[0]
    assert source.rows()[0] is nodes[0]


def test_repeated_column_sorts_and_replacement_match_qt(app):
    """Ties retain the previous display order; replacement starts a fresh row order."""
    source, reference = ProblemsModel(), ProblemsModel()
    proxy, native = TableProxy(), QSortFilterProxyModel()
    proxy.setSourceModel(source)
    native.setSourceModel(reference)
    native.setSortRole(SORT_ROLE)
    testers = [QAbstractItemModelTester(model, QAbstractItemModelTester.FailureReportingMode.Fatal)
               for model in (source, proxy)]
    rows = [("z", "b"), ("a", "b"), ("m", "a"), ("a", "c")]
    source.set_rows(rows)
    reference.set_rows(rows)
    assert native.rowCount() == len(rows)
    for column, order in [(0, Qt.AscendingOrder), (1, Qt.DescendingOrder),
                          (0, Qt.DescendingOrder), (1, Qt.AscendingOrder)]:
        proxy.sort(column, order)
        native.sort(column, order)
        assert source.rows() == [reference.row_at(native.mapToSource(native.index(row, 0)).row())
                                 for row in range(native.rowCount())]
    source.set_rows(list(reversed(rows)))
    reference.set_rows(list(reversed(rows)))
    assert source.rows() == [reference.row_at(native.mapToSource(native.index(row, 0)).row())
                             for row in range(native.rowCount())]
    source.sort(500)
    assert len(testers) == 2
