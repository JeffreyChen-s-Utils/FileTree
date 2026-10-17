"""Selected list preparation yields without changing native complete-row semantics."""

import random

from PySide6.QtCore import (
    QCoreApplication, QEvent, QItemSelection, QItemSelectionModel, QObject, QSortFilterProxyModel, Qt,
)
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QTableView, QTreeView
import pytest

from je_file_tree.core.node import Node
from je_file_tree.gui import grouped_list, list_transfer as transfer


@pytest.mark.parametrize("fragmented", [False, True])
def test_first_selected_capture_turn_bounds_native_flag_queries(qapp, monkeypatch, fragmented):
    class Counted(grouped_list.GroupedListModel):
        calls = 0

        def flags(self, index):
            self.calls += 1
            return super().flags(index)

    model = Counted()
    model.set_groups([('owned', [Node(str(row), False) for row in range(4096)])], 'auto')
    view = grouped_list.build_view(model)
    parent = model.index(0, 0)
    selection = QItemSelection()
    if fragmented:
        for row in range(0, 4096, 2):
            selection.select(model.index(row, 0, parent), model.index(row, 3, parent))
    else:
        selection.select(model.index(0, 0, parent), model.index(4095, 3, parent))
    view.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    monkeypatch.setattr(transfer, '_CHUNK_ROWS', 7)
    monkeypatch.setattr(transfer, '_CHUNK_SECONDS', 10)
    capture = transfer.ListCapture(view, view, selected=True)
    model.calls = 0
    capture.start()
    capture._timer.stop()
    try:
        capture._chunk()
        assert model.calls < 128, model.calls
        assert capture._active and not capture._complete and len(capture.rows) <= 7
    finally:
        capture.cancel()
        view.deleteLater()


def _table():
    model = QStandardItemModel()
    model.setHorizontalHeaderLabels(['Name', 'Value', 'Other'])
    for row in range(8):
        model.appendRow([QStandardItem(str(row)), QStandardItem(f'v{row}'), QStandardItem(f'x{row}')])
    view = QTableView()
    view.setModel(model)
    return view, model


def _finish(capture, limit=10000):
    ready = []
    capture.ready.connect(lambda header, rows: ready.append((header, list(rows))))
    capture.start()
    for _ in range(limit):
        capture._timer.stop()
        capture._chunk()
        if not capture._active:
            break
    assert len(ready) == 1 and not capture._active
    return ready[0]


@pytest.mark.parametrize("case", ['partial', 'disabled', 'all-disabled', 'proxy', 'tree'])
def test_selected_capture_matches_native_rows_cells_and_order(qapp, monkeypatch, case):
    view, source = _table()
    proxy = None
    if case == 'proxy':
        proxy = QSortFilterProxyModel()
        proxy.setSourceModel(source)
        proxy.sort(0, Qt.SortOrder.DescendingOrder)
        view.setModel(proxy)
    elif case == 'tree':
        source.item(1).appendRow([QStandardItem('nested'), QStandardItem('n'), QStandardItem('child')])
        view.deleteLater()
        view = QTreeView()
        view.setModel(source)
    model = view.model()
    chosen = QItemSelection()
    chosen.select(model.index(5, 0), model.index(6, 2))
    chosen.select(model.index(1, 0), model.index(1, 0))
    chosen.select(model.index(1, 2), model.index(1, 2))
    chosen.select(model.index(3, 1), model.index(3, 2))
    if case == 'disabled':
        source.item(1, 1).setFlags(Qt.ItemFlag.NoItemFlags)
    elif case == 'all-disabled':
        for row in (5, 6):
            for column in range(3):
                source.item(row, column).setFlags(Qt.ItemFlag.NoItemFlags)
    elif case == 'tree':
        parent = model.index(1, 0)
        chosen.select(model.index(0, 0, parent), model.index(0, 2, parent))
        chosen.select(model.index(1, 0), model.index(1, 2))
    selection = view.selectionModel()
    selection.select(chosen, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    expected = [[str(model.index(index.row(), column, index.parent()).data() or '') for column in range(3)]
                for index in sorted(selection.selectedRows(0), key=transfer._order_key)]
    monkeypatch.setattr(transfer, '_CHUNK_ROWS', 2)
    capture = transfer.ListCapture(view, view, selected=True)
    header, rows = _finish(capture)
    assert header == ('Name', 'Value', 'Other') and rows == expected
    assert bool(rows) is (case != 'all-disabled') and len({tuple(row) for row in rows}) == len(rows)
    assert source.rowCount() == 8 and source.item(0).text() == '0'
    view.deleteLater()


@pytest.mark.parametrize("custom", ['subclass', 'instance', 'class'])
def test_custom_selected_rows_delegation_is_preserved(qapp, monkeypatch, custom):
    view, model = _table()
    called = []

    def selected_rows(column=0):
        called.append(column)
        return [model.index(5, column), model.index(2, column)]

    if custom == 'subclass':
        class Custom(QItemSelectionModel):
            def selectedRows(self, column=0):  # noqa: N802 - Qt virtual method
                return selected_rows(column)
        view.setSelectionModel(Custom(model, view))
    elif custom == 'instance':
        monkeypatch.setattr(view.selectionModel(), 'selectedRows', selected_rows)
    else:
        monkeypatch.setattr(QItemSelectionModel, 'selectedRows', lambda _self, column=0: selected_rows(column))
    _header, rows = _finish(transfer.ListCapture(view, view, selected=True))
    assert called == [0] and [row[0] for row in rows] == ['2', '5']
    view.deleteLater()


def test_deep_parent_order_preparation_also_yields(qapp, monkeypatch):
    class Counted(QStandardItemModel):
        parents = 0

        def parent(self, index):
            self.parents += 1
            return super().parent(index)

    model = Counted()
    model.setHorizontalHeaderLabels(['Name'])
    item = QStandardItem('root')
    model.appendRow(item)
    for number in range(300):
        child = QStandardItem(str(number))
        item.appendRow(child)
        item = child
    view = QTreeView()
    view.setModel(model)
    view.selectionModel().select(item.index(), QItemSelectionModel.SelectionFlag.Select)
    monkeypatch.setattr(transfer, '_CHUNK_ROWS', 7)
    monkeypatch.setattr(transfer, '_CHUNK_SECONDS', 10)
    capture = transfer.ListCapture(view, view, selected=True)
    model.parents = 0
    capture.start()
    capture._timer.stop()
    capture._chunk()
    assert model.parents < 16 and capture._active and not capture.rows
    assert _finish(capture) == (('Name',), [['299']])
    view.deleteLater()


@pytest.mark.parametrize('change', ['selection', 'reset', 'data', 'cancel', 'insert-column', 'remove-column'])
def test_change_while_preparing_ranges_discards_stream_and_preserves_existing_file(qapp, monkeypatch, tmp_path, change):
    from je_file_tree.core.export import export_table_csv

    view, model = _table()
    selection = QItemSelection(model.index(0, 0), model.index(7, 2))
    view.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.Select)
    monkeypatch.setattr(transfer, '_CHUNK_ROWS', 1)
    stream, errors, ready = transfer.ListStream(), [], []
    capture = transfer.ListCapture(view, view, selected=True, stream=stream)
    capture.failed.connect(errors.append)
    capture.ready.connect(lambda *_: ready.append(True))
    capture.start()
    capture._timer.stop()
    capture._chunk()
    assert capture._active and not capture._pending and not capture.rows
    if change == 'selection':
        view.selectionModel().clearSelection()
    elif change == 'reset':
        model.clear()
    elif change == 'data':
        model.setData(model.index(0, 0), 'changed')
    elif change == 'insert-column':
        model.insertColumn(1)
    elif change == 'remove-column':
        model.removeColumn(1)
    else:
        capture.cancel()
    assert not capture._active and not capture._timer.isActive() and stream.closed.is_set()
    assert not ready and len(errors) == (0 if change == 'cancel' else 1)
    target = tmp_path / 'existing.csv'
    target.write_text('keep', encoding='utf-8')
    with pytest.raises(ValueError):
        export_table_csv(capture.header, stream.rows(), target)
    assert target.read_text(encoding='utf-8') == 'keep' and list(tmp_path.iterdir()) == [target]
    view.deleteLater()


def test_reentrant_data_change_cannot_repopulate_canceled_rows_or_restart_timer(qapp, monkeypatch):
    monkeypatch.setattr(transfer, '_CHUNK_SECONDS', 10)  # one chunk must reach the row on a slow runner too
    class Changing(QStandardItemModel):
        armed = False

        def data(self, index, role=Qt.ItemDataRole.DisplayRole):
            value = super().data(index, role)
            if self.armed and role == Qt.ItemDataRole.DisplayRole:
                self.armed = False
                self.setData(index, 'changed')
            return value

    model = Changing()
    model.setHorizontalHeaderLabels(['Name', 'Value'])
    model.appendRow([QStandardItem('before'), QStandardItem('old')])
    view = QTableView()
    view.setModel(model)
    view.selectionModel().select(model.index(0, 0), QItemSelectionModel.SelectionFlag.Select
                                 | QItemSelectionModel.SelectionFlag.Rows)
    capture, errors, ready, finished = transfer.ListCapture(view, view, selected=True), [], [], []
    capture.failed.connect(errors.append)
    capture.ready.connect(lambda *_: ready.append(True))
    capture.finished.connect(lambda: finished.append(True))
    model.armed = True
    capture.start()
    capture._timer.stop()
    capture._chunk()
    assert errors and finished == [True] and not ready
    assert not capture.rows and not capture._pending and not capture._timer.isActive()
    assert model.item(0).text() == 'changed' and not capture._active
    view.deleteLater()


@pytest.mark.parametrize('replace', ['model', 'selection-model'])
def test_rebinding_view_during_selection_preparation_aborts_before_using_old_selection(qapp, monkeypatch, replace):
    view, model = _table()
    view.selectionModel().select(model.index(0, 0), QItemSelectionModel.SelectionFlag.Select
                                 | QItemSelectionModel.SelectionFlag.Rows)
    monkeypatch.setattr(transfer, '_CHUNK_ROWS', 1)
    capture, errors, ready = transfer.ListCapture(view, view, selected=True), [], []
    capture.failed.connect(errors.append)
    capture.ready.connect(lambda *_: ready.append(True))
    capture.start()
    capture._timer.stop()
    capture._chunk()
    capture._timer.stop()
    if replace == 'model':
        replacement = QStandardItemModel(view)
        replacement.appendRow(QStandardItem('new'))
        view.setModel(replacement)
    else:
        view.setSelectionModel(QItemSelectionModel(model, view))
    capture._chunk()
    assert len(errors) == 1 and not ready and not capture._active
    assert not capture.rows and not capture._pending and not capture._timer.isActive()
    view.deleteLater()


def test_destroying_view_cancels_parent_owned_stream_capture(qapp, monkeypatch):
    view, model = _table()
    view.selectionModel().select(model.index(0, 0), QItemSelectionModel.SelectionFlag.Select
                                 | QItemSelectionModel.SelectionFlag.Rows)
    owner, stream, errors = QObject(), transfer.ListStream(), []
    capture = transfer.ListCapture(view, owner, selected=True, stream=stream)
    capture.failed.connect(errors.append)
    monkeypatch.setattr(transfer, '_CHUNK_ROWS', 1)
    capture.start()
    capture._timer.stop()
    capture._chunk()
    capture._timer.stop()
    view.deleteLater()
    QCoreApplication.sendPostedEvents(view, QEvent.Type.DeferredDelete)
    assert len(errors) == 1 and not capture._active and stream.closed.is_set()
    assert not capture._timer.isActive() and not capture.rows and not capture._pending
    owner.deleteLater()


def test_many_whole_row_groups_do_not_revisit_every_other_parent(qapp):
    class Counted(grouped_list.GroupedListModel):
        parents = 0

        def parent(self, index):
            self.parents += 1
            return super().parent(index)

    model = Counted()
    model.set_groups([(str(group), [Node(f'{group}-{row}', False) for row in range(2)])
                      for group in range(400)], 'auto')
    view = grouped_list.build_view(model)
    selection = QItemSelection()
    for group in range(400):
        parent = model.index(group, 0)
        selection.select(model.index(0, 0, parent), model.index(1, 3, parent))
    view.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    model.parents = 0
    _header, rows = _finish(transfer.ListCapture(view, view, selected=True))
    assert model.parents < 20000, model.parents
    assert [row[0] for row in rows] == [f'{group}-{row}' for group in range(400) for row in range(2)]
    view.deleteLater()


def test_complete_row_fast_path_matches_native_pending_select_toggle_and_deselect_commands(qapp):
    view, model = _table()
    randomizer = random.Random(4071)  # noqa: S311 - reproducible model/selection parity, no secrets
    flags = QItemSelectionModel.SelectionFlag
    commands = [flags.Select, flags.Deselect, flags.Toggle, flags.ClearAndSelect,
                flags.Select | flags.Current, flags.Deselect | flags.Current, flags.Toggle | flags.Current]
    choices = [Qt.ItemFlag.NoItemFlags, Qt.ItemFlag.ItemIsSelectable, Qt.ItemFlag.ItemIsEnabled,
               Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable]
    try:
        for case in range(40):
            view.selectionModel().clearSelection()
            for row in range(8):
                for column in range(3):
                    model.item(row, column).setFlags(choices[randomizer.randrange(len(choices))])
            for _ in range(8):
                top, bottom = sorted(randomizer.sample(range(8), 2))
                left, right = sorted(randomizer.sample(range(3), 2))
                part = QItemSelection(model.index(top, left), model.index(bottom, right))
                view.selectionModel().select(part, randomizer.choice(commands))
            expected = [[str(model.index(index.row(), column).data()) for column in range(3)]
                        for index in sorted(view.selectionModel().selectedRows(0), key=transfer._order_key)]
            capture = transfer.ListCapture(view, view, selected=True)
            _header, rows = _finish(capture)
            assert rows == expected, (case, rows, expected)
            capture.deleteLater()
    finally:
        view.deleteLater()


def test_equal_row_paths_under_different_parent_columns_keep_both_native_rows(qapp):
    view, model = _table()
    for column, prefix in ((0, 'a'), (1, 'b')):
        model.item(0, column).appendRow([QStandardItem(prefix+str(cell)) for cell in range(3)])
    chosen = QItemSelection()
    for column in (1, 0):
        parent = model.index(0, column)
        chosen.select(model.index(0, 0, parent), model.index(0, 2, parent))
    view.selectionModel().select(chosen, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    native = sorted(view.selectionModel().selectedRows(0), key=transfer._order_key)
    expected = [[str(model.index(index.row(), column, index.parent()).data()) for column in range(3)]
                for index in native]
    assert len(expected) == 2 and {row[0] for row in expected} == {'a0', 'b0'}
    _header, rows = _finish(transfer.ListCapture(view, view, selected=True))
    assert rows == expected
    view.deleteLater()
